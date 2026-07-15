"""The living siege (P17.8d): a hostile war-host can march on the castle,
settled off-screen by the resolver's siege math."""

import os as _os
import random
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import unittest

from engine.game_engine import GameEngine
from engine import castle_siege_event as siege


class _FireRng:
    """random() < SIEGE_CHANCE so the night's siege fires."""
    def random(self):
        return 0.0

    def randint(self, a, b):
        return a


class TestNoCastle(unittest.TestCase):
    def test_the_default_world_has_no_siege(self):
        eng = GameEngine(llm_provider="heuristic",
                         enable_npc_processes=False)
        eng.start_game()
        try:
            self.assertIsNone(siege._castle(eng))
            self.assertIsNone(siege.maybe_besiege(eng, random.Random(0)))
        finally:
            eng.end_game()


class TestSiege(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False,
                                world_kind="castle")
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def setUp(self):
        self.castle = siege._castle(self.engine)
        self.castle.properties.pop("fallen", None)

    def test_the_castle_carries_a_garrison(self):
        self.assertIsNotNone(self.castle)
        self.assertEqual(self.castle.properties.get("garrison"), 45)

    def test_the_walls_turn_back_a_raw_host(self):
        ft = self.engine.faction_ticker
        ft.state["brigands"]["strength"] = 60
        beat = siege.lay_siege(self.engine, self.castle, "brigands", 60,
                               random.Random(1))
        self.assertIn("walls held", beat)
        self.assertEqual(self.castle.properties.get("last_siege"), "held")
        self.assertLess(ft.state["brigands"]["strength"], 60,
                        "the shattered host is bloodied")

    def test_an_overwhelming_host_takes_the_keep(self):
        beat = siege.lay_siege(self.engine, self.castle, "monsters", 120,
                               random.Random(3))
        self.assertIn("FALLEN", beat)
        self.assertTrue(self.castle.properties.get("fallen"))

    def test_maybe_besiege_needs_real_pressure(self):
        ft = self.engine.faction_ticker
        ft.state["brigands"]["strength"] = 10
        ft.state["monsters"]["strength"] = 10
        self.assertIsNone(siege.maybe_besiege(self.engine, _FireRng()),
                          "no war-host rises from a quiet realm")

    def test_a_strong_realm_raises_a_host(self):
        ft = self.engine.faction_ticker
        ft.state["brigands"]["strength"] = 85
        ft.state["monsters"]["strength"] = 20
        beat = siege.maybe_besiege(self.engine, _FireRng())
        self.assertIsNotNone(beat, "the siege fires")
        self.assertIn("[Realm]", beat)

    def test_a_fallen_castle_is_not_besieged_again(self):
        self.castle.add_property("fallen", True)
        ft = self.engine.faction_ticker
        ft.state["brigands"]["strength"] = 90
        self.assertIsNone(siege.maybe_besiege(self.engine, _FireRng()))


if __name__ == "__main__":
    unittest.main()
