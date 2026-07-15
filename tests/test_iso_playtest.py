"""P41.13 — iso end-to-end playtest: the isometric renderer stays crash-free and
draws content across real game states (overworld, combat, loot, surfaces, spells,
night/weather, interiors, dungeons).

`iso_render.dispatch` SWALLOWS a render error and returns False (falling back to
top-down). So asserting it returns True across every state is a strong guard: a
future change that breaks iso rendering in any of these states flips the return
to False and fails here — no silent regression.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_isoplay_"))

import unittest

import pygame

from ui import iso_render
from ui.renderer import MapRenderer


class TestIsoPlaytest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        os.environ.pop("LLM_RPG_RENDER", None)         # the setting governs
        from engine.game_engine import GameEngine
        from engine import settings
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()
        settings.set_setting(cls.engine.player, "renderer", "iso")
        px, py = cls.engine.player.position
        meta = cls.engine.player.metadata.setdefault("explored", set())
        for x in range(px - 14, px + 15):
            for y in range(py - 14, py + 15):
                meta.add((x, y))
        cls.r = MapRenderer(tile_size=40)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def _dispatch(self):
        surf = pygame.Surface((640, 480))
        surf.fill((0, 0, 0))
        view = pygame.Rect(0, 0, 640, 480)
        zone = self.r.active_zone(self.engine)
        ok = iso_render.dispatch(self.r, surf, self.engine, view, zone)
        return ok, surf

    def _assert_renders(self, label):
        ok, surf = self._dispatch()
        self.assertTrue(ok, f"iso render fell back (swallowed error): {label}")
        return surf

    def test_overworld_draws_varied_content(self):
        surf = self._assert_renders("overworld")
        colors = {surf.get_at((x, y))[:3]
                  for x in range(0, 640, 20) for y in range(0, 480, 20)}
        self.assertGreater(len(colors), 5,
                           "the iso overworld should draw varied 3D content")

    def test_iso_is_playable_across_states(self):
        from world.monsters import build_monster
        from items.item_registry import create_item
        eng = self.engine

        self._assert_renders("fresh overworld")
        for d in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            eng.move_player(*d)
            self._assert_renders(f"after move {d}")

        px, py = eng.player.position
        mob = build_monster("wolf", (px + 1, py))
        mob.id = "pt_iso_wolf"
        eng.npc_manager.add_npc(mob)
        eng.world.map.place_character(mob, px + 1, py)
        eng.player_target_id = mob.id
        try:
            self._assert_renders("monster adjacent + reticle lock")
            eng.combat_effects.on_damage_dealt(mob, 7, is_kill=False)
            eng.combat_effects.spawn_spell_burst("fireball", px + 1, py)
            eng.combat_effects.update(0.05)
            self._assert_renders("combat effects + spell burst")
            eng.world.ground_items[(px, py + 1)] = [create_item("sword")]
            eng.surfaces_layer.surfaces[(px - 1, py)] = {"kind": "fire"}
            self._assert_renders("loot + fire surface")
            eng.world.time = 2 * 60                     # night
            for m in type(eng.weather_system.state.current):
                if m.value == "fog":
                    eng.weather_system.state.current = m
                    break
            self._assert_renders("night + fog")
        finally:
            eng.world.map.remove_character(mob)
            eng.npc_manager.npcs.pop("pt_iso_wolf", None)
            eng.world.ground_items.pop((px, py + 1), None)
            eng.surfaces_layer.surfaces.pop((px - 1, py), None)
            eng.combat_effects.damage_popups.clear()
            eng.combat_effects.hit_flashes.clear()
            eng.combat_effects.death_effects.clear()
            eng.combat_effects.particles.clear()
            eng.player_target_id = None

    def test_interior_renders_in_iso(self):
        eng = self.engine
        loc = next((l for l in eng.world.locations
                    if l.name in eng.interiors), None)
        self.assertIsNotNone(loc, "the start world should have an interior")
        inter = eng.interiors[loc.name]
        prev = eng.current_interior
        eng.current_interior = inter
        keep = eng.player.position
        eng.player.position = getattr(inter, "door",
                                      (inter.width // 2, inter.height // 2))
        try:
            self._assert_renders(f"interior {loc.name}")
        finally:
            eng.current_interior = prev
            eng.player.position = keep

    def test_dungeon_renders_in_iso(self):
        eng = self.engine
        try:
            from world.dungeon import generate_dungeon
            dgn = generate_dungeon(seed=11)
        except Exception:
            self.skipTest("dungeon generation unavailable")
            return
        prev = eng.current_dungeon
        eng.current_dungeon = dgn
        keep = eng.player.position
        eng.player.position = getattr(dgn, "entrance",
                                      (dgn.width // 2, dgn.height // 2))
        try:
            self._assert_renders("dungeon level")
        finally:
            eng.current_dungeon = prev
            eng.player.position = keep


if __name__ == "__main__":
    unittest.main()
