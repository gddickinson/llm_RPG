"""Townsfolk ventures (George: extend the adventurers' roam/quest life to
ordinary folk). A townsperson occasionally leaves on a mundane, story-shaped
trip — visit kin, a pilgrimage, a trade run, wanderlust — travels there and
home again with [Town] beats, bounded so the town never empties."""

import os
import unittest

from engine.game_engine import GameEngine


class TestVentureLifecycle(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.tv = self.e.townsfolk_venture

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_ordinary_folk_are_eligible(self):
        elig = self.tv._eligible(self.tv._cfg())
        self.assertTrue(elig, "some ordinary townsfolk can venture")
        classes = {self.tv._class_of(n) for n in elig}
        self.assertTrue(classes & {"villager", "merchant", "bard", "noble"})

    def test_key_npcs_are_never_dragged_off(self):
        elig = {n.id for n in self.tv._eligible(self.tv._cfg())}
        # adventure cast, quest-givers and mayors must stay put
        for npc in self.e.npc_manager.npcs.values():
            m = npc.metadata or {}
            if m.get("adventure") or m.get("quest_giver") or m.get("mayor"):
                self.assertNotIn(npc.id, elig, npc.id)

    def test_a_venture_starts_and_is_announced(self):
        npc = self.tv._eligible(self.tv._cfg())[0]
        self.assertTrue(self.tv._start(npc, self.tv._cfg()))
        self.assertIn("venture", npc.metadata)
        self.assertTrue(npc.metadata.get("venturing"))
        beats = [h["event"] for h in self.e.memory_manager.game_history
                 if h["event"].startswith("[Town]")]
        self.assertTrue(any(npc.name in b for b in beats),
                        "the going is announced as a [Town] beat")

    def test_venturer_is_skipped_by_ambient_ai(self):
        # the 'venturing' flag is what process_npc_turns checks to hand off
        npc = self.tv._eligible(self.tv._cfg())[0]
        self.tv._start(npc, self.tv._cfg())
        self.assertTrue(npc.metadata.get("venturing"))

    def test_full_out_and_back_cycle_completes(self):
        npc = self.tv._eligible(self.tv._cfg())[0]
        self.tv._start(npc, self.tv._cfg())
        self.tv.venturing.add(npc.id)
        # drive until the venture resolves (or a generous cap)
        for _ in range(600):
            if "venture" not in npc.metadata:
                break
            self.tv.run_turn()
        self.assertNotIn("venture", npc.metadata,
                         "the townsperson eventually comes home")
        self.assertNotIn("venturing", npc.metadata)
        backs = [h["event"] for h in self.e.memory_manager.game_history
                 if h["event"].startswith("[Town]") and npc.name in h["event"]]
        self.assertGreaterEqual(len(backs), 2, "a going AND a return beat")

    def test_venturing_is_capped(self):
        cfg = self.tv._cfg()
        cap = cfg.get("max_venturing", 3)
        # force many days; the cap must hold
        for _ in range(60):
            self.tv.run_day()
        self.assertLessEqual(len(self.tv.venturing), cap)

    def test_gated_off_by_env(self):
        os.environ["LLM_RPG_NO_ADVENTURERS"] = "1"
        try:
            before = set(self.tv.venturing)
            for _ in range(20):
                self.tv.run_day()
            self.assertEqual(set(self.tv.venturing), before,
                             "no new ventures while gated off")
        finally:
            os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)


class TestVenturePersistence(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")

    def test_venturing_set_round_trips(self):
        from engine.townsfolk_venture import TownsfolkVentureSystem
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        try:
            tv = e.townsfolk_venture
            npc = tv._eligible(tv._cfg())[0]
            tv._start(npc, tv._cfg())
            tv.venturing.add(npc.id)
            d = tv.to_dict()
            tv2 = TownsfolkVentureSystem(e)
            tv2.from_dict(d)          # the NPC still carries its venture meta
            self.assertIn(npc.id, tv2.venturing)
        finally:
            e.end_game()


if __name__ == "__main__":
    unittest.main()
