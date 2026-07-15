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
        # the potion is now carried — it may MERGE into a starting potion stack
        # (P25.1 stacking), so check by id rather than object identity
        self.assertTrue(
            any(getattr(it, "id", "") == "potion"
                for it in self.player.inventory))
        self.assertFalse(self.engine.world.get_items_at(*spot),
                         "the ground item should be gone after pickup")
        self.engine.current_interior = None


if __name__ == "__main__":
    unittest.main()


class TestBodyMarkers(unittest.TestCase):
    """George's second crash: string body markers in item APIs."""

    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_bodies_cannot_be_picked_up(self):
        p = self.engine.player
        x, y = p.position
        self.engine.world.add_item_to_ground("Wolf's body", x, y)
        msg = self.engine.pickup_item()
        self.assertIn("leave", msg.lower())
        self.assertFalse(any(isinstance(i, str)
                             for i in p.inventory))
        # the body stays for the shrine
        self.assertTrue(any("body" in str(i) for i in
                            self.engine.world.get_items_at(x, y)))

    def test_panel_equip_tolerates_strings(self):
        from ui.inventory_panel import InventoryPanel
        p = self.engine.player
        p.inventory.append("Wolf's body")   # legacy save could have one
        panel = InventoryPanel(self.engine)
        rows = panel.rows()
        panel.cursor = next(i for i, r in enumerate(rows)
                            if r[0] == "bag" and
                            isinstance(r[2], str))
        panel._equip_unequip(rows)     # must not raise
        panel._use(rows)               # must not raise
        p.inventory.remove("Wolf's body")


class TestWarArcFixes(unittest.TestCase):
    """PT3.3 findings."""

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

    def test_spell_kills_are_real_deaths(self):
        from world.monsters import build_monster
        wolf = build_monster("wolf", (self.player.position[0] + 1,
                                      self.player.position[1]))
        wolf.hp = wolf.max_hp = 5
        self.engine.npc_manager.add_npc(wolf)
        self.engine.world.map.place_character(wolf, *wolf.position)
        self.player.metadata["spells_known"] = ["fireball"]
        self.player.metadata["mana"] = 40
        self.player.metadata["max_mana"] = 40
        xp0 = self.player.metadata.get("xp", 0)
        msg = self.engine.cast_spell("fireball", wolf.name)
        self.assertIn("slain", msg.lower())
        self.assertFalse(wolf.is_active(),
                         "a spell-slain wolf must be DEAD, not a "
                         "0-HP zombie")
        self.assertGreater(self.player.metadata.get("xp", 0), xp0,
                           "spell kills must grant XP")

    def test_party_members_skip_scheduled_turns(self):
        mel = self.engine.npc_manager.get_npc("minstrel_01")
        mel.relationships[self.player.id] = 60
        wmap = self.engine.world.map
        wmap.remove_character(mel)
        mel.position = (self.player.position[0] + 1,
                        self.player.position[1])
        wmap.place_character(mel, *mel.position)
        self.engine.recruit("minstrel_01")
        pos = mel.position
        self.engine.turn_counter = 0
        self.engine.process_npc_turns()
        # she may step via the companion system, but never via the
        # schedule march that pulled her to the tavern mid-adventure
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertNotIn("Melody moves tavern", log)


class TestKillTargetMatching(unittest.TestCase):
    """PT3.4: 'monster' kill targets match any hostile class."""

    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_monster_target_matches_brigand_kills(self):
        ok, _ = self.engine.dm.create_quest("pt34_kill", {
            "title": "T", "description": "d",
            "objectives": [{"type": "kill", "target": "monster",
                            "required": 1, "description": "k"}],
            "giver_id": "guard_01", "reward_gold": 10,
            "reward_xp": 10})
        self.assertTrue(ok)
        self.engine.quest_manager.accept_quest("pt34_kill")
        self.engine.quest_manager.on_npc_defeated(
            "enc_bandit_abc123", "brigand")
        q = self.engine.quest_manager.get("pt34_kill")
        self.assertTrue(all(o.is_complete() for o in q.objectives),
                        "brigand kills must satisfy 'monster' "
                        "objectives")
