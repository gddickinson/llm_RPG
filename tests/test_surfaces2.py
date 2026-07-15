"""Surfaces II tests (P14.2a): blood pools + electrified water."""

import unittest

from engine.game_engine import GameEngine
from engine.surfaces import ELEC_CAP, ELEC_TURNS
from world.monsters import build_monster
from world.world_map import TerrainType


class TestSurfaces2(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.lay = self.engine.surfaces_layer
        self.ox, self.oy = self.wmap.width - 14, self.wmap.height - 10
        for y in range(self.oy - 3, self.oy + 5):
            for x in range(self.ox - 3, self.ox + 10):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.lay.surfaces = {}

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def test_serious_wounds_splash_blood(self):
        foe = build_monster("wolf", (self.ox, self.oy))
        foe.hp = foe.max_hp = 99
        self.engine.npc_manager.add_npc(foe)
        self.wmap.place_character(foe, *foe.position)
        self._put_player(self.ox + 1, self.oy)

        class _R:
            def randint(self, a, b):
                return 15 if b == 20 else b    # hit hard

            def random(self):
                return 0.9

        self.engine.combat_system.rng = _R()
        self.engine.combat_system._resolve(self.player, foe)
        self.assertEqual(self.lay.kind_at(self.ox, self.oy), "blood",
                         "the wound painted the ground")

    def test_shock_electrifies_connected_water(self):
        # a puddle chain: water surfaces bridged by a blood pool
        for i in range(3):
            self.lay.pour(self.ox + i, self.oy, "water")
        self.lay.splash_blood(self.ox + 3, self.oy)
        self.lay.pour(self.ox + 4, self.oy, "water")
        charged = self.lay.electrify(self.ox, self.oy)
        self.assertEqual(charged, 5, "blood conducts the charge")
        for i in range(5):
            self.assertEqual(
                self.lay.kind_at(self.ox + i, self.oy),
                "electrified")

    def test_dry_ground_does_not_conduct(self):
        self.assertEqual(self.lay.electrify(self.ox, self.oy), 0)

    def test_the_charge_zaps_and_maims_the_player(self):
        self.lay.pour(self.ox, self.oy, "water")
        self._put_player(self.ox, self.oy)
        self.lay.electrify(self.ox, self.oy)
        self.player.hp = 2
        self.lay.tick()
        self.assertEqual(self.player.hp, 1,
                         "current maims; the story kills")

    def test_the_charge_fades_back_to_water(self):
        self.lay.pour(self.ox, self.oy, "water")
        self.lay.electrify(self.ox, self.oy)
        for _ in range(ELEC_TURNS):
            self.lay.tick()
        self.assertEqual(self.lay.kind_at(self.ox, self.oy), "water",
                         "the water remains when the charge fades")

    def test_terrain_water_conducts_too(self):
        for i in range(4):
            self.wmap.terrain[self.oy][self.ox + i] = \
                TerrainType.WATER
        charged = self.lay.electrify(self.ox, self.oy)
        self.assertGreaterEqual(charged, 4,
                                "the river carries the lightning")

    def test_the_cap_holds(self):
        for i in range(ELEC_CAP + 10):
            self.lay.pour(self.ox - 3 + (i % 12), self.oy - 3 + i // 12,
                          "water")
        charged = self.lay.electrify(self.ox - 3, self.oy - 3)
        self.assertLessEqual(charged, ELEC_CAP)

    def test_fire_never_spreads_into_blood(self):
        self.lay.splash_blood(self.ox + 1, self.oy)
        self.lay.ignite(self.ox, self.oy, intensity=2)
        self.lay.rng.random = lambda: 0.0    # spread always fires
        for _ in range(4):
            self.lay.tick()
        self.assertNotEqual(self.lay.kind_at(self.ox + 1, self.oy),
                            "fire", "blood does not burn")

    def test_shock_spell_completes_the_combo(self):
        foe = build_monster("wolf", (self.ox, self.oy))
        foe.hp = foe.max_hp = 99
        self.engine.npc_manager.add_npc(foe)
        self.wmap.place_character(foe, *foe.position)
        self.lay.pour(self.ox, self.oy, "water")
        self._put_player(self.ox + 1, self.oy)
        self.player.metadata["spells_known"] = ["shock"]
        self.player.metadata["mana"] = 20
        self.player.metadata["max_mana"] = 20
        self.engine.cast_spell("shock", foe.name)
        self.assertEqual(self.lay.kind_at(self.ox, self.oy),
                         "electrified",
                         "lure them into the puddle, then shock it")


if __name__ == "__main__":
    unittest.main()
