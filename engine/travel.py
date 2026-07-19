"""Travel: terrain crossings + earned teleports (P2.8).

Crossings — bumping blocking terrain routes through the P11.1
traversal framework (engine/traversal.py): wade at shores, graded
swim/climb checks beyond, trained by Swimming/Agility.

Teleports — a travel menu (U key). Oakvale is always available; the
other settlements unlock by claiming their diary's easy tier ("the diary
reward is a teleport there"). Teleporting outside Oakvale costs a toll,
and all teleports share a cooldown stored in player metadata.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.travel")

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

    # ---- terrain crossings (P11.1) ---------------------------------------

    def try_shortcut(self, nx: int, ny: int) -> Optional[str]:
        """Attempt to cross blocking terrain via the traversal
        framework. Returns its message (crossed or failed); None if
        the tile has no traversal rule."""
        msg = self.engine.traversal.attempt_cross(nx, ny)
        if msg is not None and \
                self.engine.player.position == (nx, ny):
            try:
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

    def _safe_landing(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """A walkable overworld tile at or near `pos` — never a BUILDING /
        water / mountain the teleport would strand the player ON (a
        settlement's centre often overlaps a building). Bug-fix 2026-07-12e
        (George: teleporting to Oakvale trapped me on a building tile)."""
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        solid = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = pos[0] + dx, pos[1] + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in solid or (x, y) in wmap.characters:
                        continue
                    return (x, y)
        return pos

    def destinations(self) -> List[dict]:
        out = []
        quest_unlocks = self.engine.player.metadata.get(
            "teleport_unlocks", [])
        for key, name, loc_part, region in DESTINATIONS:
            pos = self._find_destination_pos(loc_part)
            unlocked = region is None or \
                "easy" in self.engine.diary_manager.claimed(region) or \
                key in quest_unlocks
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

    def at_station(self) -> bool:
        """Standing on (or beside) a WAYSTONE — a magical transit platform.
        Fast-travel departs only from one (George: no teleporting to anywhere
        from anywhere; you must reach a station first)."""
        tn = getattr(self.engine, "teleport_network", None)
        if tn is None:
            return False
        try:
            return tn.platform_at(self.engine.player.position) is not None
        except Exception:
            return False

    def teleport(self, index: int) -> str:
        if not self.at_station():
            return ("You can only travel from a waystone — find a rune-circle "
                    "platform and step onto it.")
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
        landing = self._safe_landing(dest["pos"])
        wmap.remove_character(player)
        player.position = landing
        wmap.place_character(player, *landing)
        cooldown = TELEPORT_COOLDOWN_MIN
        try:
            cooldown = int(cooldown *
                           self.engine.guild.teleport_cooldown_multiplier())
        except Exception:
            pass
        player.metadata["teleport_ready_at"] = \
            self.engine.world.time + cooldown
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
