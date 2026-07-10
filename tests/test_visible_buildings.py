"""Visible-building tests (P9A.3b) — George: 'I don't see any
difference in the buildings.'"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from engine.game_engine import GameEngine


class TestFurnitureSprites(unittest.TestCase):
    def setUp(self):
        import pygame
        pygame.init()
        from ui.sprite_loader import SpriteLoader
        self.sprites = SpriteLoader(tile_size=32)

    def test_every_furniture_kind_has_a_sprite(self):
        import pygame
        for name in ("Bed", "Chest", "Hearth", "Anvil", "Altar",
                     "Shelves", "Barrel", "Table", "Stairs up",
                     "Pew", "Statue", "Counter", "Crates"):
            surf = self.sprites.furniture(name)
            self.assertIsInstance(surf, pygame.Surface, name)
            self.assertTrue(surf.get_bounding_rect().width > 0,
                            f"{name} sprite must draw something")

    def test_sprites_are_distinct(self):
        import pygame
        bed = pygame.image.tostring(self.sprites.furniture("Bed"),
                                    "RGBA")
        anvil = pygame.image.tostring(
            self.sprites.furniture("Anvil"), "RGBA")
        self.assertNotEqual(bed, anvil)


class TestDoorGlyphs(unittest.TestCase):
    def test_all_states_have_colors(self):
        from ui.renderer import DOOR_STATE_COLORS
        for state in ("open", "closed", "locked", "broken"):
            self.assertIn(state, DOOR_STATE_COLORS)


class TestBumpAndNameplates(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.engine.world.time = 12 * 60

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _loc(self, fragment):
        return next(l for l in self.engine.world.locations
                    if fragment in l.name.lower()
                    and l.name in self.engine.interiors)

    def _put_player(self, x, y):
        wmap = self.engine.world.map
        player = self.engine.player
        wmap.remove_character(player)
        player.position = (x, y)
        wmap.place_character(player, x, y)

    def _door_tile(self, loc):
        return (loc.x + loc.width // 2, loc.y + loc.height - 1)

    def test_walls_are_solid(self):
        loc = self._loc("farmhouse")
        self._put_player(loc.x - 1, loc.y)
        moved = self.engine.player_actions.move(1, 0)
        self.assertFalse(moved, "building walls must block")
        self.assertEqual(self.engine.player.position,
                         (loc.x - 1, loc.y))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("walls of the", log.lower())

    def test_wall_message_once_per_day(self):
        loc = self._loc("farmhouse")
        self._put_player(loc.x - 1, loc.y)
        self.engine.player_actions.move(1, 0)
        self.engine.player_actions.move(1, 0)
        hits = [str(e) for e in
                self.engine.memory_manager.game_history
                if "walls of the" in str(e).lower()]
        self.assertEqual(len(hits), 1, "wall message must not spam")

    def test_bumping_the_door_enters_an_open_building(self):
        loc = self._loc("tavern")
        dx, dy = self._door_tile(loc)
        self._put_player(dx, dy + 1)
        self.engine.player_actions.move(0, -1)
        self.assertIsNotNone(self.engine.current_interior,
                             "bumping an open door must enter")
        self.assertIn("tavern",
                      self.engine.current_interior.name.lower())

    def test_bumping_a_locked_door_refuses(self):
        loc = self._loc("farmhouse")
        dx, dy = self._door_tile(loc)
        self._put_player(dx, dy + 1)
        self.engine.player_actions.move(0, -1)
        self.assertIsNone(self.engine.current_interior)
        self.assertEqual(self.engine.player.position, (dx, dy + 1))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("locked", log.lower())

    def test_nameplate_on_entry(self):
        loc = next(l for l in self.engine.world.locations
                   if "farmhouse" in l.name.lower()
                   and l.name in self.engine.interiors)
        owner = self.engine.homes.owner_of(loc.name)
        self.assertIsNotNone(owner)
        self.engine.door_manager.door(loc.name)["state"] = "open"
        wmap = self.engine.world.map
        wmap.remove_character(self.engine.player)
        self.engine.player.position = (loc.x, loc.y)
        wmap.place_character(self.engine.player, loc.x, loc.y)
        msg = self.engine.enter_building()
        self.assertIn(f"{owner.name}'s place", msg)

    def test_derelict_nameplate(self):
        derelicts = [l for l in self.engine.world.locations
                     if l.get_property("derelict", False)
                     and l.name in self.engine.interiors]
        if not derelicts:
            self.skipTest("no derelict building this world")
        loc = derelicts[0]
        self.engine.door_manager.door(loc.name)["state"] = "open"
        wmap = self.engine.world.map
        wmap.remove_character(self.engine.player)
        self.engine.player.position = (loc.x, loc.y)
        wmap.place_character(self.engine.player, loc.x, loc.y)
        msg = self.engine.enter_building()
        self.assertIn("abandoned", msg)


if __name__ == "__main__":
    unittest.main()
