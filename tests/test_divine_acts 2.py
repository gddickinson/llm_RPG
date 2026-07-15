"""The active pantheon (P20.4) — gods that meddle.

Each night a god weighs how its domain fares (tempered by your favor) and
sends a BOON to its favoured faction when the domain thrives or WRATH when
it's neglected; opposing gods contend into a wild-weather storm."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_div_"))

import unittest

from engine.game_engine import GameEngine


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.D = self.engine.divine_acts
        self.ft = self.engine.faction_ticker
        self.cfg = self.D._cfg()
        self.solara = self.cfg["gods"]["solara"]

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestJudge(_Base):
    def test_a_thriving_domain_earns_a_boon(self):
        self.ft.state["villagers"]["stores"] = 80
        line = self.D._judge("solara", self.solara, self.ft, {}, self.cfg)
        self.assertIn("harvest", line)
        self.assertGreater(self.ft.state["villagers"]["stores"], 80)

    def test_a_neglected_domain_earns_wrath(self):
        self.ft.state["villagers"]["stores"] = 20
        line = self.D._judge("solara", self.solara, self.ft, {}, self.cfg)
        self.assertIn("blight", line)
        self.assertLess(self.ft.state["villagers"]["stores"], 20)

    def test_a_middling_domain_is_left_alone(self):
        self.ft.state["villagers"]["stores"] = 45
        self.assertIsNone(
            self.D._judge("solara", self.solara, self.ft, {}, self.cfg))

    def test_favor_tips_a_god_to_act(self):
        self.ft.state["merchants"]["stores"] = 50
        grimble = self.cfg["gods"]["grimble"]
        self.assertIsNone(
            self.D._judge("grimble", grimble, self.ft, {}, self.cfg))
        self.ft.state["merchants"]["stores"] = 50
        self.assertIsNotNone(
            self.D._judge("grimble", grimble, self.ft,
                          {"grimble": 20}, self.cfg),
            "a favoured god acts where a neglected one wouldn't")

    def test_effects_are_clamped(self):
        self.ft.state["villagers"]["stores"] = 98
        self.D._judge("solara", self.solara, self.ft, {}, self.cfg)
        self.assertLessEqual(self.ft.state["villagers"]["stores"], 100)


class TestContention(_Base):
    def test_opposing_gods_build_tension_to_a_storm(self):
        self.engine.player.metadata["divine_tension"] = \
            self.cfg["tension_at"] - 1
        beats = self.D._contend(["morrik", "veyra"],
                                self.cfg["gods"], self.cfg)
        self.assertTrue(any("contend" in b for b in beats))
        self.assertEqual(self.engine.player.metadata["divine_tension"], 0,
                         "the storm resets the tension")

    def test_non_opposing_acts_raise_no_tension(self):
        beats = self.D._contend(["solara", "grimble"],
                                self.cfg["gods"], self.cfg)
        self.assertEqual(beats, [])

    def test_tension_persists_on_metadata(self):
        self.engine.player.metadata["divine_tension"] = 0
        self.D._contend(["morrik", "veyra"], self.cfg["gods"], self.cfg)
        self.assertGreater(
            self.engine.player.metadata.get("divine_tension", 0), 0)


class TestRunDay(_Base):
    def test_run_day_announces_divine_beats(self):
        self.ft.state["villagers"]["stores"] = 85
        self.ft.state["brigands"]["strength"] = 85
        self.D.rng.seed(1)
        saw = False
        for _ in range(12):
            if self.D.run_day():
                saw = True
        self.assertTrue(saw, "the gods act over the nights")
        self.assertTrue(any(g in _recent(self.engine)
                            for g in ("Solara", "Morrik", "Grimble",
                                      "Veyra", "Pale Lady", "gods contend")))


if __name__ == "__main__":
    unittest.main()
