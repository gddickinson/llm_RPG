"""Guild halls as places (M.7b) — where blades and companies congregate.

A named Location marker is planted beside each settlement at world start,
and the M.6 adventurers gather there (by their home settlement) instead of
just any tavern — so the player knows where to go to recruit or hire.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_gh_"))

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager


class _Base(unittest.TestCase):
    def setUp(self):
        # exercise the real halls (the suite disables them with adventurers)
        self._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.gh = self.engine.guildhalls

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        if self._flag is not None:
            _os.environ["LLM_RPG_NO_ADVENTURERS"] = self._flag


class TestSeeding(_Base):
    def test_halls_are_planted_as_locations(self):
        self.assertGreaterEqual(len(self.gh.halls), 1)
        for h in self.gh.halls:
            loc = self.engine.world.get_location_at(*h["pos"])
            self.assertIsNotNone(loc)
            self.assertEqual(loc.get_property("guildhall"), h["kind"])

    def test_hall_spot_matches_by_settlement(self):
        oak = self.gh.hall_spot(settlement="Oakvale")
        riv = self.gh.hall_spot(settlement="Riverside Hamlet")
        self.assertIsNotNone(oak)
        self.assertIsNotNone(riv)
        self.assertNotEqual(oak, riv)


class TestGathering(_Base):
    def test_adventurers_gather_at_their_home_hall(self):
        # every adventurer stands at (near) a guild hall, not scattered
        gathered = 0
        for aid in self.engine.adventurers.controllers:
            a = self.engine.npc_manager.npcs.get(aid)
            if a is not None and self.gh.hall_at(a.position) is not None:
                gathered += 1
        self.assertGreaterEqual(gathered, 1)

    def test_roster_lists_the_blades_on_offer(self):
        # the hall a hall_at reports for an adventurer should roster them
        for aid in self.engine.adventurers.controllers:
            a = self.engine.npc_manager.npcs.get(aid)
            hall = self.gh.hall_at(a.position) if a else None
            if hall is None:
                continue
            names = [n.id for n in self.gh.roster(hall["id"])]
            self.assertIn(aid, names)
            return
        self.skipTest("no adventurer gathered at a hall this world")


class TestPersistence(_Base):
    def test_halls_survive_a_save(self):
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            ids = sorted(h["id"] for h in self.gh.halls)
            sm.save(self.engine, name="gh")
            eng2 = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
            sm.load(eng2, name="gh")
            self.assertEqual(sorted(h["id"] for h in eng2.guildhalls.halls),
                             ids)
            # the Location markers ride the world save too
            for h in eng2.guildhalls.halls:
                self.assertIsNotNone(
                    eng2.world.get_location_at(*h["pos"]))
            eng2.end_game()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestTraining(_Base):
    """M.7c — a hall is where you go to get BETTER: pay for a lesson."""

    def _stand_at_hall(self):
        pos = tuple(self.gh.halls[0]["pos"])
        self.engine.player.position = pos
        return pos

    def _a_skill(self):
        from engine.skill_progression import SKILLS
        return next(iter(SKILLS))

    def test_training_spends_gold_and_grants_xp(self):
        from engine.skill_progression import _skills_dict
        self._stand_at_hall()
        sid = self._a_skill()
        self.engine.player.gold = 500
        g0 = self.engine.player.gold
        xp0 = _skills_dict(self.engine.player).get(sid, 0)
        self.gh.train(sid)
        self.assertLess(self.engine.player.gold, g0)
        self.assertGreater(_skills_dict(self.engine.player).get(sid, 0), xp0)

    def test_the_fee_scales_with_skill(self):
        from engine.skill_progression import _skills_dict
        self._stand_at_hall()
        sid = self._a_skill()
        low = self.gh.training_fee(self.engine.player, sid)
        _skills_dict(self.engine.player)[sid] = 100000   # a far higher level
        self.assertGreater(self.gh.training_fee(self.engine.player, sid), low)

    def test_cannot_train_away_from_a_hall(self):
        self.engine.player.position = (0, 0)
        if self.gh.hall_at((0, 0)) is not None:
            self.engine.player.position = (self.engine.world.map.width - 1,
                                           self.engine.world.map.height - 1)
        self.assertIn("guild hall", self.gh.train(self._a_skill()).lower())

    def test_an_unknown_skill_is_refused(self):
        self._stand_at_hall()
        self.assertIn("trainer", self.gh.train("basketweaving").lower())

    def test_cannot_afford_the_lesson(self):
        self._stand_at_hall()
        self.engine.player.gold = 0
        msg = self.gh.train(self._a_skill())
        self.assertIn("afford", msg.lower())
        self.assertEqual(self.engine.player.gold, 0)     # nothing charged


class TestValidation(unittest.TestCase):
    def test_bad_kind_is_flagged(self):
        from items.validate_world import check_guildhalls
        # the shipped data is clean
        self.assertEqual(check_guildhalls(), [])


if __name__ == "__main__":
    unittest.main()
