"""DM Tool API tests (P6.1) — powers, charter, budget, persistence."""

import unittest

from engine.game_engine import GameEngine
from engine.dm_api import MUTATION_BUDGET, MAX_BRUSH


class TestDMApi(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.dm = self.engine.dm
        self.player = self.engine.player

    def tearDown(self):
        # Clean runtime registries polluted by definitions
        from world.monsters import MONSTER_TEMPLATES
        from items.item_registry import ITEM_REGISTRY
        for tid in list(self.dm.defined_monsters):
            MONSTER_TEMPLATES.pop(tid, None)
        for iid in list(self.dm.defined_items):
            ITEM_REGISTRY.pop(iid, None)
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _far_spot(self):
        px, py = self.player.position
        wmap = self.engine.world.map
        return (min(wmap.width - 2, px + 20),
                min(wmap.height - 2, py + 20))

    # ---- powers ---------------------------------------------------------

    def test_define_and_spawn_monster(self):
        ok, note = self.dm.define_monster("dm_shade", {
            "name": "Gloom Shade", "class": "monster",
            "race": "goblin", "hp": 12,
            "level": self.player.level + 1, "symbol": "s",
            "description": "A drift of hungry shadow."})
        self.assertTrue(ok, note)
        ok, note = self.dm.spawn_npc("dm_shade", self._far_spot())
        self.assertTrue(ok, note)
        shades = [n for n in self.engine.npc_manager.npcs.values()
                  if n.name == "Gloom Shade"]
        self.assertEqual(len(shades), 1)

    def test_define_item_and_place(self):
        ok, note = self.dm.define_item("dm_moon_pendant", {
            "name": "Moonlit Pendant", "item_type": "amulet",
            "value": 300, "rarity": "rare",
            "equip_bonuses": {"wisdom": 1}})
        self.assertTrue(ok, note)
        spot = self._far_spot()
        ok, note = self.dm.place_item("dm_moon_pendant", spot)
        self.assertTrue(ok, note)
        items = self.engine.world.ground_items.get(spot, [])
        self.assertTrue(any(i.id == "dm_moon_pendant" for i in items))

    def test_create_quest_posts_to_board(self):
        ok, note = self.dm.create_quest("dm_shade_hunt", {
            "title": "Shadows in the Fen",
            "description": "Something hunts the reed-cutters.",
            "objectives": [{"type": "kill", "target": "monster",
                            "required": 1,
                            "description": "Slay the shade"}],
            "giver_id": "guard_01", "reward_gold": 50,
            "reward_xp": 80})
        self.assertTrue(ok, note)
        quest = self.engine.quest_manager.get("dm_shade_hunt")
        self.assertIsNotNone(quest)
        board = self.engine.quest_board_manager.board_at("Oakvale Tavern")
        self.assertIn("dm_shade_hunt", board.posted_quest_ids)

    def test_add_building_and_terrain(self):
        x, y = self._far_spot()
        ok, note = self.dm.add_building("The Mossy Shrine", x, y, 2, 2,
                                        "A shrine grown over with moss.")
        self.assertTrue(ok, note)
        names = [loc.name for loc in self.engine.world.locations]
        self.assertIn("The Mossy Shrine", names)
        ok, note = self.dm.edit_terrain(max(0, x - 4), y, 2, 2, "swamp")
        self.assertTrue(ok, note)

    def test_narrate_and_notebook(self):
        self.dm.narrate("A cold wind turns the weathervanes.")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-2:])
        self.assertIn("[DM]", log)
        self.assertTrue(any(e["command"] == "narrate" and e["ok"]
                            for e in self.dm.notebook))

    # ---- the charter --------------------------------------------------------

    def test_monster_level_cap(self):
        ok, note = self.dm.define_monster("dm_titan", {
            "name": "Titan", "class": "monster", "race": "troll",
            "hp": 99, "level": self.player.level + 10})
        self.assertFalse(ok)
        self.assertIn("cap", note)

    def test_no_spawning_on_the_player(self):
        px, py = self.player.position
        ok, note = self.dm.spawn_npc("wolf", (px + 1, py))
        self.assertFalse(ok)
        self.assertIn("charter", note)

    def test_no_burying_the_player(self):
        px, py = self.player.position
        ok, note = self.dm.add_building("Trap House", px, py, 2, 2)
        self.assertFalse(ok)
        ok, note = self.dm.edit_terrain(px, py, 1, 1, "mountain")
        self.assertFalse(ok)

    def test_brush_and_reward_caps(self):
        ok, note = self.dm.edit_terrain(0, 0, MAX_BRUSH + 1, 2, "grass")
        self.assertFalse(ok)
        ok, note = self.dm.create_quest("dm_gold", {
            "title": "Free Money", "objectives": [],
            "reward_gold": 9999})
        self.assertFalse(ok)

    def test_budget_exhaustion(self):
        for i in range(MUTATION_BUDGET):
            self.dm.adjust_faction("villagers", 1)
        ok, note = self.dm.adjust_faction("villagers", 1)
        self.assertFalse(ok)
        self.assertIn("budget", note)
        # Narration stays free
        ok, _ = self.dm.narrate("Still the rain falls.")
        self.assertTrue(ok)
        # A new day refills the budget
        self.engine.world.time += 24 * 60
        self.assertEqual(self.dm.budget_remaining(), MUTATION_BUDGET)

    # ---- beats + persistence --------------------------------------------------

    def test_scheduled_beat_fires_on_day_change(self):
        spot = self._far_spot()
        day = self.dm._day()
        ok, note = self.dm.schedule_beat(
            day + 1, "place_item", {"item_id": "potion",
                                    "position": spot})
        self.assertTrue(ok, note)
        self.engine.world.time = (day + 1) * 24 * 60 + 60
        self.engine.advance_turn()
        items = self.engine.world.ground_items.get(tuple(spot), [])
        self.assertTrue(any(i.id == "potion" for i in items))

    def test_definitions_survive_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.dm.define_monster("dm_shade2", {
            "name": "Second Shade", "class": "monster",
            "race": "goblin", "hp": 10, "level": 1})
        self.dm.define_item("dm_relic2", {
            "name": "Second Relic", "item_type": "misc", "value": 10})
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="dm")
            from world.monsters import MONSTER_TEMPLATES
            from items.item_registry import ITEM_REGISTRY
            MONSTER_TEMPLATES.pop("dm_shade2", None)
            ITEM_REGISTRY.pop("dm_relic2", None)
            self.dm.defined_monsters = {}
            self.dm.defined_items = {}
            self.assertTrue(sm.load(self.engine, name="dm"))
            self.assertIn("dm_shade2", MONSTER_TEMPLATES)
            self.assertIn("dm_relic2", ITEM_REGISTRY)
            self.assertIn("dm_shade2", self.engine.dm.defined_monsters)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
