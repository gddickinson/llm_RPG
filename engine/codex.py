"""The Field Guide / Codex (GAP.2) — the game teaches itself.

This game has ~150 systems; most are "dark matter" a player never finds.
The codex fixes that: authored entries (data/codex.json) auto-unlock the
first time a trigger phrase appears in the event log, dropping a
`[Codex]` beat that says, in one actionable line, what you just brushed
against and which key uses it. The Y-journal then lists everything you
have discovered — a running answer to "what can I even do here?".

State lives in `player.metadata["codex"]` so it rides the save for free
(the collection-log pattern). Registered as a memory observer in
`engine_setup`.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.codex")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "codex.json")


class CodexSystem:
    def __init__(self, engine):
        self.engine = engine
        self.entries = []
        self._by_id = {}
        try:
            with open(_DATA, encoding="utf-8") as fh:
                self.entries = json.load(fh).get("entries", [])
            self._by_id = {e["id"]: e for e in self.entries}
        except Exception as e:                       # pragma: no cover
            logger.info(f"Codex data unavailable: {e}")

    # ---- storage -------------------------------------------------------

    def _store(self):
        return self.engine.player.metadata.setdefault("codex", [])

    def is_unlocked(self, eid) -> bool:
        return eid in self._store()

    def _ensure_start(self):
        """Unlock `start:true` entries silently, once."""
        seen = self._store()
        for e in self.entries:
            if e.get("start") and e["id"] not in seen:
                seen.append(e["id"])

    # ---- unlocking -----------------------------------------------------

    def unlock(self, eid, announce=True) -> bool:
        e = self._by_id.get(eid)
        if e is None or eid in self._store():
            return False
        self._store().append(eid)
        meta = self.engine.player.metadata
        meta["codex_unseen"] = meta.get("codex_unseen", 0) + 1
        if announce:
            try:
                self.engine.memory_manager.add_event(
                    f"[Codex] New journal entry: {e['title']} — {e['hint']}")
            except Exception:
                pass
        return True

    def on_event(self, text: str) -> None:
        """Watch the log; unlock any entry a trigger phrase matches."""
        if not text or text.startswith("[Codex]"):
            return
        self._ensure_start()
        low = text.lower()
        for e in self.entries:
            if e["id"] in self._store():
                continue
            for trig in e.get("triggers", ()):
                if trig.lower() in low:
                    self.unlock(e["id"])
                    break

    # ---- read side -----------------------------------------------------

    def counts(self):
        self._ensure_start()
        return len(self._store()), len(self.entries)

    def mark_seen(self):
        self.engine.player.metadata["codex_unseen"] = 0

    def unseen(self) -> int:
        return self.engine.player.metadata.get("codex_unseen", 0)

    def overlay_lines(self):
        """The 'Field Guide' block for the Y-journal."""
        self._ensure_start()
        seen = self._store()
        got, total = len(seen), len(self.entries)
        lines = ["", f"— Field Guide ({got}/{total} discovered) —"]
        cats = []
        for e in self.entries:
            if e["category"] not in cats:
                cats.append(e["category"])
        for cat in cats:
            unlocked = [e for e in self.entries
                        if e["category"] == cat and e["id"] in seen]
            if not unlocked:
                continue
            lines.append(f"  {cat}:")
            for e in unlocked:
                lines.append(f"    • {e['title']} — {e['hint']}")
        # a cheap bestiary / gazetteer tally from the collection log
        try:
            kills = len(self.engine.collection_log.obtained("kills"))
            places = len(self.engine.collection_log.obtained("places"))
            lines.append(f"  Creatures encountered: {kills}   "
                         f"Places discovered: {places}")
        except Exception:
            pass
        undiscovered = total - got
        if undiscovered > 0:
            lines.append(f"  ...and {undiscovered} way(s) yet undiscovered. "
                         f"Keep exploring.")
        self.mark_seen()
        return lines
