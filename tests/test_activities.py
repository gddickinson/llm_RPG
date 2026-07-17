"""LIVING_WORLD A1 — the per-turn Activity system: a scheduled NPC that reaches
its work location PERFORMS its activity (a smith hammers, a cleric prays) instead
of loitering, tied to its profession/building. (George: make NPCs purposeful.)"""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_NO_ADVENTURERS", "1")
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_act_"))

import unittest

from engine.game_engine import GameEngine
from characters.character_types import CharacterClass
from characters.schedules import activity_to_action


class TestActivitySchedules(unittest.TestCase):
    def test_perform_activities_route_to_the_location(self):
        # A1 un-flatten: pray/play now GO to the location (so they can perform
        # there), where before pray just "waited" wherever it stood
        for act in ("work", "pray", "play", "eat", "drink"):
            verb, tgt = activity_to_action(act, "temple")
            self.assertEqual(verb, "move", f"{act} should route to move")
            self.assertEqual(tgt, "temple")
        self.assertEqual(activity_to_action("sleep", "home")[0], "sleep")


class TestActivitySystem(unittest.TestCase):
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
        self.acts = self.engine.activities

    def _npc(self, klass):
        return self.engine.npc_manager.create_random_npc(char_class=klass)

    def test_registered(self):
        self.assertIsNotNone(self.acts)

    def test_is_perform_gating(self):
        for a in ("work", "pray", "play", "eat", "drink"):
            self.assertTrue(self.acts.is_perform(a))
        for a in ("wander", "patrol", "sleep", ""):
            self.assertFalse(self.acts.is_perform(a))

    def test_profession_from_workplace_building(self):
        # a real keeper resolves its trade from its home_location building kind
        keeper = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self.assertEqual(self.acts.profession_of(keeper), "cook")
        # ... and it's cached on metadata
        self.assertIn("_profession", keeper.metadata)

    def test_smith_hammers(self):
        n = self._npc(CharacterClass.MERCHANT)
        n.metadata["_profession"] = "smith"        # simulate a forge workplace
        self.assertTrue(self.acts.perform(n, "work"))
        self.assertEqual(n.metadata.get("_emote"), "hammer")

    def test_generic_work_when_no_profession(self):
        n = self._npc(CharacterClass.VILLAGER)
        n.metadata["_profession"] = ""             # resolved: none
        self.acts.perform(n, "work")
        self.assertEqual(n.metadata.get("_emote"), "stoop")

    def test_class_overrides_generic_work(self):
        n = self._npc(CharacterClass.CLERIC)
        n.metadata["_profession"] = ""
        self.acts.perform(n, "work")
        self.assertEqual(n.metadata.get("_emote"), "kneel")

    def test_pray_and_play(self):
        cl = self._npc(CharacterClass.CLERIC)
        self.acts.perform(cl, "pray")
        self.assertEqual(cl.metadata.get("_emote"), "kneel")
        bard = self._npc(CharacterClass.BARD)
        self.acts.perform(bard, "play")
        self.assertEqual(bard.metadata.get("_emote"), "dance")

    def test_unknown_activity_is_not_performed(self):
        n = self._npc(CharacterClass.VILLAGER)
        self.assertFalse(self.acts.perform(n, "sleep"))


class TestScheduleArchetypes(unittest.TestCase):
    """A5 — classes with no bespoke schedule get a characterful day-plan instead
    of the old random cardinal walk."""

    def test_previously_scheduleless_classes_have_a_plan(self):
        from characters.schedules import schedule_for, current_entry
        for k in ("wizard", "rogue", "noble", "ranger", "paladin", "monk",
                  "druid", "sorcerer", "warlock", "artificer", "barbarian"):
            self.assertTrue(schedule_for(k), f"{k} has no day-plan")
            self.assertIsNotNone(current_entry(k, 10))

    def test_wizard_is_scheduled_not_random_walking(self):
        from llm.providers.heuristic import HeuristicProvider
        from characters.character_types import CharacterClass
        eng = _shared_engine()
        wiz = eng.npc_manager.create_random_npc(char_class=CharacterClass.WIZARD)
        ws = {"player_position": eng.player.position, "time_of_day": "morning"}
        d = HeuristicProvider().get_npc_action(wiz, ws, {}, False)
        self.assertEqual(d["action"], "move")
        self.assertEqual(d.get("activity"), "work")
        eng.activities.perform(wiz, "work")
        self.assertEqual(wiz.metadata.get("_emote"), "cast")


