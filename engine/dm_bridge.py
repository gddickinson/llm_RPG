"""Session-DM bridge (P6.3) — a live Dungeon Master over files.

Run the game with `--dm-bridge` and it maintains `saves/dm/`:

    digest.json          — the world digest, refreshed periodically and
                           at every dawn (what the DM reads)
    inbox/*.json         — command bundles the DM drops in:
                           {"commands": [{"command": "narrate",
                                          "args": {"text": "..."}}]}
    processed/           — consumed bundles + a .result.json for each,
                           listing per-command ok/notes

A Claude Code session (or any tool, or a human with a text editor)
reads the digest, reasons, and writes bundles — the game applies them
through the charter-enforced DM API within a couple of seconds.
Malformed input never crashes the game; it lands in processed/ with an
error result.
"""

import json
import logging
import os
import time
from typing import List, Tuple

logger = logging.getLogger("llm_rpg.dm_bridge")

POLL_SECONDS = 2.0
DIGEST_SECONDS = 10.0

ALLOWED_COMMANDS = (
    "narrate", "define_monster", "define_item", "spawn_npc",
    "place_item", "add_building", "edit_terrain", "create_quest",
    "adjust_faction", "schedule_beat", "install_module",
    "define_structure",
)


class DMBridge:
    def __init__(self, engine, root: str = None):
        self.engine = engine
        self.root = root or os.path.join("saves", "dm")
        self.inbox = os.path.join(self.root, "inbox")
        self.processed = os.path.join(self.root, "processed")
        for d in (self.root, self.inbox, self.processed):
            os.makedirs(d, exist_ok=True)
        self._last_poll = 0.0
        self._last_digest = 0.0
        self.export_digest()
        self._write_readme()

    # ---- outbound -------------------------------------------------------

    def export_digest(self) -> str:
        path = os.path.join(self.root, "digest.json")
        tmp = path + ".tmp"
        try:
            with open(tmp, "w") as fp:
                json.dump(self.engine.dm.digest(), fp, indent=2,
                          default=str)
            os.replace(tmp, path)
        except Exception as e:
            logger.warning(f"digest export failed: {e}")
        return path

    # ---- inbound ----------------------------------------------------------

    def tick(self) -> None:
        """Call from the frame/turn loop; throttles itself."""
        now = time.monotonic()
        if now - self._last_digest >= DIGEST_SECONDS:
            self._last_digest = now
            self.export_digest()
        if now - self._last_poll >= POLL_SECONDS:
            self._last_poll = now
            self.poll()

    def poll(self) -> int:
        """Consume every bundle in the inbox. Returns bundles handled."""
        try:
            names = sorted(f for f in os.listdir(self.inbox)
                           if f.endswith(".json"))
        except OSError:
            return 0
        handled = 0
        for name in names:
            path = os.path.join(self.inbox, name)
            results = self._run_bundle(path)
            self._finish(name, path, results)
            handled += 1
        if handled:
            self.export_digest()
        return handled

    def _run_bundle(self, path: str) -> List[dict]:
        try:
            with open(path, "r") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as e:
            return [{"command": "(file)", "ok": False,
                     "note": f"unreadable bundle: {e}"}]
        commands = data.get("commands") if isinstance(data, dict) \
            else data
        if not isinstance(commands, list):
            return [{"command": "(file)", "ok": False,
                     "note": "bundle must be a list or "
                             "{'commands': [...]}"}]
        results = []
        for entry in commands[:32]:
            results.append(self._run_command(entry))
        return results

    def _run_command(self, entry) -> dict:
        if not isinstance(entry, dict):
            return {"command": "(entry)", "ok": False,
                    "note": "each command must be an object"}
        command = str(entry.get("command", ""))
        args = entry.get("args", {})
        if command not in ALLOWED_COMMANDS:
            return {"command": command, "ok": False,
                    "note": f"not a DM command (allowed: "
                            f"{', '.join(ALLOWED_COMMANDS)})"}
        if not isinstance(args, dict):
            return {"command": command, "ok": False,
                    "note": "args must be an object"}
        try:
            ok, note = getattr(self.engine.dm, command)(**args)
            return {"command": command, "ok": bool(ok), "note": note}
        except TypeError as e:
            return {"command": command, "ok": False,
                    "note": f"bad args: {e}"}
        except Exception as e:
            logger.warning(f"DM bridge command error: {e}")
            return {"command": command, "ok": False,
                    "note": f"error: {e}"}

    def _finish(self, name: str, path: str,
                results: List[dict]) -> None:
        result_path = os.path.join(self.processed,
                                   name[:-5] + ".result.json")
        try:
            with open(result_path, "w") as fp:
                json.dump({"bundle": name, "results": results},
                          fp, indent=2)
        except OSError as e:
            logger.warning(f"result write failed: {e}")
        try:
            os.replace(path, os.path.join(self.processed, name))
        except OSError:
            try:
                os.remove(path)
            except OSError:
                pass

    def _write_readme(self) -> None:
        path = os.path.join(self.root, "README.md")
        if os.path.exists(path):
            return
        try:
            with open(path, "w") as fp:
                fp.write(
                    "# DM Bridge\n\n"
                    "- Read `digest.json` for the state of the world.\n"
                    "- Drop `inbox/<name>.json` bundles:\n"
                    '  `{"commands": [{"command": "narrate", '
                    '"args": {"text": "..."}}]}`\n'
                    f"- Commands: {', '.join(ALLOWED_COMMANDS)}\n"
                    "- Results land in `processed/<name>.result.json`.\n")
        except OSError:
            pass
