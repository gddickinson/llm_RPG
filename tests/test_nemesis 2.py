"""The Nemesis system (P19.6).

An elite that survives a brush with death becomes a named nemesis: it
flees, rises in power and title, returns nights later to hunt the player,
and — when its luck finally runs out — passes into the Legendarium."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_nem_"))

import unittest

from engine.game_engine import GameEngine
from engine.nemesis import NemesisSystem
from world.monsters import build_monster
from world.world_map import TerrainType


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.N = self.engine.nemesis
        for yy in range(4, 30):
            for xx in range(4, 30):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (15, 15)
        self.engine.world.map.place_character(self.engine.player, 15, 15)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _tagged(self, nid, pos=(16, 15), **meta):
        m = build_monster("bandit", pos)
        m.metadata["nemesis_id"] = nid
        m.metadata["elite"] = True
        m.metadata.update(meta)
        self.engine.npc_manager.add_npc(m)
        self.engine.world.map.place_character(m, *pos)
        return m

    def _rec(self, escapes_left=2, power=1):
        rec = {"id": "nem_T_1", "name": "Grukk", "title": "the Fierce",
               "template": "bandit", "power": power,
               "escapes_left": escapes_left, "level": 8, "npc_id": None}
        self.N.nemeses["nem_T_1"] = rec
        return rec


class TestDeathsDoor(_Base):
    def test_ordinary_foe_dies_normally(self):
        w = build_monster("wolf", (17, 15))     # no elite / nemesis tag
        self.assertIsNone(self.N.intercept_death(w))
        self.assertEqual(self.N.nemeses, {})

    def test_a_nemesis_escapes_and_rises(self):
        rec = self._rec(escapes_left=2, power=1)
        m = self._tagged("nem_T_1")
        msg = self.N.intercept_death(m)
        self.assertIsNotNone(msg)
        self.assertIn("escapes", msg)
        self.assertEqual(rec["power"], 2, "it rose in power")
        self.assertEqual(rec["escapes_left"], 1)
        self.assertIsNone(self.engine.npc_manager.get_npc(m.id),
                          "it left the field")

    def test_a_rising_nemesis_earns_a_grander_title(self):
        rec = self._rec(escapes_left=2, power=1)
        t0 = rec["title"]
        self.N.intercept_death(self._tagged("nem_T_1"))
        self.assertNotEqual(rec["title"], t0)

    def test_out_of_escapes_it_dies_and_becomes_legend(self):
        self._rec(escapes_left=0, power=3)
        m = self._tagged("nem_T_1")
        self.assertIsNone(self.N.intercept_death(m),
                          "no escape left — it dies")
        self.assertNotIn("nem_T_1", self.N.nemeses)
        self.assertIn("falls at last", _recent(self.engine))

    def test_an_elite_can_be_born_a_nemesis(self):
        # force the birth roll by seeding low
        self.N.rng.seed(1)
        m = build_monster("bandit", (16, 15))
        m.metadata["elite"] = True
        self.engine.npc_manager.add_npc(m)
        self.engine.world.map.place_character(m, 16, 15)
        results = []
        for seed in range(8):        # some seed births a nemesis
            self.N.rng.seed(seed)
            mm = build_monster("bandit", (18, 15))
            mm.id = f"enc_bandit_born{seed}"
            mm.metadata["elite"] = True
            self.engine.npc_manager.add_npc(mm)
            r = self.N.intercept_death(mm)
            results.append(r is not None)
        self.assertTrue(any(results), "an elite sometimes escapes as a nemesis")


class TestReturn(_Base):
    def test_a_nemesis_returns_scaled(self):
        rec = self._rec(escapes_left=1, power=3)
        ok = self.N._summon(rec, self.N._cfg())
        self.assertTrue(ok)
        npc = self.engine.npc_manager.get_npc(rec["npc_id"])
        self.assertIsNotNone(npc)
        self.assertEqual(npc.metadata.get("nemesis_id"), rec["id"])
        self.assertTrue(npc.metadata.get("elite"))
        self.assertGreater(npc.level, rec["level"], "it comes back stronger")
        self.assertIn("Grukk", npc.name)
        self.assertIn("returns to hunt", _recent(self.engine))

    def test_on_field_tracks_liveness(self):
        rec = self._rec()
        self.assertFalse(self.N._on_field(rec))
        self.N._summon(rec, self.N._cfg())
        self.assertTrue(self.N._on_field(rec))

    def test_run_day_skips_an_on_field_nemesis(self):
        rec = self._rec()
        self.N._summon(rec, self.N._cfg())
        npc_id = rec["npc_id"]
        self.N.run_day()
        self.assertEqual(rec["npc_id"], npc_id, "no duplicate while on field")


class TestNemesisPersistence(unittest.TestCase):
    def test_round_trip(self):
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        eng.nemesis.nemeses["nem_X"] = {"id": "nem_X", "name": "Skarn",
                                        "title": "the Dreaded", "power": 4,
                                        "escapes_left": 1, "template": "bandit",
                                        "level": 10, "npc_id": None}
        d = eng.nemesis.to_dict()
        restored = NemesisSystem(eng)
        restored.from_dict(d)
        self.assertIn("nem_X", restored.nemeses)
        self.assertEqual(restored.nemeses["nem_X"]["title"], "the Dreaded")
        eng.end_game()


class TestCombatIntegration(_Base):
    def test_killing_a_tagged_elite_makes_it_escape(self):
        import random
        self._rec(escapes_left=2, power=1)
        m = self._tagged("nem_T_1", pos=(16, 15))
        m.hp = 1
        # a nemesis with escapes left slips away from a killing blow; seed
        # the combat rng and swing until one lands (deterministic)
        self.engine.combat_system.rng = random.Random(0)
        for _ in range(30):
            if self.engine.npc_manager.get_npc(m.id) is None:
                break
            self.engine.combat_system.player_attack(m.name)
        self.assertIsNone(self.engine.npc_manager.get_npc(m.id),
                          "the nemesis escaped rather than died")
        self.assertIn("nem_T_1", self.N.nemeses, "and lives to return")


if __name__ == "__main__":
    unittest.main()
