"""The endgame curve — elites & party-scaled packs (P19.5).

A party that out-levels the wilderness draws elite variants (Dire,
Champion, Ancient) and warbands, so the wild scales to a high-level party.
Low-level play is untouched."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine import elites
from world.monsters import build_monster


class _Rng:
    """A stub whose .random() is fixed — 0.0 always passes a chance,
    1.0 always fails it."""
    def __init__(self, val):
        self.val = val

    def random(self):
        return self.val


class TestPartyLevel(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_solo_party_level_is_the_hero(self):
        self.engine.player.level = 7
        self.assertEqual(elites.party_level(self.engine), 7)

    def test_a_fuller_party_warrants_tougher_foes(self):
        self.engine.player.level = 7
        ally = build_monster("wolf", (5, 5))
        ally.id = "ally1"
        ally.level = 4
        self.engine.npc_manager.add_npc(ally)
        self.engine.companion_manager.party.append(ally.id)
        # strongest is the hero (7), plus one for party size
        self.assertEqual(elites.party_level(self.engine), 8)


class TestPromotion(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_no_gap_no_promotion(self):
        self.engine.player.level = 1
        w = build_monster("wolf", (5, 5))
        self.assertFalse(elites.maybe_promote(self.engine, w, _Rng(0.0)))
        self.assertEqual(w.name, "Wolf")
        self.assertIsNone(w.metadata.get("elite"))

    def test_a_high_party_promotes(self):
        self.engine.player.level = 20
        w = build_monster("wolf", (5, 5))
        base_hp = w.max_hp
        self.assertTrue(elites.maybe_promote(self.engine, w, _Rng(0.0)))
        self.assertTrue(w.metadata.get("elite"))
        self.assertGreater(w.max_hp, base_hp)
        self.assertGreater(w.level, 1)
        self.assertNotEqual(w.name, "Wolf")       # retitled

    def test_the_chance_can_decline(self):
        self.engine.player.level = 20
        w = build_monster("wolf", (5, 5))
        self.assertFalse(elites.maybe_promote(self.engine, w, _Rng(1.0)))
        self.assertEqual(w.name, "Wolf")

    def test_best_tier_grows_with_the_gap(self):
        cfg = elites._config()
        small = elites._best_tier(3, cfg)          # Dire tier
        big = elites._best_tier(15, cfg)           # Ancient tier
        self.assertIsNotNone(small)
        self.assertIsNotNone(big)
        self.assertGreater(big["hp_mult"], small["hp_mult"])

    def test_apply_tier_buffs(self):
        w = build_monster("wolf", (5, 5))
        elites.apply_tier(w, {"title": "Ancient {name}", "hp_mult": 3.0,
                              "level_bonus": 9, "str_bonus": 6})
        self.assertEqual(w.name, "Ancient Wolf")
        self.assertEqual(w.max_hp, 30)
        self.assertEqual(w.hp, 30)
        self.assertTrue(w.metadata.get("elite"))


class TestWarband(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_no_gap_no_warband(self):
        self.engine.player.level = 1
        self.assertEqual(elites.extra_pack(self.engine, 1, _Rng(0.0)), 0)

    def test_a_high_party_draws_a_warband(self):
        self.engine.player.level = 20
        n = elites.extra_pack(self.engine, 1, _Rng(0.0))
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, 3, "the warband is capped")

    def test_a_declined_roll_gives_no_warband(self):
        self.engine.player.level = 20
        self.assertEqual(elites.extra_pack(self.engine, 1, _Rng(1.0)), 0)


class TestEncounterIntegration(unittest.TestCase):
    def test_a_high_party_meets_elites_or_warbands(self):
        from world.world_map import TerrainType
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        engine.player.level = 20
        # a clear grass field, hero in the middle
        for yy in range(4, 40):
            for xx in range(4, 40):
                engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        engine.world.map.remove_character(engine.player)
        engine.player.position = (20, 20)
        engine.world.map.place_character(engine.player, 20, 20)
        em = engine.encounter_manager
        em.rng.seed(3)
        elite_or_pack = 0
        for _ in range(120):
            em._cooldown_until = 0
            engine.turn_counter += 30
            msg = em.maybe_spawn()
            if msg and ("fearsome" in msg or "pack of" in msg):
                elite_or_pack += 1
        self.assertGreater(elite_or_pack, 0,
                           "a level-20 party should meet elites/warbands")
        engine.end_game()


if __name__ == "__main__":
    unittest.main()
