"""M2 — world-altering spells: a spell's `world_effect` reshapes the world through
the M0 worldcraft layer (terraform, build, destroy) + surfaces/tile_damage.

A pure world spell targets the tile the caster faces; a damage spell that carries
a world_effect applies it at the struck tile. Overworld only.
"""

import unittest

from engine.game_engine import GameEngine
from engine import worldcraft as wc, spell_world
from world.world_map import TerrainType
from ui.character_creator import CharacterSpec
from characters.character_types import CharacterClass, CharacterRace


def _mage(cls=CharacterClass.WIZARD):
    return CharacterSpec(name="Mage", race=CharacterRace.HUMAN,
                         character_class=cls,
                         stats={"strength": 8, "dexterity": 10,
                                "constitution": 10, "intelligence": 18,
                                "wisdom": 16, "charisma": 10})


class _Base(unittest.TestCase):
    CLASS = CharacterClass.WIZARD

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False,
                                 player_spec=_mage(self.CLASS))
        self.engine.start_game()
        self.p = self.engine.player
        self.p.level = 12
        from engine.spells import learn_new_spells
        learn_new_spells(self.p)
        self.p.metadata["mana"] = 99
        self.p.metadata["max_mana"] = 99
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _two_grass(self):
        for y in range(self.wmap.height - 1):
            for x in range(self.wmap.width):
                a, b = (x, y), (x, y + 1)
                if all(self.wmap.get_terrain_at(*t) == TerrainType.GRASS
                       and not wc.protected(self.engine, *t)
                       and t not in self.wmap.characters for t in (a, b)):
                    return a, b
        self.skipTest("no grass pair")

    def _face_south_at(self, pos):
        self.wmap.remove_character(self.p)
        self.p.position = pos
        self.wmap.place_character(self.p, *pos)
        self.p.metadata.setdefault("_anim", {})["facing"] = (0, 1)


class TestResolveTile(unittest.TestCase):
    def test_faces_the_target(self):
        class C:
            position = (5, 5)
            metadata = {"_anim": {"facing": (1, 0)}}
            id = "c"
        # facing east → one tile east
        self.assertEqual(spell_world.resolve_tile(_Eng(), C()), (6, 5))


class _Eng:
    class player:
        id = "player"


class TestWorldSpells(_Base):
    def test_wall_of_stone_builds(self):
        stand, tgt = self._two_grass()
        self._face_south_at(stand)
        msg = self.engine.cast_spell("wall_of_stone")
        self.assertIn("reshape", msg.lower())
        self.assertEqual(self.wmap.get_terrain_at(*tgt), TerrainType.BUILDING)

    def test_disintegrate_destroys_a_wall(self):
        stand, tgt = self._two_grass()
        self._face_south_at(stand)
        self.engine.cast_spell("wall_of_stone")           # raise it
        self.assertEqual(self.wmap.get_terrain_at(*tgt), TerrainType.BUILDING)
        self._face_south_at(stand)
        self.engine.cast_spell("disintegrate")            # blow it up
        self.assertEqual(self.wmap.get_terrain_at(*tgt), TerrainType.RUBBLE)

    def test_costs_mana(self):
        stand, _ = self._two_grass()
        self._face_south_at(stand)
        before = self.p.metadata["mana"]
        self.engine.cast_spell("wall_of_stone")
        self.assertLess(self.p.metadata["mana"], before)

    def test_pure_world_spell_needs_open_sky(self):
        # simulate being inside: an active zone blocks terrain magic
        class Zone:
            name = "Some Cellar"
        self.engine.current_interior = Zone()
        try:
            msg = self.engine.cast_spell("wall_of_stone")
            self.assertIn("open sky", msg.lower())
        finally:
            self.engine.current_interior = None

    def test_cannot_reshape_protected_ground(self):
        # a protected GRASS tile (inside a typed POI) resists the build spell
        for loc in self.engine.world.locations:
            if not (loc.properties or {}).get("type"):
                continue
            for yy in range(loc.y, loc.y + loc.height):
                for xx in range(loc.x, loc.x + loc.width):
                    tgt, stand = (xx, yy), (xx, yy - 1)
                    if (stand[1] >= 0
                            and self.wmap.get_terrain_at(*tgt) == TerrainType.GRASS
                            and stand not in self.wmap.characters
                            and self.wmap.get_terrain_at(*stand)
                            != TerrainType.BUILDING):
                        self._face_south_at(stand)
                        self.engine.cast_spell("wall_of_stone")
                        self.assertEqual(self.wmap.get_terrain_at(*tgt),
                                         TerrainType.GRASS,
                                         "protected ground resists the spell")
                        return
        self.skipTest("no protected grass tile with a free approach")


