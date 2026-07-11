"""Doors & locks (P9A.1) — you can no longer walk into any building.

George's playtest: "They shouldn't be allowed to enter any building at
will. Doors need to be opened, locks need keys or to be picked/forced."
The autonomous_world survey confirmed openable doors and keys were
never built there, so this is new work; the lockpick/force checks port
its d20 pattern; P12.1 graded the rolls — crit failures snap picks
and pop shoulders, crit successes are quiet or clean.

Policy comes from `data/doors.json` by building-name match: homes are
LOCKED (their owner's key may exist), shops and forges lock at NIGHT,
taverns/temples/shrines stay open. A locked door yields to, in order:
the right key in your pack, a lockpick attempt (d20 + DEX modifier vs
the lock level; a bad failure breaks your picks), or force (SHIFT+TAB:
d20 + STR modifier, and NOISY either way — the crash is remembered for
the trespass system, P9A.4). Forced locks stay broken until dawn, when
every intact door resets to its policy. State persists via save_load.
"""

import json
import logging
import os
import random
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.doors")

FORCE_BONUS_DC = 3         # forcing is harder than picking


def _load_styles() -> dict:
    try:
        with open(os.path.join("data", "doors.json")) as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        logger.warning("doors.json missing/corrupt; all doors open")
        return {"styles": [], "default": {"policy": "open"}}


STYLES = _load_styles()


def _mod(score: int) -> int:
    return (score - 10) // 2


class DoorManager:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        # location name -> {"state", "lock_level", "key"}
        self.doors: Dict[str, dict] = {}

    # ----------------------------------------------------------- state

    def spec_for(self, name: str) -> dict:
        low = name.lower()
        for style in STYLES.get("styles", []):
            if any(word in low for word in style.get("match", [])):
                return style
        return STYLES.get("default", {"policy": "open"})

    def door(self, name: str) -> dict:
        if name not in self.doors:
            spec = self.spec_for(name)
            policy = spec.get("policy", "open")
            state = "locked" if policy == "locked" else \
                ("closed" if policy == "night_locked" else "open")
            self.doors[name] = {"state": state,
                                "policy": policy,
                                "lock_level": spec.get("lock_level", 10),
                                "key": spec.get("key")}
        return self.doors[name]

    def _is_night(self) -> bool:
        try:
            return self.engine.world.get_time_of_day() in ("night",
                                                           "evening")
        except Exception:
            return False

    def _effective_state(self, door: dict) -> str:
        if door["policy"] == "night_locked" and \
                door["state"] == "closed" and self._is_night():
            return "locked"
        return door["state"]

    # ----------------------------------------------------------- entry

    def try_enter(self, name: str) -> Tuple[bool, str]:
        """Called by enter_building. (allowed, message-prefix/refusal)."""
        door = self.door(name)
        state = self._effective_state(door)
        if state in ("open", "broken"):
            return True, ""
        if state == "closed":
            door["state"] = "open"
            return True, "You push the door open. "
        # locked
        key_msg = self._try_key(door)
        if key_msg:
            return True, key_msg
        pick = self._try_picks(door, name)
        if pick is not None:
            return pick
        return False, (f"The {name} is locked tight. "
                       f"(Lockpicks could open it — or force it "
                       f"with SHIFT+TAB.)")

    def _try_key(self, door: dict) -> Optional[str]:
        key_id = door.get("key")
        if not key_id:
            return None
        for item in self.engine.player.inventory:
            if getattr(item, "id", "") == key_id:
                door["state"] = "open"
                return f"Your {item.name} turns in the lock. "
        return None

    def _try_picks(self, door: dict,
                   name: str) -> Optional[Tuple[bool, str]]:
        player = self.engine.player
        picks = next((i for i in player.inventory
                      if getattr(i, "id", "") == "lockpicks"), None)
        if picks is None:
            return None
        from engine.skills import Degree, Skill, check
        result = check(player, Skill.LOCKPICKING,
                       dc=door["lock_level"], rng=self.rng)
        if result.degree is Degree.CRIT_SUCCESS:
            door["state"] = "open"
            self.engine.memory_manager.add_event(
                f"You pick the lock of the {name}.")
            return True, ("The lock springs open at the first "
                          "touch — flawless work. ")
        if result.success:
            door["state"] = "open"
            msg = "The lock clicks open under your picks. "
            self.engine.memory_manager.add_event(
                f"You pick the lock of the {name}.")
            return True, msg
        if result.degree is Degree.CRIT_FAIL:
            player.inventory.remove(picks)
            return False, ("Your lockpicks snap off in the lock! "
                           "You'll need a new set.")
        return False, ("The lock resists your picks. "
                       "(Try again, or force it with SHIFT+TAB.)")

    def force(self, name: str) -> Tuple[bool, str]:
        """SHIFT+TAB: shoulder the door. Noisy, remembered."""
        door = self.door(name)
        if self._effective_state(door) in ("open", "broken"):
            return True, "The door already stands open."
        player = self.engine.player
        from engine.skills import Degree, Skill, check
        result = check(player, Skill.ATHLETICS,
                       dc=door["lock_level"] + FORCE_BONUS_DC,
                       rng=self.rng)
        day = self.engine.world.time // (24 * 60)
        player.metadata["forced_entry_day"] = day     # P9A.4 hook
        self.engine.memory_manager.add_event(
            "The crash of splintering wood echoes down the street.")
        if result.degree is Degree.CRIT_SUCCESS:
            door["state"] = "broken"
            msg = (f"The door of the {name} bursts off its hinges — "
                   f"one clean hit!")
            self.engine.memory_manager.add_event(msg)
            return True, msg
        if result.success:
            door["state"] = "broken"
            msg = f"The door of the {name} gives way!"
            self.engine.memory_manager.add_event(msg)
            return True, msg
        if result.degree is Degree.CRIT_FAIL:
            player.take_damage(2)
            if player.hp <= 0:
                player.hp = 1
            return False, ("Something pops in your shoulder! (-2 HP) "
                           "The door doesn't budge — and someone "
                           "will have heard that.")
        return False, "The door shudders but holds. Your shoulder " \
                      "aches — and someone will have heard that."

    # --------------------------------------------------------- nightly

    def run_day(self) -> None:
        """Dawn: every intact door resets to its policy; broken doors
        get repaired by their owners."""
        for name, door in self.doors.items():
            policy = door["policy"]
            door["state"] = "locked" if policy == "locked" else \
                ("closed" if policy == "night_locked" else "open")

    # ----------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"doors": {k: dict(v) for k, v in self.doors.items()}}

    def from_dict(self, data: dict) -> None:
        self.doors = {k: dict(v)
                      for k, v in data.get("doors", {}).items()}
