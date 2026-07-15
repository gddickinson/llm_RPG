"""P22.6 — non-blocking quick-cast (favourite slots + cast from play mode)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_quick_"))

import unittest

import pygame

from engine import quick_spells as qs


class TestSlots(unittest.TestCase):
    class _P:
        def __init__(self, known):
            self.metadata = {"spells_known": list(known)}

    def test_defaults_put_offensive_spells_first(self):
        p = self._P(["heal", "fireball", "bless"])
        qs.ensure_defaults(p)
        slots = qs.get_slots(p)
        self.assertEqual(slots[0], "fireball", "a damage spell ranks first")
        self.assertIn("heal", slots)

    def test_defaults_do_not_override_existing(self):
        p = self._P(["fireball"])
        p.metadata["quick_spells"] = ["heal"]
        qs.ensure_defaults(p)
        self.assertEqual(qs.get_slots(p), ["heal"])

    def test_set_and_read_slot(self):
        p = self._P([])
        qs.set_slot(p, 2, "frost_bolt")
        self.assertEqual(qs.slot_spell(p, 2), "frost_bolt")
        self.assertIsNone(qs.slot_spell(p, 0))

    def test_slots_are_capped(self):
        p = self._P([])
        qs.set_slot(p, qs.MAX_SLOTS + 3, "nope")   # out of range → ignored
        self.assertEqual(qs.get_slots(p), [])

    def test_no_known_spells_leaves_slots_empty(self):
        p = self._P([])
        qs.ensure_defaults(p)
        self.assertFalse(any(qs.get_slots(p)))


class TestQuickCast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def setUp(self):
        from engine.spells import ensure_mana
        p = self.engine.player
        p.metadata["spells_known"] = ["fireball", "heal"]
        p.metadata.pop("quick_spells", None)
        ensure_mana(p)
        p.metadata["mana"] = 80

    def test_empty_slot_is_graceful(self):
        self.engine.player.metadata["quick_spells"] = []
        self.engine.player.metadata["spells_known"] = []
        msg = qs.quick_cast(self.engine, 0)
        self.assertIn("empty", msg.lower())

    def test_quick_heal_restores_hp(self):
        p = self.engine.player
        qs.ensure_defaults(p)
        slots = qs.get_slots(p)
        self.assertIn("heal", slots)
        p.hp = max(1, p.max_hp - 20)
        before = p.hp
        qs.quick_cast(self.engine, slots.index("heal"))
        self.assertGreater(p.hp, before, "quick heal should restore HP")

    def test_quick_damage_hits_a_nearby_hostile(self):
        from world.monsters import build_monster
        eng = self.engine
        p = eng.player
        qs.ensure_defaults(p)
        slots = qs.get_slots(p)
        px, py = p.position
        mob = build_monster("goblin", (px + 1, py))
        mob.id = "qc_goblin"
        mob.hp = mob.max_hp = 30
        eng.npc_manager.add_npc(mob)
        eng.world.map.place_character(mob, px + 1, py)
        try:
            before = mob.hp
            msg = qs.quick_cast(eng, slots.index("fireball"))
            self.assertLess(mob.hp, before,
                            f"quick fireball should hit the goblin: {msg}")
        finally:
            eng.world.map.remove_character(mob)
            eng.npc_manager.npcs.pop("qc_goblin", None)

    def test_no_target_is_graceful(self):
        # no hostile anywhere near → a damage quick-cast fails cleanly
        eng = self.engine
        qs.ensure_defaults(eng.player)
        slots = qs.get_slots(eng.player)
        msg = qs.quick_cast(eng, slots.index("fireball"))
        self.assertIsInstance(msg, str)
        self.assertTrue(len(msg) > 0)


class TestQuickbarHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_quickbar_paints_for_a_caster(self):
        from ui.quickbar import draw_quickbar

        class _P:
            metadata = {"spells_known": ["fireball", "heal"],
                        "mana": 50, "max_mana": 50}
        class _Eng:
            player = _P()
        surf = pygame.Surface((400, 300))
        surf.fill((0, 0, 0))
        font = pygame.font.SysFont("monospace", 12)
        draw_quickbar(surf, _Eng(), pygame.Rect(0, 0, 400, 300), font)
        painted = sum(1 for x in range(0, 200, 3) for y in range(0, 80, 3)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 20, "the quick-cast bar should draw")

    def test_quickbar_silent_for_non_caster(self):
        from ui.quickbar import draw_quickbar

        class _P:
            metadata = {"spells_known": []}
        class _Eng:
            player = _P()
        surf = pygame.Surface((400, 300))
        surf.fill((0, 0, 0))
        font = pygame.font.SysFont("monospace", 12)
        draw_quickbar(surf, _Eng(), pygame.Rect(0, 0, 400, 300), font)
        painted = sum(1 for x in range(0, 400, 5) for y in range(0, 300, 5)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertEqual(painted, 0, "no bar for a non-caster")


class TestSpellbookRail(unittest.TestCase):
    """George: the spellbook must not cover the main screen."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()
        cls.engine.player.metadata["spells_known"] = ["fireball", "heal"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_panel_is_a_right_rail_leaving_the_field_visible(self):
        from ui.spell_panel import SpellPanel
        W, H = 800, 600
        surf = pygame.Surface((W, H))
        bg = (46, 74, 52)
        surf.fill(bg)
        SpellPanel(self.engine).draw(surf, pygame.Rect(0, 0, W, H))
        # the LEFT half stays the untouched battlefield background
        left = sum(1 for x in range(0, W // 2, 12) for y in range(0, H, 12)
                   if surf.get_at((x, y))[:3] != bg)
        self.assertEqual(left, 0, "the spellbook must not cover the field")
        # the RIGHT edge carries the panel
        right = sum(1 for x in range(3 * W // 4, W, 8)
                    for y in range(0, H, 12)
                    if surf.get_at((x, y))[:3] != bg)
        self.assertGreater(right, 20, "the spellbook rail should draw at right")


if __name__ == "__main__":
    unittest.main()
