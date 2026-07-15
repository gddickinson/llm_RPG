"""Adventurer NPCs (P-M.6) — the world's other heroes.

A small band of adventuring-class NPCs seed at the taverns SEEKING a
company (so the player can recruit one before deep trust — the party
forms), ride the away-agent brain with `social=False` (never touching the
player's quest log or party), and persist across a save.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_adv_"))

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager


class _Base(unittest.TestCase):
    def setUp(self):
        # exercise the real band (the suite disables it by default)
        self._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        # bulletproof restore: runs even if setUp raises, and always re-asserts
        # the suite default so a leaked flag can't enable adventurers in later
        # tests (whose [Realm] company lines would crowd log-window assertions)
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

    def _an_adventurer(self):
        aid = next(iter(self.advs.controllers))
        return aid, self.engine.npc_manager.npcs[aid]


class TestSeeding(_Base):
    def test_a_band_is_seeded(self):
        self.assertGreaterEqual(len(self.advs.controllers), 1)
        for aid in self.advs.controllers:
            a = self.engine.npc_manager.npcs[aid]
            self.assertTrue(a.metadata.get("adventurer"))
            self.assertTrue(a.metadata.get("seeking_party"))

    def test_they_carry_an_adventuring_class(self):
        recruitable = {"warrior", "ranger", "wizard", "cleric",
                       "bard", "paladin"}
        for aid in self.advs.controllers:
            a = self.engine.npc_manager.npcs[aid]
            self.assertIn(a.character_class.value, recruitable)

    def test_they_are_not_driven_as_player_chars(self):
        for aid in self.advs.controllers:
            a = self.engine.npc_manager.npcs[aid]
            self.assertFalse(a.metadata.get("player_char"))


class TestPartyForms(_Base):
    def test_a_seeking_adventurer_joins_before_deep_trust(self):
        aid, a = self._an_adventurer()
        self.assertEqual(a.get_relationship(self.engine.player.id), 0)
        self.assertEqual(self.engine.companion_manager.can_recruit(a), "")
        self.engine.companion_manager.recruit(aid)
        self.assertIn(aid, self.engine.companion_manager.party)
        self.assertFalse(a.metadata.get("seeking_party"))

    def test_a_wary_stranger_still_needs_trust(self):
        # clearing the flag makes them an ordinary recruit again
        aid, a = self._an_adventurer()
        a.metadata["seeking_party"] = False
        self.assertNotEqual(self.engine.companion_manager.can_recruit(a), "")


class TestSafeDriving(_Base):
    def test_driving_never_touches_the_player_quest_log(self):
        before = len(self.engine.quest_manager.quests)
        for _ in range(20):
            self.advs.run_turn()
            self.engine.advance_turn()
        self.assertEqual(len(self.engine.quest_manager.quests), before)

    def test_a_recruited_adventurer_is_no_longer_self_driven(self):
        aid, a = self._an_adventurer()
        self.engine.companion_manager.recruit(aid)
        self.advs.run_turn()                 # must skip a party member
        self.assertFalse(a.metadata.get("seeking_party"))

    def test_the_brain_is_asocial(self):
        for ctrl in self.advs.controllers.values():
            self.assertFalse(ctrl.social)

    def test_driving_does_not_eject_the_player_from_a_building(self):
        # the player is inside a building; a driven adventurer shares the
        # GLOBAL current_interior via acting_as and must NOT exit_building
        # the player out of it (2026-07-12c teleport bug)
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors)
        w = self.engine.world.map
        w.remove_character(self.engine.player)
        self.engine.player.position = (loc.x + loc.width // 2,
                                       loc.y + loc.height - 1)
        w.place_character(self.engine.player, *self.engine.player.position)
        self.engine.enter_building(loc, via_breach=True)
        self.assertIsNotNone(self.engine.active_zone())
        inside = self.engine.player.position
        for _ in range(5):
            self.advs.run_turn()
        self.assertIsNotNone(self.engine.active_zone())    # still indoors
        self.assertEqual(self.engine.player.position, inside)


class TestCombatAttribution(_Base):
    def test_a_kill_is_not_pinned_on_the_player(self):
        # an adventurer's XP/level gains must not read as the player's
        from engine.agent_controller import acting_as
        from world.monsters import build_monster
        _, adv = self._an_adventurer()
        foe = build_monster("wolf", adv.position)
        start = len(self.engine.memory_manager.game_history)
        with acting_as(self.engine, adv):
            self.engine.combat_system._award_xp(foe)
        after = " ".join(str(e) for e in
                         self.engine.memory_manager.game_history[start:])
        self.assertNotIn("You gain", after)


class TestPersistence(_Base):
    def test_the_band_survives_a_save(self):
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            ids = sorted(self.advs.controllers)
            aid = ids[0]
            self.engine.npc_manager.npcs[aid].level = 6
            sm.save(self.engine, name="adv")
            eng2 = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
            sm.load(eng2, name="adv")
            self.assertEqual(sorted(eng2.adventurers.controllers), ids)
            self.assertEqual(eng2.npc_manager.npcs[aid].level, 6)
            eng2.end_game()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
