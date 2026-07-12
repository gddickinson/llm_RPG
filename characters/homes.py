"""Occupants & homes (P9A.3) — buildings belong to somebody.

George: "Different buildings are likely to have different occupants
depending on the style of building and the occupants occupation."
The AW survey's correction is applied here: occupants are bound to
buildings EXPLICITLY at world start, never by proximity accident.

- Named preset NPCs keep their authored homes (the tavernkeeper at
  the tavern, Durgan at his forge). A guard whose "home" is just the
  settlement moves into the watch building if one stands.
- Every other enterable building takes style-matched residents from
  its blueprint's npc_class/npc_count (farmhouses get farmers, the
  library gets a wizard) with generated names.
- Buildings that match no occupation stand DERELICT — flagged on the
  location and dusty in the interior description.

Residents are full NPCs: schedules route them home at night (the
existing "home" activity), they gossip, sicken (P8.2), and witness.
`occupants_of` / `owner_of` / `is_derelict` feed the P9A.4 trespass
system. Everything persists through the normal NPC save path.
"""

import logging
from typing import List, Optional

logger = logging.getLogger("llm_rpg.homes")

RESIDENT_NAMES = ("Merta", "Aldo", "Bess", "Tomlin", "Rhea", "Cobb",
                  "Ivo", "Sela", "Bram", "Nolla", "Piet", "Gwen")
GUARD_HOMES = ("watchtower", "barracks", "keep")
MAX_RESIDENTS = 2


class HomeSystem:
    def __init__(self, engine):
        self.engine = engine
        self._name_i = 0

    # ------------------------------------------------------ assignment

    def assign(self) -> int:
        """Bind occupants at new-game start. Idempotent. Returns the
        number of residents created."""
        engine = self.engine
        self._rehome_guards()
        occupied = {getattr(n, "home_location", "")
                    for n in engine.npc_manager.npcs.values()
                    if n.is_active()}
        created = 0
        try:
            from world.blueprints import blueprint_for_location
        except Exception:
            return 0
        for loc in engine.world.locations:
            if loc.name not in engine.interiors or \
                    loc.name in occupied:
                continue
            # An "Abandoned ..." building stands empty on purpose — a
            # derelict home the player can claim (P15.12).
            if "abandoned" in loc.name.lower():
                self._mark_derelict(loc)
                continue
            bp = blueprint_for_location(loc.name)
            npc_class = getattr(bp, "npc_class", "") if bp else ""
            count = min(MAX_RESIDENTS,
                        getattr(bp, "npc_count", 1) if bp else 1)
            if not npc_class:
                self._mark_derelict(loc)
                continue
            for _ in range(max(1, count)):
                if self._spawn_resident(loc, npc_class):
                    created += 1
        if created:
            logger.info(f"Homes: {created} residents moved in")
        return created

    def _rehome_guards(self) -> None:
        """A guard 'living' in the settlement at large gets the watch."""
        engine = self.engine
        watch = [l for l in engine.world.locations
                 if any(k in l.name.lower() for k in GUARD_HOMES)]
        if not watch:
            return
        for npc in engine.npc_manager.npcs.values():
            if getattr(npc.character_class, "value", "") != "guard":
                continue
            home = getattr(npc, "home_location", "")
            if home and home in engine.interiors:
                continue
            npc.home_location = watch[0].name

    def _spawn_resident(self, loc, npc_class: str) -> bool:
        from characters.character import Character
        from characters.character_types import (CharacterClass,
                                                CharacterRace)
        engine = self.engine
        try:
            klass = CharacterClass(npc_class)
        except ValueError:
            klass = CharacterClass.VILLAGER
        name = RESIDENT_NAMES[self._name_i % len(RESIDENT_NAMES)]
        self._name_i += 1
        spot = self._doorstep(loc)
        if spot is None:
            return False
        nid = f"res_{loc.name.lower().replace(' ', '_')}_{self._name_i}"
        npc = Character(
            id=nid, name=name, character_class=klass,
            race=CharacterRace.HUMAN, level=1,
            strength=9, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
            hp=10, max_hp=10, position=spot,
            description=f"{name} of the {loc.name}.",
            personality={"traits": ["settled"]},
            goals=[f"Keep the {loc.name} in good order"],
            inventory=[],
        )
        npc.home_location = loc.name
        engine.npc_manager.add_npc(npc)
        engine.world.map.place_character(npc, *spot)
        return True

    def _doorstep(self, loc) -> Optional[tuple]:
        wmap = self.engine.world.map
        for dx, dy in ((0, loc.height), (loc.width, 0), (-1, 0),
                       (0, -1), (loc.width, loc.height)):
            x, y = loc.x + dx, loc.y + dy
            if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                continue
            try:
                if wmap.get_terrain_at(x, y).value in \
                        ("water", "mountain", "building"):
                    continue
                if wmap.get_character_at(x, y) is None:
                    return (x, y)
            except Exception:
                continue
        return None

    def _mark_derelict(self, loc) -> None:
        loc.add_property("derelict", True)
        inter = self.engine.interiors.get(loc.name)
        if inter is not None and "Dust lies thick" not in \
                inter.description:
            inter.description += " Dust lies thick — no one lives here."

    # ----------------------------------------------------------- query

    def occupants_of(self, loc_name: str) -> List:
        return [n for n in self.engine.npc_manager.npcs.values()
                if getattr(n, "home_location", "") == loc_name
                and n.is_active()]

    def owner_of(self, loc_name: str):
        occupants = self.occupants_of(loc_name)
        return occupants[0] if occupants else None

    def is_derelict(self, loc_name: str) -> bool:
        for loc in self.engine.world.locations:
            if loc.name == loc_name:
                return bool(loc.get_property("derelict", False))
        return False
