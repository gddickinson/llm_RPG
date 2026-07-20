"""Overworld monster lairs (P19.2).

Seeded dangers on the overworld — a dragon's roost, a goblin warren, a
troll den — each a boss or a pack over a hoard. Clear it and the hoard
spills onto the ground, gold fills the purse, and the place falls quiet.
An overworld dragon gets its full breath (the telegraph fires outside a
zone), so a roost is where you actually face one."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from engine.lairs import LairSystem, MIN_DIST_FROM_START
from engine import bosses
from items.item_registry import create_item


class TestLairData(unittest.TestCase):
    def test_archetypes_load_with_real_items(self):
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        arche = eng.lairs._archetypes()
        self.assertIn("dragon_roost", arche)
        for key, spec in arche.items():
            self.assertTrue(spec.get("occupants"), f"{key} needs occupants")
            for iid in spec.get("hoard", []):
                self.assertIsNotNone(create_item(iid),
                                     f"{key} hoard item '{iid}' must exist")
        eng.end_game()


class TestLairSeeding(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_lairs_are_seeded(self):
        self.assertTrue(self.engine.lairs.lairs, "the world should hold lairs")

    def test_each_lair_has_live_occupants_and_a_marker(self):
        for lair in self.engine.lairs.lairs:
            live = [oid for oid in lair["occupants"]
                    if (n := self.engine.npc_manager.npcs.get(oid))
                    and n.is_active()]
            self.assertTrue(live, f"{lair['name']} should be occupied")
            loc = self.engine.world.get_location_at(*lair["pos"])
            self.assertIsNotNone(loc, "a lair reads as a place on the map")

    def test_a_roost_holds_a_dragon_boss(self):
        roost = next((l for l in self.engine.lairs.lairs
                      if l["key"] == "dragon_roost"), None)
        if roost is None:
            self.skipTest("no roost seeded in this layout")
        drag = self.engine.npc_manager.npcs[roost["occupants"][0]]
        self.assertTrue(bosses.is_boss(drag))
        self.assertEqual(drag.name, "Young Dragon")

    def test_lairs_are_far_from_the_player_start(self):
        px, py = self.engine.player.position
        for lair in self.engine.lairs.lairs:
            lx, ly = lair["pos"]
            self.assertGreaterEqual(abs(lx - px) + abs(ly - py),
                                    MIN_DIST_FROM_START,
                                    "a dragon is not a starting-meadow foe")

    def test_seed_does_not_run_twice(self):
        before = len(self.engine.lairs.lairs)
        self.assertEqual(self.engine.lairs.seed(), 0, "already seeded")
        self.assertEqual(len(self.engine.lairs.lairs), before)


class TestLairClearing(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.assertTrue(self.engine.lairs.lairs)
        self.lair = self.engine.lairs.lairs[0]

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _slay_all(self):
        for oid in self.lair["occupants"]:
            n = self.engine.npc_manager.npcs.get(oid)
            if n is not None:
                n.hp = 0
                if hasattr(n, "defeat"):
                    n.defeat()

    def test_live_lair_yields_nothing(self):
        self.assertEqual(self.engine.lairs.check_cleared(), 0)
        self.assertFalse(self.lair["cleared"])

    def test_clearing_drops_the_hoard_and_gold(self):
        gold0 = self.engine.player.gold
        self._slay_all()
        got = self.engine.lairs.check_cleared()
        self.assertGreaterEqual(got, 1)
        self.assertTrue(self.lair["cleared"])
        self.assertEqual(self.engine.player.gold,
                         gold0 + self.lair["gold"], "the hoard's gold is yours")
        pos = tuple(self.lair["pos"])
        ground = getattr(self.engine.world, "ground_items", {}).get(pos, [])
        self.assertGreaterEqual(len(ground), len(self.lair["hoard"]),
                                "the hoard spills onto the ground")

    def test_a_legend_is_recorded(self):
        self._slay_all()
        self.engine.lairs.check_cleared()
        recent = " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                          for e in self.engine.memory_manager.get_recent_history())
        self.assertIn("[Legend]", recent)

    def test_clearing_is_not_rewarded_twice(self):
        self._slay_all()
        self.engine.lairs.check_cleared()
        gold_after = self.engine.player.gold
        self.assertEqual(self.engine.lairs.check_cleared(), 0,
                         "an already-cleared lair pays nothing more")
        self.assertEqual(self.engine.player.gold, gold_after)


class TestLairPersistence(unittest.TestCase):
    def test_round_trip(self):
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        eng.lairs.lairs[0]["cleared"] = True
        d = eng.lairs.to_dict()
        restored = LairSystem(eng)
        restored.from_dict(d)
        self.assertEqual(len(restored.lairs), len(eng.lairs.lairs))
        self.assertTrue(restored.lairs[0]["cleared"])
        self.assertTrue(restored._seeded, "a loaded world does not re-seed")
        self.assertEqual(restored.seed(), 0)
        eng.end_game()


class TestLairHomeBehaviour(unittest.TestCase):
    """LIVING_WORLD C1 — a lair's occupants are LEASHED to the den + given roles,
    so a warren holds together and reads as an occupied camp (George: do
    intelligent monsters have activities? do social ones have jobs?)."""

    def setUp(self):
        self.eng = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
        self.eng.start_game()
        if not self.eng.lairs.lairs:
            self.eng.lairs.seed()
        self.lair = self.eng.lairs.lairs[0]
        self.occ = [self.eng.npc_manager.npcs[i] for i in self.lair["occupants"]
                    if i in self.eng.npc_manager.npcs]

    def tearDown(self):
        try:
            self.eng.end_game()
        except Exception:
            pass

    def test_occupants_are_leashed_with_roles(self):
        for m in self.occ:
            self.assertEqual(m.metadata["behavior"].get("territorial"), 6,
                             "a territorial leash (fixes the warren scatter)")
            self.assertEqual(m.metadata["home_pos"], self.lair["pos"],
                             "leashed to the den centre")
            self.assertIn(m.metadata.get("lair_role"),
                          ("chief", "sentry", "guard", "shaman", "forager"))

    def test_a_lair_has_a_chief_and_sentries(self):
        roles = {m.metadata.get("lair_role") for m in self.occ}
        self.assertTrue({"sentry", "guard"} & roles, "someone stands watch")

    def test_the_den_holds_together(self):
        # drive the occupants many turns with the player far off: none wander away
        prov = self.eng.llm_interface.provider
        cx, cy = self.lair["pos"]
        self.eng.player.position = (cx + 40, cy)
        ws = {"player_position": self.eng.player.position,
              "time_of_day": "morning"}
        maxstray = 0
        for _ in range(40):
            for m in self.occ:
                if m.is_alive():
                    self.eng.action_router.process(
                        m, prov.get_npc_action(m, ws, {}, ""))
            for m in self.occ:
                maxstray = max(maxstray,
                               abs(m.position[0] - cx) + abs(m.position[1] - cy))
        self.assertLessEqual(maxstray, 12, "the den holds — it does not scatter")

    def test_sentry_advances_the_ring_at_a_waypoint(self):
        # _patrol_home moves toward the current ring waypoint and advances to the
        # next once reached — waypoint 0 is (home_x + r, home_y)
        prov = self.eng.llm_interface.provider
        s = self.occ[0]
        home = (50, 50)
        s.metadata["patrol_i"] = 0
        s.position = (53, 50)                  # standing on waypoint 0 (r=3)
        act = prov._patrol_home(s, s.metadata, home)
        self.assertEqual(act["action"], "move")
        self.assertEqual(s.metadata["patrol_i"], 1, "reached wp0 → next waypoint")

    def test_sentry_paces_toward_a_waypoint(self):
        prov = self.eng.llm_interface.provider
        s = self.occ[0]
        home = (50, 50)
        s.metadata["patrol_i"] = 0
        s.position = (50, 50)                  # at the den → move toward wp0 (east)
        act = prov._patrol_home(s, s.metadata, home)
        self.assertEqual(act["target"], "east", "walks toward the perimeter")


class TestMonsterDayNight(unittest.TestCase):
    """LIVING_WORLD C2 — a nocturnal creature lies DORMANT at its den by day and
    stirs by night (George: should monsters sleep?)."""

    def setUp(self):
        self.eng = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
        self.eng.start_game()
        self.prov = self.eng.llm_interface.provider

    def tearDown(self):
        try:
            self.eng.end_game()
        except Exception:
            pass

    def _nocturnal(self):
        from world.monsters import build_monster
        m = build_monster("restless_bones", (30, 30))
        m.metadata["home_pos"] = [30, 30]
        m.metadata["lair_role"] = "sentry"
        self.assertEqual(m.metadata["active"], "night")
        return m

    def test_nocturnal_is_dormant_by_day(self):
        m = self._nocturnal()
        act = self.prov._hostile_action(m, {"time_of_day": "morning"}, False)
        self.assertEqual(act["action"], "wait")
        self.assertTrue(m.metadata.get("asleep"))
        self.assertEqual(m.metadata.get("_bubble"), "sleep")

    def test_nocturnal_is_active_by_night(self):
        m = self._nocturnal()
        act = self.prov._hostile_action(m, {"time_of_day": "night"}, False)
        self.assertEqual(act["action"], "move", "it patrols at night")
        self.assertFalse(m.metadata.get("asleep"))

    def test_survival_wakes_a_dormant_monster(self):
        m = self._nocturnal()
        # with the player in view even by day it engages, not sleeps
        act = self.prov._hostile_action(
            m, {"time_of_day": "morning", "player_position": (31, 30)}, True)
        self.assertNotEqual(act.get("target"), "dormant in its lair")

    def test_always_active_monster_never_sleeps(self):
        from world.monsters import build_monster
        g = build_monster("goblin", (40, 40))       # active defaults to 'always'
        g.metadata["home_pos"] = [40, 40]
        g.metadata["lair_role"] = "guard"
        self.prov._hostile_action(g, {"time_of_day": "night"}, False)
        self.assertFalse(g.metadata.get("asleep"))


if __name__ == "__main__":
    unittest.main()
