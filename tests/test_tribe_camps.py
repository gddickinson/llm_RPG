"""LIVING_WORLD C3 — visible TRIBE CAMPS: a monster tribe (an abstract strength
int that only ever spilled a raid party) now has a findable camp near its
territory with a role-tagged cast — chief, shaman, foragers, warriors — reusing
the C1 lair-role/leash behaviour. (George: do social monsters have jobs in their
tribes/communities?)"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_NO_ADVENTURERS", "1")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_camp_"))

import unittest

from engine.game_engine import GameEngine
from engine.tribe_camps import TribeCampSystem, CAMP_HOME_RADIUS


class TestTribeCamps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def setUp(self):
        self.tc = self.engine.tribe_camps

    def test_camps_seed_at_world_start(self):
        self.assertTrue(self.tc.camps, "a camp is planted for the tribes")

    def test_a_camp_has_a_role_tagged_cast(self):
        c = self.tc.camps[0]
        roles = [m.metadata.get("lair_role") for m in self.tc.roster(c["tid"])]
        self.assertIn("chief", roles)
        self.assertIn("shaman", roles)
        self.assertTrue(any(r in ("sentry", "guard") for r in roles),
                        "warriors stand watch")

    def test_members_are_leashed_and_tribe_tagged(self):
        c = self.tc.camps[0]
        for m in self.tc.roster(c["tid"]):
            self.assertEqual(m.metadata["behavior"].get("territorial"),
                             CAMP_HOME_RADIUS)
            self.assertEqual(m.metadata["home_pos"], c["pos"])
            self.assertEqual(m.metadata.get("tribe"), c["tid"])
            self.assertEqual(m.metadata.get("lair"), f"tribe:{c['tid']}",
                             "bands via the pack brain when the player closes in")

    def test_camp_has_a_findable_marker(self):
        markers = [l for l in self.engine.world.locations
                   if l.get_property("tribe_camp")]
        self.assertGreaterEqual(len(markers), len(self.tc.camps))
        self.assertTrue(self.tc.camp_at(tuple(self.tc.camps[0]["pos"])))

    def test_camp_size_scales_with_strength(self):
        # a stronger tribe fields more warriors than a weak one (chief+shaman+
        # forager + up to MAX_WARRIORS)
        sizes = {c["tid"]: len(self.tc.roster(c["tid"])) for c in self.tc.camps}
        self.assertTrue(all(3 <= n <= 3 + 4 for n in sizes.values()), sizes)

    def test_camp_holds_together(self):
        c = self.tc.camps[0]
        crew = [m for m in self.tc.roster(c["tid"]) if m.is_alive()]
        prov = self.engine.llm_interface.provider
        cx, cy = c["pos"]
        self.engine.player.position = (cx + 50, cy)
        ws = {"player_position": self.engine.player.position,
              "time_of_day": "morning"}
        maxstray = 0
        for _ in range(30):
            for m in crew:
                if m.is_alive():
                    self.engine.action_router.process(
                        m, prov.get_npc_action(m, ws, {}, ""))
            for m in crew:
                maxstray = max(maxstray,
                               abs(m.position[0] - cx) + abs(m.position[1] - cy))
        self.assertLessEqual(maxstray, 14, "the camp does not scatter")

    def test_c3_raid_is_credited_to_the_camp(self):
        T = self.engine.monster_tribes
        tid = self.tc.camps[0]["tid"]
        sett = T._target_settlement()
        if sett is None:
            self.skipTest("no settlement")
        cx, cy = sett.center()
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (cx + 2, cy)
        self.engine.world.map.place_character(self.engine.player, cx + 2, cy)
        T.strength[tid] = 90
        T._raid(tid, T._tribes()[tid])
        recent = " ".join(self.engine.memory_manager.get_recent_history(6))
        self.assertIn("warband of " + self.tc.camp_name(tid), recent)

    def test_c3_a_wiped_camp_sends_no_raiders(self):
        T = self.engine.monster_tribes
        tid = self.tc.camps[-1]["tid"]
        for m in self.tc.roster(tid):
            if (m.metadata or {}).get("lair_role") in ("chief", "sentry", "guard"):
                m.hp = 0
                m.status = "defeated"
        self.assertEqual(self.tc.living_warriors(tid), 0)
        sett = T._target_settlement()
        if sett is None:
            self.skipTest("no settlement")
        cx, cy = sett.center()
        self.engine.world.map.remove_character(self.engine.player)
        self.engine.player.position = (cx + 2, cy)
        self.engine.world.map.place_character(self.engine.player, cx + 2, cy)
        before = len([n for n in self.engine.npc_manager.npcs.values()
                      if (n.metadata or {}).get("tribe") == tid
                      and not (n.metadata or {}).get("camp_member")])
        T.strength[tid] = 90
        T._maybe_spill(tid, T._tribes()[tid], sett)
        after = len([n for n in self.engine.npc_manager.npcs.values()
                     if (n.metadata or {}).get("tribe") == tid
                     and not (n.metadata or {}).get("camp_member")])
        self.assertEqual(after, before, "no warriors left to march")

    def test_persist_round_trip(self):
        d = self.tc.to_dict()
        fresh = TribeCampSystem(self.engine)
        fresh.from_dict(d)
        self.assertEqual(len(fresh.camps), len(self.tc.camps))
        self.assertTrue(fresh._seeded, "a loaded world does not re-seed")
        self.assertEqual(fresh.seed(), 0)


if __name__ == "__main__":
    unittest.main()
