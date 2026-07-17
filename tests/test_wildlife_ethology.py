"""LIVING_WORLD Area B — wildlife ETHOLOGY: day/night rest (B1), grazing + thirst
drives (B2), and herd cohesion (B3). Animals live a real day instead of the old
50/50 random wander. (George: should animals hunt/flee/sleep?)"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_NO_ADVENTURERS", "1")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_eth_"))

import unittest

from engine.game_engine import GameEngine
from world import wildlife
from world import wildlife_ethology as eth
from world.world_map import TerrainType


class TestRosterProps(unittest.TestCase):
    def test_active_and_herd_flags(self):
        self.assertEqual(wildlife.ROSTER["deer"]["active"], "day")
        self.assertEqual(wildlife.ROSTER["fox"]["active"], "night")
        self.assertTrue(wildlife.ROSTER["deer"]["herd"])
        self.assertFalse(wildlife.ROSTER["fox"]["herd"])

    def test_build_carries_them(self):
        a = wildlife.build_wildlife("deer", (5, 5))
        self.assertEqual(a.metadata["active"], "day")
        self.assertTrue(a.metadata["herd"])


class TestRestTime(unittest.TestCase):
    def test_diurnal_rests_at_night_active_by_day(self):
        self.assertTrue(eth.is_rest_time({"active": "day"}, night=True))
        self.assertFalse(eth.is_rest_time({"active": "day"}, night=False))

    def test_nocturnal_rests_by_day_active_at_night(self):
        self.assertTrue(eth.is_rest_time({"active": "night"}, night=False))
        self.assertFalse(eth.is_rest_time({"active": "night"}, night=True))


class TestEthology(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.sys = self.engine.wildlife
        self.wmap = self.engine.world.map
        for yy in range(15, 30):
            for xx in range(15, 33):
                self.wmap.terrain[yy][xx] = TerrainType.GRASS
        self.engine.player.position = (0, 0)   # keep the player far off

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _animal(self, species, pos):
        a = wildlife.build_wildlife(species, pos)
        self.engine.npc_manager.add_npc(a)
        try:
            self.wmap.remove_character(a)
        except Exception:
            pass
        a.position = pos
        self.wmap.place_character(a, *pos)
        return a

    def test_b1_diurnal_beds_down_at_night(self):
        deer = self._animal("deer", (20, 20))
        eth.live(self.sys, deer, night=True)
        self.assertTrue(deer.metadata.get("asleep"))
        self.assertEqual(deer.metadata.get("_bubble"), "sleep")

    def test_b1_wakes_by_day(self):
        deer = self._animal("deer", (20, 20))
        deer.metadata["asleep"] = True
        eth.live(self.sys, deer, night=False)
        self.assertFalse(deer.metadata.get("asleep"))

    def test_b2_hungry_grazer_feeds_on_grass(self):
        deer = self._animal("deer", (20, 20))     # standing on grass
        deer.metadata["hunger"] = 9
        eth.live(self.sys, deer, night=False)
        self.assertEqual(deer.metadata.get("hunger"), 0, "grazed → sated")
        self.assertEqual(deer.metadata.get("_emote"), "stoop")

    def test_b2_thirsty_animal_drinks_at_water(self):
        self.wmap.terrain[20][22] = TerrainType.WATER
        deer = self._animal("deer", (21, 20))     # adjacent to the water tile
        deer.metadata["thirst"] = 20
        self.assertTrue(eth._seek_water(self.sys, deer))
        self.assertEqual(deer.metadata.get("thirst"), 0)

    def test_b2_thirsty_animal_walks_toward_water(self):
        self.wmap.terrain[20][28] = TerrainType.WATER
        deer = self._animal("deer", (22, 20))
        deer.metadata["thirst"] = 20
        before = deer.position
        eth._seek_water(self.sys, deer)
        self.assertGreater(before[0], 22 - 1)     # sanity
        self.assertNotEqual(deer.position, before, "steps toward the water")

    def test_b3_herd_cohesion_pulls_toward_the_group(self):
        for p in [(25, 20), (25, 21), (25, 22)]:
            self._animal("deer", p)
        loner = self._animal("deer", (30, 21))
        vx, vy = eth._herd_vector(self.sys, loner)
        self.assertEqual(vx, -1, "cohesion pulls west toward the herd")

    def test_b3_solitary_species_has_no_cohesion(self):
        fox = self._animal("fox", (20, 20))
        self.assertEqual(eth._herd_vector(self.sys, fox), (0, 0))

    def test_b4_wolf_is_a_pack_predator(self):
        self.assertIn("wolf", wildlife.ROSTER)
        w = self._animal("wolf", (20, 20))
        self.assertIn("deer", w.metadata["preys_on"])
        self.assertTrue(w.metadata["herd"], "wolves run as a pack")
        self.assertEqual(w.metadata["active"], "night")

    def test_b4_cornered_boar_charges(self):
        # wall a boar in on all sides but the player's, so it can't bolt
        for (x, y) in [(9, 11), (11, 11), (10, 12), (9, 10), (11, 10),
                       (9, 12), (11, 12)]:
            self.wmap.terrain[y][x] = TerrainType.MOUNTAIN
        self.wmap.terrain[11][10] = TerrainType.SWAMP
        boar = self._animal("boar", (10, 11))
        self.engine.player.position = (10, 10)
        self.assertFalse(self.sys._can_flee(boar, (10, 10)), "cornered")
        hp0 = self.engine.player.hp
        self.sys._act(boar, (10, 10), night=False)
        self.assertLess(self.engine.player.hp, hp0, "the boar gores the player")

    def test_b4_charge_never_kills(self):
        boar = self._animal("boar", (10, 11))
        boar.metadata["charge_damage"] = 999
        self.engine.player.hp = 3
        self.engine.player.position = (10, 10)
        self.sys._charge(boar, (10, 10))
        self.assertEqual(self.engine.player.hp, 1, "a scare, floored at 1 HP")

    def test_b4_charge_cooldown(self):
        boar = self._animal("boar", (10, 11))
        self.engine.player.position = (10, 10)
        self.engine.player.hp = 30
        self.sys._charge(boar, (10, 10))
        hp1 = self.engine.player.hp
        self.sys._charge(boar, (10, 10))       # immediate re-charge is on cooldown
        self.assertEqual(self.engine.player.hp, hp1)

    def test_b4_fed_predator_resets_hunger(self):
        fox = self._animal("fox", (40, 40))
        fox.metadata["pred_hunger"] = 5
        fox.metadata["fed"] = True
        self.sys.run_day()
        self.assertEqual(fox.metadata.get("pred_hunger"), 0)

    def test_survival_overrides_rest(self):
        # a resting deer startles awake + flees when the player closes in
        deer = self._animal("deer", (20, 20))
        deer.metadata["asleep"] = True
        self.engine.player.position = (21, 20)     # inside timid range
        before = deer.position
        self.sys._act(deer, self.engine.player.position, night=True)
        self.assertFalse(deer.metadata.get("asleep"), "startled awake")
        self.assertNotEqual(deer.position, before, "flees the player")

    def test_c5_predator_monster_hunts_wildlife(self):
        from world.monsters import build_monster
        # a wolf MONSTER preys on deer; keep the player off to the side so the
        # wolf isn't busy fighting the hero
        self.engine.player.position = (16, 25)
        deer = self._animal("deer", (20, 20))
        wolf = build_monster("wolf", (20, 24))
        self.assertIn("deer", wolf.metadata["preys_on"])
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.remove_character(wolf)
        wolf.position = (20, 24)
        self.wmap.place_character(wolf, 20, 24)
        killed = False
        for _ in range(12):
            self.engine.turn_counter += 1
            self.sys.run_turn()
            if not deer.is_alive() or deer.id not in self.engine.npc_manager.npcs:
                killed = True
                break
        self.assertTrue(killed, "the wolf runs down the deer")

    def test_c5_non_predator_monster_ignores_wildlife(self):
        from world.monsters import build_monster
        from world import wildlife_ethology as eth
        self.engine.player.position = (16, 25)
        deer = self._animal("deer", (20, 20))
        goblin = build_monster("goblin", (20, 22))   # no preys_on
        self.engine.npc_manager.add_npc(goblin)
        self.wmap.remove_character(goblin)
        goblin.position = (20, 22)
        self.wmap.place_character(goblin, 20, 22)
        before = goblin.position
        eth.monster_predation(self.sys, self.engine.player.position)
        self.assertEqual(goblin.position, before, "a goblin doesn't hunt deer")
        self.assertTrue(deer.is_alive())


if __name__ == "__main__":
    unittest.main()