class TestDruidWorldSpells(_Base):
    CLASS = CharacterClass.DRUID

    def test_plant_growth_grows_forest(self):
        stand, tgt = self._two_grass()
        self._face_south_at(stand)
        self.engine.cast_spell("plant_growth")
        self.assertEqual(self.wmap.get_terrain_at(*tgt), TerrainType.FOREST)

    def test_conjure_water(self):
        stand, tgt = self._two_grass()
        self._face_south_at(stand)
        self.engine.cast_spell("conjure_water")
        self.assertEqual(self.wmap.get_terrain_at(*tgt), TerrainType.WATER)


class TestDamagePlusWorld(_Base):
    def test_firestorm_scorches_the_ground(self):
        # firestorm razes + ignites the struck tile; verify it lays a fire surface
        stand, tgt = self._two_grass()
        self._face_south_at(stand)
        # aim: put a dummy foe on the target so the damage spell resolves there
        foe = self.engine.npc_manager.create_random_npc("goblin")
        from characters.character_types import CharacterClass as CC
        foe.character_class = CC.MONSTER
        foe.position = tgt
        self.wmap.place_character(foe, *tgt)
        self.engine.player_target_id = foe.id
        self.engine.cast_spell("firestorm")
        lit = self.engine.surfaces_layer.surfaces.get(tuple(tgt))
        self.assertTrue(lit and lit.get("kind") == "fire",
                        "firestorm should ignite the struck ground")


class TestAmbientCasters(unittest.TestCase):
    """George: NPCs + away-heroes should cast world-altering spells too."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _cluster(self):
        for y in range(1, self.wmap.height - 1):
            for x in range(1, self.wmap.width - 1):
                c = (x, y)
                nbrs = [(x + dx, y + dy)
                        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))]
                if all(self.wmap.get_terrain_at(*t) == TerrainType.GRASS
                       and not wc.protected(self.engine, *t)
                       for t in [c] + nbrs) and c not in self.wmap.characters:
                    return c, nbrs
        self.skipTest("no grass cluster")

    def _caster(self, cls):
        npc = self.engine.npc_manager.create_random_npc("villager")
        npc.character_class = cls
        npc.metadata = {}
        return npc

    def test_npc_druid_grows_a_forest(self):
        npc = self._caster(CharacterClass.DRUID)
        spot, nbrs = self._cluster()
        npc.position = spot
        self.wmap.place_character(npc, *spot)
        msg = spell_world.ambient_shape(self.engine, npc)
        self.assertIsNotNone(msg)
        self.assertTrue(any(self.wmap.get_terrain_at(*t) == TerrainType.FOREST
                            for t in nbrs), "a druid grows a woodland")

    def test_npc_wizard_raises_a_wall(self):
        npc = self._caster(CharacterClass.WIZARD)
        spot, nbrs = self._cluster()
        npc.position = spot
        self.wmap.place_character(npc, *spot)
        spell_world.ambient_shape(self.engine, npc)
        self.assertTrue(any(self.wmap.get_terrain_at(*t) == TerrainType.BUILDING
                            for t in nbrs))

    def test_innate_grant_for_npc(self):
        npc = self._caster(CharacterClass.DRUID)
        spot, _ = self._cluster()
        npc.position = spot
        self.wmap.place_character(npc, *spot)
        self.assertEqual(npc.metadata.get("spells_known", []), [])
        spell_world.ambient_shape(self.engine, npc)
        # cast granted the spell innately
        self.assertTrue(npc.metadata.get("spells_known"),
                        "an NPC gains the world spell it wields")

    def test_non_caster_does_nothing(self):
        npc = self._caster(CharacterClass.WARRIOR)
        spot, nbrs = self._cluster()
        npc.position = spot
        self.wmap.place_character(npc, *spot)
        self.assertIsNone(spell_world.ambient_shape(self.engine, npc))
        self.assertTrue(all(self.wmap.get_terrain_at(*t) == TerrainType.GRASS
                            for t in nbrs))

    def test_caster_in_a_zone_is_blocked(self):
        npc = self._caster(CharacterClass.DRUID)
        npc.metadata["zone"] = "Some Crypt"       # a dungeon native
        spot, _ = self._cluster()
        npc.position = spot
        self.wmap.place_character(npc, *spot)
        self.assertIsNone(spell_world.ambient_shape(self.engine, npc))

    def test_ambient_run_is_safe(self):
        from engine import ambient_magic
        ambient_magic.run(self.engine)          # never raises


if __name__ == "__main__":
    unittest.main()
