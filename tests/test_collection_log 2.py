"""Collection log tests (P2.5)."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestCollectionLog(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.log = self.engine.collection_log

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_starting_gear_recorded_on_first_turn(self):
        self.engine.advance_turn()
        items = self.log.obtained("items")
        self.assertIn("sword", items)   # starter kit
        self.assertIn("potion", items)

    def test_new_item_recorded_once(self):
        self.player.inventory.append(create_item("mithril_ore"))
        self.engine.advance_turn()
        self.engine.advance_turn()
        bucket = self.player.metadata["collection"]["items"]
        self.assertEqual(bucket.count("mithril_ore"), 1)

    def test_place_discovery_recorded_and_announced(self):
        loc = self.engine.world.locations[0]
        self.player.position = loc.center()
        # a corner may fall inside a nested location; record whatever the
        # innermost location at the player's tile actually is
        expected = self.engine.world.get_location_at(*self.player.position)
        self.engine.advance_turn()
        self.assertIn(expected.name, self.log.obtained("places"))
        history = " ".join(str(e) for e in
                           self.engine.memory_manager.game_history[-6:])
        self.assertIn("Discovered", history)

    def test_player_kill_recorded(self):
        from world.monsters import build_monster
        px, py = self.player.position
        wolf = build_monster("wolf", (px + 1, py))
        wolf.hp = 1
        self.engine.npc_manager.add_npc(wolf)
        for _ in range(40):
            self.engine.combat_system.player_attack(wolf.name)
            if not wolf.is_active():
                break
        self.assertIn("Wolf", self.log.obtained("kills"))

    def test_npc_on_npc_kill_not_credited_to_player(self):
        from world.monsters import build_monster
        a = build_monster("wolf", (50, 50))
        b = build_monster("goblin", (51, 50))
        b.hp = 1
        self.engine.npc_manager.add_npc(a)
        self.engine.npc_manager.add_npc(b)
        for _ in range(40):
            self.engine.combat_system.npc_attack(a, b.name, "attack")
            if not b.is_active():
                break
        self.assertNotIn("Goblin", self.log.obtained("kills"))

    def test_craft_recorded(self):
        self.player.inventory.append(create_item("raw_trout"))
        self.engine.craft("cooked_trout")
        self.assertIn("cooked_trout", self.log.obtained("crafts"))

    def test_totals_and_overlay(self):
        self.engine.advance_turn()
        totals = self.log.totals()
        self.assertGreater(totals["items"][0], 0)
        self.assertGreater(totals["items"][1], 80)
        lines = self.log.overlay_lines()
        self.assertTrue(lines[0].startswith("Collected"))
        self.assertTrue(any("Items" in ln for ln in lines))

    def test_collection_persists_in_saves(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.engine.advance_turn()
        before = self.log.obtained("items")
        self.assertTrue(before)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="c")
            self.player.metadata["collection"] = {}
            self.assertTrue(sm.load(self.engine, name="c"))
            self.assertEqual(
                self.engine.collection_log.obtained("items"), before)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
