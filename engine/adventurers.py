"""Adventurer NPCs (P-M.6) — the world's OTHER heroes.

Beyond the folk going about their farming and smithing, a small band of
adventuring-class NPCs live lives of their own: sharp-eyed scouts, broad
axemen, hedge-wizards. When they haven't found a company they hang about
the gathering places — the taverns — LOOKING for a band to join (which is
why the player, or a driven away-hero, can recruit one there even before
deep trust). Otherwise they are OUT in the world: roaming, cracking open
lairs, grabbing loot, and — through the very same policy the away-hero
uses — surviving, growing, or falling.

They ride the proven away-agent brain (`AgentController`), but with
`social=False`: an adventurer never touches the PLAYER's quest log or
party. Combat XP already flows to whoever acts, so an adventurer that
fights grows in level on its own.

Content-as-data: the band lives in `data/adventurers.json` (name, class,
race, level, disposition, home settlement, kit). Kept deliberately small
so driving them each turn stays cheap.
"""

import logging
import os
import random
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.adventurers")

MAX_DRIVEN = 4                 # keep the per-turn cost bounded
_WALKABLE = {TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD,
             TerrainType.BRIDGE, TerrainType.FARMLAND}


class AdventurerSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.controllers: Dict[str, object] = {}   # adventurer id -> brain
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _specs(self) -> List[dict]:
        from items.data_loader import load_data_file
        try:
            return load_data_file("adventurers.json").get("adventurers", [])
        except Exception as e:
            logger.debug(f"adventurers.json: {e}")
            return []

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        # Disabled across the general test suite (like module packs) so a
        # roaming, driven band doesn't perturb turn-advancing tests; the
        # adventurer tests clear this flag to exercise the real thing.
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return 0
        if self._seeded or self.controllers:
            return 0
        self._seeded = True
        placed = 0
        for spec in self._specs():
            spot = self._gathering_spot(spec.get("home", ""))
            if spot is None:
                continue
            if self._place(spec, spot):
                placed += 1
        if placed:
            logger.info(f"Seeded {placed} adventurer(s).")
        return placed

    def _gathering_spot(self, home: str) -> Optional[Tuple[int, int]]:
        """A walkable tile beside a tavern/inn (in the named settlement if
        we can find one) — where an adventurer loiters seeking a band."""
        locs = getattr(self.engine.world, "locations", [])
        taverns = [l for l in locs
                   if any(w in l.name.lower() for w in ("tavern", "inn"))]
        if home:
            pref = [l for l in taverns if home.lower() in l.name.lower()]
            taverns = pref or taverns
        for loc in taverns:
            spot = self._walkable_beside(loc.x, loc.y)
            if spot is not None:
                return spot
        # fallback: any walkable tile a little way from the player
        return self._any_walkable()

    def _walkable_beside(self, cx: int, cy: int) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1), (1, 1), (-1, 1)):
            x, y = cx + dx, cy + dy
            if 0 <= x < wmap.width and 0 <= y < wmap.height \
                    and wmap.terrain[y][x] in _WALKABLE \
                    and (x, y) not in wmap.characters:
                return (x, y)
        return None

    def _any_walkable(self) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        for _ in range(200):
            x = self.rng.randint(1, wmap.width - 2)
            y = self.rng.randint(1, wmap.height - 2)
            if wmap.terrain[y][x] in _WALKABLE and (x, y) not in wmap.characters \
                    and abs(x - px) + abs(y - py) > 6:
                return (x, y)
        return None

    def _place(self, spec: dict, spot) -> bool:
        from characters.character import Character
        from characters.character_types import CharacterClass, CharacterRace
        from items.item_registry import create_item
        try:
            lvl = spec.get("level", 1)
            hp = 10 + 4 * lvl
            s = 10 + lvl                     # solid, level-scaled abilities
            adv = Character(
                id=spec["id"], name=spec["name"],
                character_class=CharacterClass(spec.get("class", "warrior")),
                race=CharacterRace(spec.get("race", "human")),
                level=lvl,
                strength=s, dexterity=s, constitution=s,
                intelligence=s, wisdom=s, charisma=s,
                hp=hp, max_hp=hp,
                position=tuple(spot), gold=spec.get("gold", 0),
                description=spec.get("flavor", ""))
            adv.inventory = [it for it in
                             (create_item(i) for i in spec.get("inventory", []))
                             if it is not None]
            self._equip_best(adv)
            adv.metadata["adventurer"] = True
            adv.metadata["seeking_party"] = True
            adv.metadata["home_spot"] = list(spot)
            try:
                from engine.settings import set_setting
                set_setting(adv, "disposition",
                            spec.get("disposition", "balanced"))
            except Exception:
                pass
            self.engine.npc_manager.add_npc(adv)
            self.engine.world.map.place_character(adv, *spot)
            self.controllers[adv.id] = self._make_brain(spot)
            return True
        except Exception as e:
            logger.debug(f"Place adventurer {spec.get('id')}: {e}")
            return False

    def _equip_best(self, adv) -> None:
        from characters.equipment import equip
        for it in adv.inventory:
            try:
                if it.is_weapon() or it.is_ranged_weapon():
                    equip(adv, it)
                    break
            except Exception:
                continue

    def _make_brain(self, spot):
        from engine.agent_controller import AgentController
        ctrl = AgentController(seed=(spot[0] * 131 + spot[1]))
        ctrl.social = False                 # never touches player state
        ctrl.home = tuple(spot)             # loiter here while seeking
        return ctrl

    # ---- the per-turn drive ---------------------------------------

    def run_turn(self) -> None:
        """Drive each free, living adventurer one step. Recruited ones are
        the party's business (companion_manager); the dead are skipped."""
        party = getattr(getattr(self.engine, "companion_manager", None),
                        "party", {})
        driven = 0
        for aid, ctrl in list(self.controllers.items()):
            if driven >= MAX_DRIVEN:
                break
            adv = self.engine.npc_manager.npcs.get(aid)
            if adv is None or not adv.is_active():
                continue
            if aid in party:                # now a companion — hands off
                adv.metadata["seeking_party"] = False
                continue
            # seeking a band => stay by the tavern; else strike out
            seeking = adv.metadata.get("seeking_party", True)
            ctrl.home = tuple(adv.metadata.get("home_spot")) if seeking \
                and adv.metadata.get("home_spot") else None
            try:
                ctrl.take_turn(self.engine, adv)
                driven += 1
            except Exception as e:
                logger.debug(f"Drive adventurer {aid}: {e}")

    def living(self) -> List[str]:
        return [aid for aid, c in self.controllers.items()
                if (self.engine.npc_manager.npcs.get(aid) is not None
                    and self.engine.npc_manager.npcs[aid].is_active())]

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "ids": list(self.controllers.keys())}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self._seeded = d.get("seeded", False)
        # the adventurer Characters ride the normal NPC save; rebuild a
        # brain for each that is still in the world
        self.controllers = {}
        for aid in d.get("ids", []):
            adv = self.engine.npc_manager.npcs.get(aid)
            if adv is None:
                continue
            spot = adv.metadata.get("home_spot") or list(adv.position)
            self.controllers[aid] = self._make_brain(tuple(spot))
