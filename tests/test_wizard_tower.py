"""Wizard's Tower tests (P9.4) — sigils, wards, and the observatory."""

import unittest

from engine.game_engine import GameEngine


class TestWizardTower(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.hall = self.engine.interiors["Wizard's Tower"]
        self.library = self.hall.level_above

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _sigil(self, idx):
        return next(f for f in self.library.furniture
                    if f["name"] == "Sigil" and f["idx"] == idx)

    def test_four_floors_of_increasing_strangeness(self):
        menagerie = self.library.level_above
        observatory = menagerie.level_above
        self.assertIsNotNone(observatory)
        self.assertTrue(menagerie.dark)
        self.assertIsNone(observatory.level_above,
                          "the observatory is the top")

    def test_ward_seals_the_library_stairs(self):
        self.assertTrue(
            self.engine.structures.stairs_warded(self.library,
                                                 up=True))
        self.engine.current_interior = self.library
        sx, sy = self.library.stairs_up
        self.engine.player.position = (sx + 1, sy)
        moved = self.engine.player_actions.move(-1, 0)
        self.assertFalse(moved, "the ward must block the stairs")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("ward", log.lower())
        self.engine.current_interior = None

    def test_wrong_order_resets(self):
        s = self.engine.structures
        s.touch_sigil(self.library, self._sigil(0))  # Sun first: wrong
        self.assertEqual(
            s.puzzle_progress.get(self.library.name, []), [])
        self.assertNotIn(self.library.name, s.solved)

    def test_moon_sun_stars_dissolves_the_ward(self):
        s = self.engine.structures
        s.touch_sigil(self.library, self._sigil(1))  # Moon
        s.touch_sigil(self.library, self._sigil(0))  # Sun
        msg = s.touch_sigil(self.library, self._sigil(2))  # Stars
        self.assertIn("dissolves", msg)
        self.assertIn(self.library.name, s.solved)
        self.assertFalse(s.stairs_warded(self.library, up=True))

    def test_menagerie_wakes_on_first_visit(self):
        menagerie = self.library.level_above
        spawned = self.engine.structures.on_enter_level(menagerie)
        self.assertEqual(spawned, 2)
        natives = [n for n in self.engine.npc_manager.npcs.values()
                   if n.metadata.get("zone") == menagerie.name]
        self.assertTrue(all("Wisp" in n.name for n in natives))

    def test_observatory_holds_the_prize(self):
        observatory = self.library.level_above.level_above
        chest = next(f for f in observatory.furniture
                     if f["name"] == "Chest")
        key = f"wizard_tower:{chest['x']}:{chest['y']}"
        ids = [getattr(i, "id", "") for i in
               self.engine.structures.chest_contents.get(key, [])]
        self.assertIn("scroll_fireball", ids)

    def test_alzara_lives_here(self):
        alzara = self.engine.npc_manager.get_npc("tower_wizard_01")
        self.assertIsNotNone(alzara)
        self.assertEqual(alzara.home_location, "Wizard's Tower")
        from engine.heart_events import HEART_EVENTS
        self.assertIn("tower_wizard_01", HEART_EVENTS)

    def test_solved_ward_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        s = self.engine.structures
        s.solved.append(self.library.name)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="tower")
            s.solved = []
            self.assertTrue(sm.load(self.engine, name="tower"))
            self.assertIn(self.library.name,
                          self.engine.structures.solved)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_content_validates(self):
        from items.data_validate import _check_structures
        self.assertEqual(_check_structures(), [])


if __name__ == "__main__":
    unittest.main()
