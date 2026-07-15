"""Structure framework tests (P9.1) — the Ruined Keep opens."""

import unittest

from engine.game_engine import GameEngine


class TestStructures(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _keep(self):
        return next((name, i) for name, i in
                    self.engine.interiors.items()
                    if "ruined keep" in name.lower())

    def test_content_validates(self):
        from items.data_validate import _check_structures
        self.assertEqual(_check_structures(), [])

    def test_keep_is_enterable_with_levels(self):
        name, hall = self._keep()
        self.assertTrue(hall.ground)
        self.assertIsNotNone(hall.level_below, "the crypt exists")
        crypt = hall.level_below
        self.assertTrue(crypt.dark, "crypts are dark")
        self.assertEqual(hall.stairs_down, crypt.stairs_up)

    def test_hall_inscriptions_carry_this_worlds_history(self):
        from engine.furniture import interact
        name, hall = self._keep()
        self.engine.current_interior = hall
        stone = next(f for f in hall.furniture
                     if f["name"] == "Inscription")
        self.engine.player.position = (stone["x"], stone["y"])
        msg = interact(self.engine)
        self.assertIn("Year", msg,
                      "hall carvings must quote the history sim")
        self.engine.current_interior = None

    def test_crypt_inscription_is_authored(self):
        from engine.furniture import interact
        name, hall = self._keep()
        crypt = hall.level_below
        self.engine.current_interior = crypt
        stone = next(f for f in crypt.furniture
                     if f["name"] == "Inscription")
        self.engine.player.position = (stone["x"], stone["y"])
        msg = interact(self.engine)
        self.assertIn("steward", msg)
        self.engine.current_interior = None

    def test_crypt_guardian_is_the_troll(self):
        name, hall = self._keep()
        crypt = hall.level_below
        self.engine.structures.on_enter_level(crypt)
        native = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.metadata.get("zone") == crypt.name)
        self.assertIn("Troll", native.name)

    def test_footprint_relics_moved_into_the_crypt_chest(self):
        name, hall = self._keep()
        loc = next(l for l in self.engine.world.locations
                   if l.name == name)
        for (x, y) in self.engine.world.ground_items:
            self.assertFalse(
                loc.contains(x, y),
                "nothing may lie unreachable on the footprint")
        crypt = hall.level_below
        chest = next(f for f in crypt.furniture
                     if f["name"] == "Chest")
        key = f"ruined_keep:{chest['x']}:{chest['y']}"
        contents = self.engine.structures.chest_contents.get(key, [])
        if not contents:
            self.skipTest("no keep-placed relic this worldgen")
        self.assertTrue(all(hasattr(i, "id") for i in contents))

    def test_chest_loots_exactly_once(self):
        from engine.furniture import interact
        name, hall = self._keep()
        crypt = hall.level_below
        chest = next(f for f in crypt.furniture
                     if f["name"] == "Chest")
        key = f"ruined_keep:{chest['x']}:{chest['y']}"
        if not self.engine.structures.chest_contents.get(key):
            from items.item_registry import create_item
            self.engine.structures.chest_contents[key] = \
                [create_item("potion")]
        self.engine.current_interior = crypt
        self.engine.player.position = (chest["x"], chest["y"])
        msg = interact(self.engine)
        self.assertIn("Inside the chest", msg)
        msg = interact(self.engine)
        self.assertIn("empty", msg)
        self.engine.current_interior = None

    def test_chest_contents_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        from items.item_registry import create_item
        key = "ruined_keep:6:1"
        self.engine.structures.chest_contents[key] = \
            [create_item("potion")]
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="crypt")
            self.engine.structures.chest_contents = {}
            self.assertTrue(sm.load(self.engine, name="crypt"))
            loaded = self.engine.structures.chest_contents.get(key)
            self.assertTrue(loaded)
            self.assertEqual(loaded[0].id, "potion")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_first_visit_populates_the_crypt(self):
        name, hall = self._keep()
        crypt = hall.level_below
        before = len(self.engine.npc_manager.npcs)
        spawned = self.engine.structures.on_enter_level(crypt)
        self.assertEqual(spawned, 1)
        self.assertEqual(len(self.engine.npc_manager.npcs),
                         before + 1)
        native = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.metadata.get("zone") == crypt.name)
        self.assertEqual(native.name, "Wandering Troll")
        # second visit: the crypt stays as you left it
        self.assertEqual(
            self.engine.structures.on_enter_level(crypt), 0)

    def test_native_is_fightable_in_its_level(self):
        from engine.presence import npc_adjacent_to_player
        name, hall = self._keep()
        crypt = hall.level_below
        self.engine.structures.on_enter_level(crypt)
        native = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.metadata.get("zone") == crypt.name)
        self.engine.current_interior = crypt
        nx, ny = native.position
        self.engine.player.position = (nx + 1, ny)
        self.assertTrue(npc_adjacent_to_player(self.engine, native))
        msg = self.engine.combat_system.player_attack(native.name)
        self.assertNotIn("too far away", msg)
        self.engine.current_interior = None

    def test_native_not_targetable_from_other_levels(self):
        name, hall = self._keep()
        crypt = hall.level_below
        self.engine.structures.on_enter_level(crypt)
        native = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.metadata.get("zone") == crypt.name)
        self.engine.current_interior = hall
        self.engine.player.position = hall.door
        ok, why = self.engine.targeting.can_hit(native)
        self.assertFalse(ok)
        self.assertIn("isn't here", why)
        self.engine.current_interior = None

    def test_populated_state_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        name, hall = self._keep()
        crypt = hall.level_below
        self.engine.structures.on_enter_level(crypt)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="keep")
            self.engine.structures.populated = {}
            self.assertTrue(sm.load(self.engine, name="keep"))
            self.assertEqual(
                self.engine.structures.on_enter_level(
                    self.engine.interiors[name].level_below), 0,
                "a populated crypt must not respawn after load")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_build_is_idempotent(self):
        self.assertEqual(self.engine.structures.build(), 0)


if __name__ == "__main__":
    unittest.main()
