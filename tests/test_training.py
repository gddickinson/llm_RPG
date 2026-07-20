"""Training & advancement: level-up grants Training Points, spent at a
class-appropriate trainer on skills + spells."""

import unittest

from engine.game_engine import GameEngine
from engine import training
from engine.skill_progression import get_skill_level


def _npc(engine, aid, cls_value, pos):
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace
    c = Character(id=aid, name=aid, character_class=CharacterClass(cls_value),
                  race=CharacterRace.HUMAN, level=5, strength=10,
                  dexterity=10, constitution=10, intelligence=10,
                  wisdom=10, charisma=10, hp=20, max_hp=20)
    engine.npc_manager.add_npc(c)
    engine.world.map.place_character(c, *pos)
    return c


class TestPoints(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_levelup_grants_training_points(self):
        before = training.training_points(self.p)
        from engine.leveling import award_xp
        self.p.metadata["xp"] = 0
        award_xp(self.p, 100000)               # vault several levels
        self.assertGreater(training.training_points(self.p), before)

    def test_no_trainer_here_by_default(self):
        # standing in the open with no mentor nearby
        self.p.position = (1, 1)
        self.assertIsNone(training.trainer_here(self.engine))


class TestTrainAtTrainer(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.p.position = (5, 5)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_combat_trainer_teaches_martial_skills(self):
        # a warrior beside a blacksmith → combat/trade trainer present
        _npc(self.engine, "guard_t", "guard", (6, 5))
        prof = training.trainer_here(self.engine)
        self.assertIsNotNone(prof)
        self.assertIn("weaponry", prof["skills"])

    def test_spend_raises_a_skill(self):
        _npc(self.engine, "guard_t", "guard", (6, 5))
        self.p.metadata["training_points"] = 3
        self.p.level = 6                       # cap = 18
        before = get_skill_level(self.p, "weaponry")
        ok, msg = training.train_skill(self.engine, "weaponry")
        self.assertTrue(ok, msg)
        self.assertEqual(get_skill_level(self.p, "weaponry"), before + 1)
        self.assertEqual(training.training_points(self.p), 2)

    def test_cannot_train_without_points(self):
        _npc(self.engine, "guard_t", "guard", (6, 5))
        self.p.metadata["training_points"] = 0
        ok, msg = training.train_skill(self.engine, "weaponry")
        self.assertFalse(ok)

    def test_cannot_train_off_class_trainer(self):
        # a WARRIOR beside a wizard: the arcane tutor won't drill a warrior
        _npc(self.engine, "mage", "wizard", (6, 5))
        prof = training.trainer_here(self.engine)
        # arcane isn't suitable for a warrior → no spellcraft on offer
        if prof is not None:
            self.assertNotIn("spellcraft", prof["skills"])

    def test_wizard_learns_a_spell_at_an_arcane_tutor(self):
        from characters.character_types import CharacterClass
        self.p.character_class = CharacterClass.WIZARD
        self.p.level = 8
        self.p.intelligence = 16
        import engine.spells as spells
        spells.ensure_mana(self.p)
        _npc(self.engine, "mage", "wizard", (6, 5))
        prof = training.trainer_here(self.engine)
        self.assertIsNotNone(prof)
        self.assertTrue(prof["teaches_spells"])
        opts = training.spell_options(self.engine, prof)
        if not opts:
            self.skipTest("no cross-school spell available for this caster")
        self.p.metadata["training_points"] = 5
        sid = opts[0][0]
        ok, msg = training.learn_spell(self.engine, sid)
        self.assertTrue(ok, msg)
        self.assertIn(sid, self.p.metadata["spells_known"])
        self.assertEqual(training.training_points(self.p), 3)


class TestTrainingTab(unittest.TestCase):
    def _gui(self):
        import pygame
        pygame.display.init()
        pygame.display.set_mode((1200, 800))
        from ui.gui import GameGUI
        engine = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        engine.start_game()
        return GameGUI(engine)

    def test_tab_draws_no_trainer_and_at_trainer(self):
        from ui.player_screen import TABS
        gui = self._gui()
        gui.show_player_screen()
        gui.player_screen.tab = TABS.index("Training")
        gui.player_screen.draw(gui.screen)          # no-trainer state, no raise
        _npc(gui.engine, "guard_t", "guard",
             (gui.engine.player.position[0] + 1, gui.engine.player.position[1]))
        gui.player_screen.draw(gui.screen)          # at-trainer state
        gui.engine.end_game()

    def test_execute_trains_the_selected_skill(self):
        from ui.player_screen import TABS
        from ui import hub_training
        gui = self._gui()
        p = gui.engine.player
        p.position = (5, 5)
        p.level = 6
        p.metadata["training_points"] = 3
        _npc(gui.engine, "guard_t", "guard", (6, 5))
        gui.show_player_screen()
        gui.player_screen.tab = TABS.index("Training")
        _, rows = hub_training.build_rows(gui.engine)
        acts = hub_training._actions(rows)
        self.assertTrue(acts)
        gui.player_screen.train_cursor = 0
        before = get_skill_level(p, acts[0]["id"])
        hub_training.execute(gui.engine, gui.player_screen)
        self.assertEqual(get_skill_level(p, acts[0]["id"]), before + 1)
        gui.engine.end_game()


if __name__ == "__main__":
    unittest.main()
