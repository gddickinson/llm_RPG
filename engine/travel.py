"""Travel: agility shortcuts + earned teleports (P2.8).

Shortcuts — high Agility turns blocking terrain into paths anywhere on
the map: level 15 clambers over mountains, level 25 swims across water.
Each crossing costs extra minutes and grants Agility XP (the skill that
literally opens the map).

Teleports — a travel menu (U key). Oakvale is always available; the
other settlements unlock by claiming their diary's easy tier ("the diary
reward is a teleport there"). Teleporting outside Oakvale costs a toll,
and all teleports share a cooldown stored in player metadata.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.travel")

CLIMB_LEVEL = 15
SWIM_LEVEL = 25
SHORTCUT_XP = 8
SHORTCUT_EXTRA_MINUTES = 3
TELEPORT_COOLDOWN_MIN = 240   # 4 game hours
TELEPORT_TOLL = 15

# (key, display name, location-name substring, diary region or None=free)
DESTINATIONS = [
    ("oakvale", "Oakvale Village", "Oakvale Village", None),
    ("riverside", "Riverside Hamlet", "Riverside", "riverside"),
    ("stonepine", "Stonepine Camp", "Stonepine", "stonepine"),
]


class TravelSystem:
    def __init__(self, engine):
        self.engine = engine

    # ---- agility shortcuts ----------------------------------------------

    def try_shortcut(self, nx: int, ny: int) -> Optional[str]:
        """Attempt to cross blocking terrain. Returns a message if the
        tile was shortcut-able (crossed or level-gated); None otherwise."""
        from world.world_map import TerrainType
        from engine.skill_progression import (get_skill_level,
                                              add_skill_xp)
        wmap = self.engine.world.map
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            return None
        terrain = wmap.get_terrain_at(nx, ny)
        if terrain == TerrainType.MOUNTAIN:
            needed, verb = CLIMB_LEVEL, "clamber over the rocks"
        elif terrain == TerrainType.WATER:
            needed, verb = SWIM_LEVEL, "swim across"
        else:
            return None

        player = self.engine.player
        level = get_skill_level(player, "agility")
        if level < needed:
            hint = (f"You can't pass. (Agility {needed} would let "
                    f"you {verb}.)")
            self.engine.memory_manager.add_event(hint)
            return hint

        # Don't land on another character
        for npc in self.engine.npc_manager.npcs.values():
            if npc.is_active() and npc.position == (nx, ny):
                return None

        old_pos = player.position
        wmap.remove_character(player)
        player.position = (nx, ny)
        wmap.place_character(player, nx, ny)
        self.engine.world.advance_time(SHORTCUT_EXTRA_MINUTES)
        msg = f"You {verb}. (+{SHORTCUT_XP} Agility XP)"
        self.engine.memory_manager.add_event(msg)
        for note in add_skill_xp(player, "agility", SHORTCUT_XP):
            self.engine.memory_manager.add_event(note)
        try:
            self.engine.pet_system.on_player_moved(old_pos)
            self.engine.pet_system.maybe_award("agility")
        except Exception:
            pass
        return msg

    # ---- teleports ---------------------------------------------------------

    def _find_destination_pos(self, name_part: str) -> Optional[Tuple[int, int]]:
        for loc in self.engine.world.locations:
            if name_part.lower() in loc.name.lower():
                return (loc.x + loc.width // 2, loc.y + loc.height // 2)
        return None

    def destinations(self) -> List[dict]:
        out = []
        for key, name, loc_part, region in DESTINATIONS:
            pos = self._find_destination_pos(loc_part)
            unlocked = region is None or \
                "easy" in self.engine.diary_manager.claimed(region)
            out.append({
                "key": key, "name": name, "pos": pos,
                "unlocked": unlocked and pos is not None,
                "toll": 0 if region is None else TELEPORT_TOLL,
                "locked_reason": (
                    "" if unlocked else
                    f"complete the {name.split()[0]} diary (easy)"),
            })
        return out

    def cooldown_remaining(self) -> int:
        ready_at = self.engine.player.metadata.get("teleport_ready_at", 0)
        return max(0, ready_at - self.engine.world.time)

    def teleport(self, index: int) -> str:
        dests = self.destinations()
        if not (0 <= index < len(dests)):
            return "No such destination."
        dest = dests[index]
        if not dest["unlocked"]:
            return f"{dest['name']} is locked — {dest['locked_reason']}."
        remaining = self.cooldown_remaining()
        if remaining > 0:
            return (f"Your travel focus needs {remaining} more minutes "
                    f"to recover.")
        player = self.engine.player
        if dest["toll"] and player.gold < dest["toll"]:
            return f"The toll is {dest['toll']}g (you have {player.gold})."
        if dest["toll"]:
            player.gold -= dest["toll"]

        wmap = self.engine.world.map
        wmap.remove_character(player)
        player.position = dest["pos"]
        wmap.place_character(player, *dest["pos"])
        player.metadata["teleport_ready_at"] = \
            self.engine.world.time + TELEPORT_COOLDOWN_MIN
        toll_note = f" (toll {dest['toll']}g)" if dest["toll"] else ""
        msg = f"You travel to {dest['name']}{toll_note}."
        self.engine.memory_manager.add_event(msg)
        self.engine.advance_turn()
        return msg

    # ---- UI --------------------------------------------------------------

    def overlay_lines(self) -> List[str]:
        out = ["Choose a destination (1-9), Esc to cancel:", ""]
        cd = self.cooldown_remaining()
        if cd:
            out.append(f"(travel focus recovering: {cd} min)")
            out.append("")
        for i, dest in enumerate(self.destinations(), start=1):
            if dest["unlocked"]:
                toll = f"  — toll {dest['toll']}g" if dest["toll"] else ""
                out.append(f"  {i}. {dest['name']}{toll}")
            else:
                out.append(f"  {i}. {dest['name']}  [LOCKED — "
                           f"{dest['locked_reason']}]")
        return out
