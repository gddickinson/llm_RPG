"""Faction agendas & diplomacy (P20.3) — wars with aims, not dice.

Each faction holds an agenda it pursues (nudging its strength/stores) and a
web of relations that drift toward war between enemies and alliance between
friends; agendas shift on a faction's fortunes. Heuristic; persists."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_fa_"))

import unittest

from engine.game_engine import GameEngine
from engine.faction_agendas import FactionAgendas, _key


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.FA = self.engine.faction_agendas
        self.FA._ensure()
        self.cfg = self.FA._cfg()
        self.ft = self.engine.faction_ticker

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestSetup(_Base):
    def test_initial_agendas(self):
        self.assertEqual(self.FA.agenda_of("brigands"), "expand")
        self.assertEqual(self.FA.agenda_of("merchants"), "hoard")

    def test_enemies_start_hostile(self):
        self.assertLess(self.FA.relation("brigands", "guards"), 0)

    def test_friends_start_warm(self):
        self.assertGreater(self.FA.relation("villagers", "guards"), 0)


class TestPursue(_Base):
    def test_an_agenda_nudges_the_state(self):
        self.ft.state["brigands"]["strength"] = 40
        self.FA._pursue(self.cfg, self.ft)
        self.assertGreater(self.ft.state["brigands"]["strength"], 40,
                           "expanding brigands grow stronger")

    def test_hoarders_pile_stores(self):
        self.ft.state["merchants"]["stores"] = 40
        self.FA._pursue(self.cfg, self.ft)
        self.assertGreater(self.ft.state["merchants"]["stores"], 40)


class TestDiplomacy(_Base):
    def test_enemies_drift_to_war(self):
        self.FA.relations[_key("brigands", "guards")] = -59
        beats = self.FA._diplomacy(self.cfg)
        self.assertTrue(self.FA.at_war("brigands", "guards"))
        self.assertTrue(any("at war" in b for b in beats))

    def test_friends_drift_to_alliance(self):
        self.FA.relations[_key("villagers", "guards")] = 59
        beats = self.FA._diplomacy(self.cfg)
        self.assertIn(f"ally:{_key('villagers', 'guards')}", self.FA.latched)
        self.assertTrue(any("alliance" in b for b in beats))

    def test_war_is_declared_once(self):
        self.FA.relations[_key("brigands", "guards")] = -80
        first = self.FA._diplomacy(self.cfg)
        second = self.FA._diplomacy(self.cfg)
        self.assertTrue(any("at war" in b for b in first))
        self.assertFalse(any("at war" in b for b in second),
                         "no repeat war declaration")

    def test_run_day_announces_a_realm_beat(self):
        self.FA.relations[_key("brigands", "guards")] = -80
        self.FA.run_day()
        self.assertIn("war", _recent(self.engine))


class TestAgendaShift(_Base):
    def test_strength_turns_to_dominate(self):
        self.ft.state["brigands"]["strength"] = 90
        beat = self.FA._maybe_shift("brigands", self.ft, self.cfg)
        self.assertEqual(self.FA.agenda_of("brigands"), "dominate")
        self.assertIn("dominate", beat)

    def test_a_beaten_faction_recovers(self):
        self.ft.state["brigands"]["strength"] = 10
        beat = self.FA._maybe_shift("brigands", self.ft, self.cfg)
        self.assertEqual(self.FA.agenda_of("brigands"), "recover")
        self.assertIn("wounds", beat)

    def test_recovery_returns_to_nature(self):
        self.FA.agendas["brigands"] = "recover"
        self.ft.state["brigands"]["strength"] = 60
        self.FA._maybe_shift("brigands", self.ft, self.cfg)
        self.assertEqual(self.FA.agenda_of("brigands"), "expand",
                         "recovered, it resumes its nature")


class TestPersistence(unittest.TestCase):
    def test_round_trip(self):
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        fa = eng.faction_agendas
        fa._ensure()
        fa.agendas["brigands"] = "dominate"
        fa.latched.add("war:brigands|guards")
        d = fa.to_dict()
        restored = FactionAgendas(eng)
        restored.from_dict(d)
        self.assertEqual(restored.agenda_of("brigands"), "dominate")
        self.assertTrue(restored.at_war("brigands", "guards"))
        eng.end_game()


if __name__ == "__main__":
    unittest.main()
