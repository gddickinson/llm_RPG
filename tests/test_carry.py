"""Carry capacity + PT3.2 explorer-arc fixes (George's reports)."""

import unittest

from engine.game_engine import GameEngine
from engine.carry import capacity, can_carry, full_message
from items.item_registry import create_item


class TestCarryCapacity(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _fill_pack(self):
        while can_carry(self.player):
            self.player.inventory.append(create_item("potion"))

    def test_capacity_scales_with_strength(self):
        self.player.strength = 10
        base = capacity(self.player)
        self.player.strength = 16
        self.assertGreater(capacity(self.player), base)
        self.player.strength = 4
        self.assertGreaterEqual(capacity(self.player), 8,
                                "even the weak can carry a little")

    def test_pickup_refuses_when_full(self):
        self._fill_pack()
        item = create_item("sword")
        x, y = self.player.position
        self.engine.world.add_item_to_ground(item, x, y)
        msg = self.engine.pickup_item()
        self.assertIn("pack is full", msg.lower())
        self.assertFalse(any(i is item for i in
                             self.player.inventory))

    def test_forage_refuses_when_full(self):
        from world.world_map import TerrainType
        self._fill_pack()
        wmap = self.engine.world.map
        for yy in range(wmap.height):
            for xx in range(wmap.width):
                if wmap.get_terrain_at(xx, yy) == TerrainType.FOREST \
                        and wmap.get_character_at(xx, yy) is None:
                    wmap.remove_character(self.player)
                    self.player.position = (xx, yy)
                    wmap.place_character(self.player, xx, yy)
                    msg = self.engine.forage()
                    self.assertIn("pack is full", msg.lower())
                    return

    def test_full_pack_keeps_chests_lootable(self):
        s = self.engine.structures
        key = "ruined_keep_test:1:1"
        s.chest_contents[key] = [create_item("potion")]
        # emulate loot with a full pack via the real API
        keep = next(i for n, i in self.engine.interiors.items()
                    if "ruined keep" in n.lower())
        crypt = keep.level_below
        chest = next(f for f in crypt.furniture
                     if f["name"] == "Chest")
        real_key = f"ruined_keep:{chest['x']}:{chest['y']}"
        s.chest_contents.setdefault(real_key,
                                    [create_item("potion")])
        self._fill_pack()
        msg = s.loot_chest(crypt, chest)
        self.assertIn("pack is full", msg.lower())
        self.assertNotIn(real_key, s.looted,
                         "chest must stay lootable for later")


class TestExplorerFixes(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_tome_teaches_fireball(self):
        tome = create_item("tome_of_fireball")
        self.player.inventory.append(tome)
        msg = self.engine.use_item(tome.name)
        self.assertIn("learn", msg.lower())
        self.assertIn("fireball",
                      self.player.metadata.get("spells_known", []))

    def test_tower_chest_holds_the_tome(self):
        tower = self.engine.interiors["Wizard's Tower"]
        obs = tower.level_above.level_above.level_above
        chest = next(f for f in obs.furniture if f["name"] == "Chest")
        key = f"wizard_tower:{chest['x']}:{chest['y']}"
        ids = [getattr(i, "id", "") for i in
               self.engine.structures.chest_contents.get(key, [])]
        self.assertIn("tome_of_fireball", ids)

    def test_keep_crypt_chest_never_empty(self):
        keep = next(i for n, i in self.engine.interiors.items()
                    if "ruined keep" in n.lower())
        crypt = keep.level_below
        chest = next(f for f in crypt.furniture
                     if f["name"] == "Chest")
        key = f"ruined_keep:{chest['x']}:{chest['y']}"
        self.assertTrue(self.engine.structures.chest_contents.get(key),
                        "the guardian must guard SOMETHING")

    def test_inventory_panel_tolerates_string_items(self):
        from ui.inventory_panel import InventoryPanel
        panel = InventoryPanel(self.engine)
        line = panel._render_row("bag", "", "Wolf's body", "  ")
        self.assertIn("Wolf's body", line)

    def test_pickup_works_indoors_beside_furniture(self):
        """George: furniture flavor shadowed indoor pickups."""
        inter = self.engine.interiors["Oakvale Tavern"]
        self.engine.current_interior = inter
        hearth = next(f for f in inter.furniture
                      if f["name"] == "Hearth")
        spot = (hearth["x"] + 1, hearth["y"])
        self.player.position = spot
        item = create_item("potion")
        self.engine.world.add_item_to_ground(item, *spot)
        # ground item underfoot must beat the adjacent hearth
        here = self.engine.world.get_items_at(*spot)
        self.assertTrue(here)
        msg = self.engine.pickup_item()
        self.assertIn("pick up", msg.lower())
        self.assertIn(item, self.player.inventory)
        self.engine.current_interior = None


if __name__ == "__main__":
    unittest.main()
