"""Monster tribes as populations (P19.4).

Wild tribes grow strength each night, swarm out to raid the nearest
settlement when they cross a threshold (draining its stores and, near the
player, spilling a coordinated raid party), and are beaten back when the
player cuts their raiders down. Strength persists."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.monster_tribes import MonsterTribeSystem, DEFEAT_HIT


def _recent_text(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.T = self.engine.monster_tribes
        # keep the trolls dormant so tests isolate the goblins
        self.T.strength["crag_trolls"] = 0
        setts = self.engine.production._settlements()
        self.sett = setts[0] if setts else None

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _stand_near(self, loc, dx=3):
        cx, cy = loc.center()
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (cx + dx, cy)
        self.engine.world.map.place_character(self.engine.player, cx + dx, cy)

    def _tribe_raiders(self, tid="gorge_goblins"):
        return [n for n in self.engine.npc_manager.npcs.values()
                if (n.metadata or {}).get("tribe") == tid and n.is_active()]


class TestTribeGrowth(_Base):
    def test_tribes_load(self):
        self.assertGreater(self.T.strength_of("gorge_goblins"), 0)
        self.assertIn("crag_trolls", self.T._tribes())

    def test_nightly_growth(self):
        self.T.strength["gorge_goblins"] = 10
        self.T.run_day()
        self.assertEqual(self.T.strength_of("gorge_goblins"), 15)  # +growth 5

    def test_growth_is_capped(self):
        self.T.strength["gorge_goblins"] = 99
        self.T.run_day()
        self.assertLessEqual(self.T.strength_of("gorge_goblins"), 100)

    def test_below_threshold_no_raid(self):
        self.T.strength["gorge_goblins"] = 10
        self.T.run_day()
        self.assertNotIn("swarm out", _recent_text(self.engine))


class TestTribeRaid(_Base):
    def test_reaching_threshold_raids(self):
        self.T.strength["gorge_goblins"] = 60
        self.T.run_day()
        self.assertIn("Gorge Goblins", _recent_text(self.engine))
        self.assertIn("raid", _recent_text(self.engine))

    def test_a_raid_spends_strength(self):
        self.T.strength["gorge_goblins"] = 60     # -> +5 growth = 65, raid
        self.T.run_day()
        self.assertLess(self.T.strength_of("gorge_goblins"), 65,
                        "the raid committed strength")

    def test_a_raid_drains_the_larder(self):
        if self.sett is None:
            self.skipTest("no settlement")
        self._stand_near(self.sett)
        self.engine.production.store_of(self.sett.name)["bread"] = 40
        self.T.strength["gorge_goblins"] = 70
        self.T.run_day()
        self.assertLess(self.engine.production.store_of(self.sett.name)["bread"],
                        40, "the raiders strip the stores")

    def test_a_near_raid_spills_raiders(self):
        if self.sett is None:
            self.skipTest("no settlement")
        self._stand_near(self.sett)
        self.T.strength["gorge_goblins"] = 80
        self.T.run_day()
        self.assertTrue(self._tribe_raiders(),
                        "a raid you can see spills onto the map")

    def test_a_far_raid_stays_abstract(self):
        if self.sett is None:
            self.skipTest("no settlement")
        # stand very far from every settlement
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (self.engine.world.map.width - 2, 1)
        self.engine.world.map.place_character(
            self.engine.player, self.engine.world.map.width - 2, 1)
        self.T.strength["gorge_goblins"] = 80
        self.T.run_day()
        self.assertFalse(self._tribe_raiders(),
                         "a distant raid is only a report")

    def test_spilled_raiders_coordinate_as_a_pack(self):
        if self.sett is None:
            self.skipTest("no settlement")
        self._stand_near(self.sett)
        self.T.strength["gorge_goblins"] = 80
        self.T.run_day()
        raiders = self._tribe_raiders()
        if len(raiders) < 2:
            self.skipTest("only one raider spilled in this layout")
        self.engine.monster_packs.update()
        leaders = {r.metadata.get("pack_leader_id") for r in raiders}
        self.assertEqual(len(leaders), 1)
        self.assertTrue(all(r.metadata.get("pack_leader_id") for r in raiders))


class TestBeatenBack(_Base):
    def test_slaying_a_raider_beats_the_tribe_back(self):
        self.T.strength["gorge_goblins"] = 50
        raider = self._make_raider()
        s0 = self.T.strength_of("gorge_goblins")
        self.T.on_defeat(raider)
        self.assertEqual(self.T.strength_of("gorge_goblins"), s0 - DEFEAT_HIT)

    def test_an_untagged_kill_does_nothing(self):
        self.T.strength["gorge_goblins"] = 50
        from world.monsters import build_monster
        wild = build_monster("goblin", (5, 5))     # no tribe tag
        self.T.on_defeat(wild)
        self.assertEqual(self.T.strength_of("gorge_goblins"), 50)

    def test_crossing_below_threshold_announces_a_repulse(self):
        spec = self.T._tribes()["gorge_goblins"]
        self.T.strength["gorge_goblins"] = spec["raid_threshold"]
        self.T.on_defeat(self._make_raider())
        self.assertIn("beaten back", _recent_text(self.engine))

    def _make_raider(self):
        from world.monsters import build_monster
        r = build_monster("goblin", (5, 5))
        r.metadata["tribe"] = "gorge_goblins"
        return r


class TestTribePersistence(unittest.TestCase):
    def test_round_trip(self):
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        eng.monster_tribes.strength["gorge_goblins"] = 42
        d = eng.monster_tribes.to_dict()
        restored = MonsterTribeSystem(eng)
        restored.from_dict(d)
        self.assertEqual(restored.strength_of("gorge_goblins"), 42)
        eng.end_game()


if __name__ == "__main__":
    unittest.main()
