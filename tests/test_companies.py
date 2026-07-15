"""M.6b — rival adventuring COMPANIES.

The seeking, un-recruited adventurers who hail from the same settlement
band into a company led by the strongest; the followers then travel with
their leader, and the company carries a renown that rises as it grows. A
company whose leader falls disbands back to seeking.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_co_"))

import unittest

from engine.game_engine import GameEngine
from engine import companies


class _Base(unittest.TestCase):
    def setUp(self):
        self._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        # bulletproof restore: runs even if setUp raises, and always re-asserts
        # the suite default so a leaked flag can't enable adventurers elsewhere
        self.addCleanup(_os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.advs = self.engine.adventurers

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        if self._flag is not None:
            _os.environ["LLM_RPG_NO_ADVENTURERS"] = self._flag

    def _by_home(self, home):
        npcs = self.engine.npc_manager.npcs
        return [npcs[aid] for aid in self.advs.controllers
                if npcs[aid].metadata.get("home_settlement") == home]


class TestFormation(_Base):
    def test_two_same_home_seekers_band_together(self):
        # Kestrel + Bram both hail from Oakvale — they form ONE company
        oak = self._by_home("Oakvale")
        self.assertGreaterEqual(len(oak), 2)
        self.assertEqual(companies.form(self.advs), 1)
        lids = {a.metadata.get("company") for a in oak}
        self.assertEqual(len(lids), 1)          # all under one leader
        self.assertIsNotNone(next(iter(lids)))

    def test_the_leader_is_the_strongest(self):
        oak = self._by_home("Oakvale")
        companies.form(self.advs)
        leader_id = oak[0].metadata.get("company")
        strongest = max(oak, key=lambda a: a.level)
        self.assertEqual(leader_id, strongest.id)
        self.assertTrue(strongest.metadata.get("company_leader"))

    def test_the_company_takes_a_name(self):
        companies.form(self.advs)
        leaders = companies.companies(self.advs)
        self.assertTrue(leaders)
        npcs = self.engine.npc_manager.npcs
        self.assertTrue(npcs[leaders[0]].metadata.get("company_name"))

    def test_a_lone_seeker_stays_company_less(self):
        # Sable hails from Riverside Hamlet alone — no band forms there
        companies.form(self.advs)
        river = self._by_home("Riverside Hamlet")
        for a in river:
            self.assertIsNone(a.metadata.get("company"))

    def test_forming_is_idempotent(self):
        self.assertEqual(companies.form(self.advs), 1)
        self.assertEqual(companies.form(self.advs), 0)   # no re-banding

    def test_a_forming_beat_is_logged(self):
        companies.form(self.advs)
        text = " ".join(str(e) for e in
                        self.engine.memory_manager.game_history)
        self.assertIn("[Realm]", text)
        self.assertIn("forms", text)


class TestRenownAndMembers(_Base):
    def test_members_lists_the_whole_band(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        band = companies.members(self.advs, leader_id)
        self.assertGreaterEqual(len(band), 2)
        self.assertIn(self.engine.npc_manager.npcs[leader_id], band)

    def test_renown_sums_member_levels(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        band = companies.members(self.advs, leader_id)
        expected = sum(m.level for m in band) * companies.RENOWN_PER_LEVEL
        self.assertEqual(companies.renown(self.advs, leader_id), expected)

    def test_renown_is_positive_for_a_real_company(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        self.assertGreater(companies.renown(self.advs, leader_id), 0)


class TestTravelTogether(_Base):
    def test_a_follower_trails_its_leader(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        npcs = self.engine.npc_manager.npcs
        follower = next(a for a in companies.members(self.advs, leader_id)
                        if a.id != leader_id)
        trail = companies.leader_position(self.advs, follower)
        self.assertEqual(trail, tuple(npcs[leader_id].position))

    def test_a_leader_roams_free(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        leader = self.engine.npc_manager.npcs[leader_id]
        self.assertIsNone(companies.leader_position(self.advs, leader))

    def test_run_turn_homes_a_follower_on_the_leader(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        follower = next(a for a in companies.members(self.advs, leader_id)
                        if a.id != leader_id)
        self.advs.run_turn()
        ctrl = self.advs.controllers[follower.id]
        # its brain is aimed at the leader's neighbourhood (the leader may
        # have stepped on since it was homed), not its far tavern loiter spot
        self.assertIsNotNone(ctrl.home)
        lp = self.engine.npc_manager.npcs[leader_id].position
        self.assertLessEqual(max(abs(ctrl.home[0] - lp[0]),
                                 abs(ctrl.home[1] - lp[1])), 3)


class TestDissolution(_Base):
    def test_disbands_when_the_leader_falls(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        follower = next(a for a in companies.members(self.advs, leader_id)
                        if a.id != leader_id)
        leader = self.engine.npc_manager.npcs[leader_id]
        leader.hp, leader.status = 0, "dead"               # leader down
        companies.dissolve(self.advs)
        self.assertIsNone(follower.metadata.get("company"))
        self.assertTrue(follower.metadata.get("seeking_party"))

    def test_a_recruited_leader_stands_the_company_down(self):
        companies.form(self.advs)
        leader_id = companies.companies(self.advs)[0]
        # a company leader is no longer seeking, so simulate the rare recruit
        # by seating it in the party directly, then stand the company down
        self.engine.companion_manager.party.append(leader_id)
        companies.dissolve(self.advs)
        self.assertFalse(self.engine.npc_manager.npcs[leader_id]
                         .metadata.get("company_leader"))


if __name__ == "__main__":
    unittest.main()
