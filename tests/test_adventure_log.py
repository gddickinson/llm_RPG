"""Adventure Leads (George: with rivals racing to clear adventures, the player
must SEE what deeds are abroad and where). The Y-journal lists each seeded
adventure's state — open / underway / a rival closing in / ended — with the
giver and a compass bearing."""

import os
import unittest

from engine.game_engine import GameEngine
from engine import adventure_log


class TestAdventureLog(unittest.TestCase):
    def setUp(self):
        self._flag = os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_open_adventures_list_with_giver_and_bearing(self):
        ls = {l["id"]: l for l in adventure_log.leads(self.e)}
        self.assertIn("blackbanner", ls)
        self.assertEqual(ls["blackbanner"]["status"], "open")
        self.assertEqual(ls["blackbanner"]["giver"], "Marshal Orsa")
        self.assertIsNotNone(ls["blackbanner"]["bearing"])
        # titles resolve (incl. the bespoke ravenmoor)
        self.assertEqual(ls["blackbanner"]["title"], "The Blackbanner Reaving")
        self.assertEqual(ls["ravenmoor"]["title"],
                         "The Hollowing of Ravenmoor")

    def test_status_reflects_begun_rival_and_ended(self):
        self.e.accept_quest("q_wychwood_vanishings")
        hero = next(h for h in
                    (self.e.npc_manager.get_npc(a)
                     for a in self.e.adventurers.living())
                    if h and h.level >= 5)
        self.e.npc_adventuring.active[hero.id] = {"adv": "blackbanner",
                                                  "act": 2, "day": 0}
        self.e.emberfell.resolve()
        ls = {l["id"]: l["status"] for l in adventure_log.leads(self.e)}
        self.assertEqual(ls["wychwood"], "active")
        self.assertEqual(ls["blackbanner"], "rival")
        self.assertEqual(ls["emberfell"], "ended")

    def test_lines_render_the_urgency(self):
        hero = next(h for h in
                    (self.e.npc_manager.get_npc(a)
                     for a in self.e.adventurers.living())
                    if h and h.level >= 5)
        self.e.npc_adventuring.active[hero.id] = {"adv": "blackbanner",
                                                  "act": 2, "day": 0}
        text = "\n".join(adventure_log.lines(self.e))
        self.assertIn("Adventure Leads", text)
        self.assertIn("a rival hero is closing in", text)

    def test_bearing_is_a_compass_point(self):
        self.assertEqual(adventure_log._bearing((0, 0), (5, 0)), "E")
        self.assertEqual(adventure_log._bearing((0, 5), (0, 0)), "N")
        self.assertEqual(adventure_log._bearing((5, 0), (0, 0)), "W")


if __name__ == "__main__":
    unittest.main()