class TestPatrol(unittest.TestCase):
    """A2 — a guard walks a real beat (the gates, or a ring) not a loiter."""

    def test_guard_walks_a_beat(self):
        import random
        random.seed(2)
        eng = _shared_engine()
        guard = eng.npc_manager.get_npc("guard_01")
        loc = next(l for l in eng.world.locations if "village" in l.name.lower())
        c = loc.center()
        eng.world.map.remove_character(guard)
        guard.position = (c[0], c[1])
        eng.world.map.place_character(guard, *guard.position)
        seen, moves = set(), 0
        for _ in range(80):
            b = guard.position
            eng.action_router.process(
                guard, {"action": "move", "target": loc.name,
                        "activity": "patrol"})
            seen.add(guard.position)
            if guard.position != b:
                moves += 1
        self.assertGreater(moves, 30, "a patrol covers ground")
        self.assertGreater(len(seen), 8, "a patrol visits many tiles")
        self.assertTrue(guard.metadata.get("_patrol_route"))


class TestWorkHandler(unittest.TestCase):
    """A6 — _handle_work forges gated on the worker's profession, not merchant."""

    def test_smith_profession_forges(self):
        from characters.character_types import CharacterClass
        eng = _shared_engine()
        n = eng.npc_manager.create_random_npc(char_class=CharacterClass.VILLAGER)
        n.metadata["_profession"] = "smith"
        before = len(n.inventory)
        eng.action_router._handle_work(n, "a sword", "work")
        self.assertGreater(len(n.inventory), before, "a smith forges a good")


_ENGINE = None


def _shared_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = GameEngine(llm_provider="heuristic",
                             enable_npc_processes=False)
        _ENGINE.start_game()
    return _ENGINE


class TestActivityThroughRouter(unittest.TestCase):
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

    def _at_work(self, npc):
        loc = next(l for l in self.engine.world.locations
                   if l.name == npc.home_location)
        c = loc.center()
        self.engine.world.map.remove_character(npc)
        npc.position = c
        self.engine.world.map.place_character(npc, *c)
        return c

    def test_arrived_worker_performs_not_loiters(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")  # a cook
        self._at_work(goren)
        goren.metadata.pop("_emote", None)
        before = goren.position
        self.engine.action_router.process(
            goren, {"action": "move", "target": goren.home_location,
                    "activity": "work"})
        self.assertEqual(goren.metadata.get("_emote"), "stir")
        self.assertEqual(goren.position, before, "a worker stays at its station")

    def test_wander_activity_still_loiters(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        self._at_work(goren)
        goren.metadata.pop("_emote", None)
        self.engine.action_router.process(
            goren, {"action": "move", "target": goren.home_location,
                    "activity": "wander"})
        self.assertIsNone(goren.metadata.get("_emote"),
                          "a non-work activity strolls, it doesn't perform")

    def test_far_worker_walks_before_performing(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        c = self._at_work(goren)
        self.engine.world.map.remove_character(goren)
        goren.position = (c[0] + 15, c[1])
        self.engine.world.map.place_character(goren, *goren.position)
        goren.metadata.pop("_emote", None)
        before = goren.position
        self.engine.action_router.process(
            goren, {"action": "move", "target": goren.home_location,
                    "activity": "work"})
        self.assertNotEqual(goren.position, before, "walks toward work")
        self.assertIsNone(goren.metadata.get("_emote"), "not performing yet")


if __name__ == "__main__":
    unittest.main()
