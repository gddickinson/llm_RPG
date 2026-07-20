"""Fog-of-war dim overlay tracks the tile size (George 2026-07-18).

The explored-but-out-of-sight fog overlay was cached ONCE at the renderer's
construction tile_size, but zoom changes `tile_size` at runtime — so a stale
small overlay darkened only a corner of a bigger tile. `_dim_surface()` now
rebuilds it to the current size.
"""

import unittest

try:
    import pygame
    from ui.renderer import MapRenderer
    _OK = True
except Exception:                                    # pragma: no cover
    _OK = False


@unittest.skipUnless(_OK, "pygame not available")
class TestFogDim(unittest.TestCase):
    def test_overlay_matches_construction_size(self):
        r = MapRenderer(tile_size=32)
        self.assertEqual(r._dim_surface().get_size(), (32, 32))

    def test_overlay_rebuilds_on_zoom(self):
        r = MapRenderer(tile_size=32)
        r._dim_surface()                     # prime the cache at 32
        r.tile_size = 64                     # settings_panel.apply_setting('zoom', 64)
        self.assertEqual(r._dim_surface().get_size(), (64, 64),
                         "the dim overlay must follow the tile size, not a "
                         "stale construction size")
        r.tile_size = 48
        self.assertEqual(r._dim_surface().get_size(), (48, 48))

    def test_overlay_is_translucent_dark(self):
        r = MapRenderer(tile_size=48)
        px = r._dim_surface().get_at((0, 0))
        self.assertLess(px[0], 60)           # dark
        self.assertGreater(px[3], 0)         # semi-transparent (not opaque black)
        self.assertLess(px[3], 255)

    def test_dim_blit_covers_the_whole_tile_after_zoom(self):
        # end-to-end: an out-of-sight tile is dimmed across its FULL area once
        # zoomed, not just a construction-sized corner
        from engine.game_engine import GameEngine
        from engine import discovery
        from world.world_map import TerrainType
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        px, py = eng.player.position
        wmap = eng.world.map
        for y in range(max(0, py - 5), min(wmap.height, py + 6)):
            for x in range(max(0, px - 5), min(wmap.width, px + 6)):
                discovery._explored(eng).add((x, y))
        eng._visible_tiles = {(px, py)}            # only the hero's tile in sight
        r = MapRenderer(tile_size=32)              # constructed SMALL...
        r.tile_size = 64                           # ...then zoomed (the bug case)
        r.sprites.tile_size = 64
        sizes = []
        orig = r._dim_surface
        r._dim_surface = lambda: (sizes.append(orig().get_size()) or orig())
        target = pygame.Surface((832, 832))
        r.render(target, eng, pygame.Rect(0, 0, 832, 832))
        self.assertTrue(sizes, "some tiles were out of sight and dimmed")
        self.assertTrue(all(s == (64, 64) for s in sizes),
                        f"every dim overlay must be a full 64px tile: {set(sizes)}")
        try:
            eng.end_game()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
