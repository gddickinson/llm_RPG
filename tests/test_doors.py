"""Door & lock tests (P9A.1)."""

import random
import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestDoors(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.doors = self.engine.door_manager
        self.engine.world.time = 12 * 60          # noon

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _stand_at(self, name_fragment):
        loc = next(l for l in self.engine.world.locations
                   if name_fragment in l.name.lower()
                   and l.name in self.engine.interiors)
        wmap = self.engine.world.map
        wmap.remove_character(self.engine.player)
        self.engine.player.position = (loc.x, loc.y)
        wmap.place_character(self.engine.player, loc.x, loc.y)
        return loc

    def test_policies_from_data(self):
        self.assertEqual(self.doors.spec_for("Old Farmhouse")["policy"],
                         "locked")
        self.assertEqual(self.doors.spec_for("General Goods")["policy"],
                         "night_locked")
        self.assertEqual(self.doors.spec_for("Oakvale Tavern")["policy"],
                         "open")

    def test_taverns_always_open(self):
        allowed, note = self.doors.try_enter("Oakvale Tavern")
        self.assertTrue(allowed)
        self.assertEqual(note, "")

    def test_homes_are_locked_without_tools(self):
        allowed, note = self.doors.try_enter("Old Farmhouse")
        self.assertFalse(allowed)
        self.assertIn("locked", note.lower())

    def test_shops_open_by_day_locked_by_night(self):
        allowed, _ = self.doors.try_enter("General Goods")
        self.assertTrue(allowed, "shops open in daytime")
        self.doors.run_day()                       # reset to closed
        self.engine.world.time = 23 * 60           # night
        allowed, note = self.doors.try_enter("General Goods")
        self.assertFalse(allowed)
        self.assertIn("locked", note.lower())

    def test_lockpicks_can_open(self):
        self.engine.player.inventory.append(create_item("lockpicks"))
        self.engine.player.dexterity = 20
        self.doors.rng = random.Random(1)
        opened = False
        for _ in range(10):
            allowed, note = self.doors.try_enter("Old Farmhouse")
            if allowed:
                opened = True
                break
        self.assertTrue(opened, "DEX 20 + picks must open a 12 lock")

    def test_bad_pick_snaps_the_picks(self):
        self.engine.player.inventory.append(create_item("lockpicks"))
        self.engine.player.dexterity = 1
        self.doors.rng = random.Random(0)
        snapped = False
        for _ in range(20):
            allowed, note = self.doors.try_enter("Old Farmhouse")
            if "snap" in note:
                snapped = True
                break
        self.assertTrue(snapped)
        self.assertFalse(any(getattr(i, "id", "") == "lockpicks"
                             for i in self.engine.player.inventory))

    def test_the_right_key_opens(self):
        door = self.doors.door("Old Farmhouse")
        door["key"] = "lockpicks"     # any carried item id works as key
        self.engine.player.inventory.append(create_item("lockpicks"))
        allowed, note = self.doors.try_enter("Old Farmhouse")
        self.assertTrue(allowed)
        self.assertIn("turns in the lock", note)

    def test_forcing_is_noisy_and_remembered(self):
        self.engine.player.strength = 20
        self.doors.rng = random.Random(2)
        loc = self._stand_at("farmhouse")
        msg = self.engine.force_door()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertIn("splintering wood", log)
        self.assertIn("forced_entry_day",
                      self.engine.player.metadata)

    def test_forced_door_admits_and_resets_at_dawn(self):
        self.engine.player.strength = 20
        self.doors.rng = random.Random(2)
        loc = self._stand_at("farmhouse")
        for _ in range(10):
            msg = self.engine.force_door()
            if "You enter" in msg or "gives way" in msg:
                break
        door = self.doors.door(loc.name)
        self.assertEqual(door["state"], "broken")
        self.doors.run_day()
        self.assertEqual(door["state"], "locked",
                         "dawn repairs and relocks")

    def test_enter_building_respects_the_door(self):
        loc = self._stand_at("farmhouse")
        msg = self.engine.enter_building()
        self.assertIsNone(self.engine.current_interior)
        self.assertIn("locked", msg.lower())

    def test_door_state_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        door = self.doors.door("Old Farmhouse")
        door["state"] = "broken"
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="doors")
            self.doors.doors = {}
            self.assertTrue(sm.load(self.engine, name="doors"))
            self.assertEqual(
                self.engine.door_manager.door("Old Farmhouse")["state"],
                "broken")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
