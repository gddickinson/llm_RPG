"""The autonomous Dungeon Master (P6.4).

When an LLM provider is active, one planning call per game-day: the
model reads the world digest and its own campaign notes, updates the
arc, and proposes a small command bundle — executed through the same
charter-enforced DM API as every other driver. Junk output means a
quiet day. No provider means this module never runs; the world director
keeps the world alive as before.
"""

import json
import logging
import re
from typing import List

logger = logging.getLogger("llm_rpg.dm_auto")

MAX_COMMANDS_PER_DAY = 6
MAX_NOTES = 800

DM_SYSTEM = """You are the Dungeon Master of a living fantasy RPG. Once per day you may quietly shape the world to make play richer: foreshadow, plant, escalate, pay off. You work in multi-day arcs.

Reply with ONLY JSON:
{"arc_notes": "<your private campaign notes: current arc, planted threads, promises to keep — under 600 chars>",
 "commands": [{"command": "<name>", "args": {...}}, ...]}

Commands (max %d/day; the engine enforces a strict charter — refusals are normal, adapt tomorrow):
- narrate {text} — atmospheric scene line the player sees, prefixed [DM]
- define_monster {template_id, spec:{name,class,race,hp,level,symbol,description}}
- define_item {item_id, spec:{name,item_type,value,description,...}}
- spawn_npc {template_id, position:[x,y]} — never near the player
- place_item {item_id, position:[x,y]}
- add_building {name,x,y,w,h,description}
- edit_terrain {x,y,w,h,terrain}
- create_quest {quest_id, spec:{title,description,objectives:[{type,target,required,description}],giver_id,reward_gold,reward_xp}}
- adjust_faction {faction, delta}
- schedule_beat {day, command, args} — plant future payoffs

Principles: build on what the player is already doing (read their quests and deeds); foreshadow before you strike; reuse your own creations; small consistent touches beat grand disconnected gestures; never target the player directly.""" % MAX_COMMANDS_PER_DAY


class AutonomousDM:
    def __init__(self, engine):
        self.engine = engine

    def active(self) -> bool:
        iface = getattr(self.engine, "llm_interface", None)
        return iface is not None and \
            getattr(iface, "provider_name", "heuristic") != "heuristic"

    def run_day(self) -> List[dict]:
        """The daily planning call. Returns executed command results."""
        if not self.active():
            return []
        dm = self.engine.dm
        digest = json.dumps(dm.digest(), default=str)
        notes = dm.campaign_notes or "(a fresh campaign — no arc yet)"
        prompt = (f"YOUR CAMPAIGN NOTES\n{notes}\n\n"
                  f"THE WORLD TODAY\n{digest}\n\n"
                  f"Plan tonight's touches.")
        try:
            raw = self.engine.llm_interface.generate_response(
                prompt, DM_SYSTEM, max_tokens=900, temperature=0.9)
        except Exception as e:
            logger.warning(f"DM planning call failed: {e}")
            return []

        plan = self._parse(raw)
        if plan is None:
            dm._log("plan_day", False, "unparseable plan — quiet day")
            return []

        new_notes = str(plan.get("arc_notes", ""))[:MAX_NOTES]
        if new_notes:
            dm.campaign_notes = new_notes

        from engine.dm_bridge import ALLOWED_COMMANDS
        results = []
        for entry in plan.get("commands", [])[:MAX_COMMANDS_PER_DAY]:
            if not isinstance(entry, dict):
                continue
            command = str(entry.get("command", ""))
            args = entry.get("args", {})
            if command not in ALLOWED_COMMANDS or \
                    not isinstance(args, dict):
                dm._log(command or "(none)", False,
                        "autonomous DM proposed a non-command")
                continue
            try:
                ok, note = getattr(dm, command)(**args)
            except TypeError as e:
                ok, note = dm._log(command, False, f"bad args: {e}")
            except Exception as e:
                ok, note = dm._log(command, False, f"error: {e}")
            results.append({"command": command, "ok": ok,
                            "note": note})
        dm._log("plan_day", True,
                f"{sum(1 for r in results if r['ok'])} of "
                f"{len(results)} commands landed")
        return results

    @staticmethod
    def _parse(raw: str):
        if not raw:
            return None
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
