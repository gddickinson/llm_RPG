"""P33.4 — character motion & equipment: the drawn weapon/armour follows what
a character actually wields, and a strike animates.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_cm_"))

import unittest

from ui import char_motion as cm


class _Item:
    def __init__(self, name, wk="melee"):
        self.id = name.lower().replace(" ", "_")
        self.name = name
        self.weapon_kind = wk


class _Char:
    def __init__(self, klass="warrior", weapon=None, armor=None, shield=None):
        self.equipment = {"weapon": weapon, "armor": armor, "shield": shield}
        self.character_class = type("C", (), {"value": klass})()


class TestWeapon(unittest.TestCase):
    def test_worn_bow_draws_a_bow(self):
        self.assertEqual(cm.weapon_kind(_Char(weapon=_Item("Longbow", "ranged"))),
                         "bow")

    def test_worn_axe_beats_the_class_default(self):
        # a warrior (class default sword) actually wielding a greataxe → axe
        self.assertEqual(cm.weapon_kind(_Char("warrior",
                                              weapon=_Item("Greataxe"))), "axe")

    def test_magic_weapon_no_keyword_is_a_staff(self):
        self.assertEqual(cm.weapon_kind(_Char(weapon=_Item("Focus", "magic"))),
                         "staff")

    def test_unarmed_falls_back_to_class(self):
        self.assertEqual(cm.weapon_kind(_Char("warrior")), "sword")
        self.assertIsNone(cm.weapon_kind(_Char("villager")))


class TestArmor(unittest.TestCase):
    def test_metal_and_leather_and_none(self):
        base = (100, 100, 100)
        self.assertEqual(cm.armor_tint(_Char(armor=_Item("Plate Armor")), base),
                         cm.METAL_TINT)
        self.assertEqual(cm.armor_tint(_Char(armor=_Item("Leather Armor")), base),
                         cm.LEATHER_TINT)
        self.assertEqual(cm.armor_tint(_Char(), base), base)

    def test_has_shield(self):
        self.assertTrue(cm.has_shield(_Char(shield=_Item("Shield"))))
        self.assertFalse(cm.has_shield(_Char()))


class TestLunge(unittest.TestCase):
    def test_lunge_curve(self):
        self.assertEqual(cm.attack_lunge(0), 0.0)          # spent
        self.assertEqual(cm.attack_lunge(cm.ATTACK_DUR), 0.0)   # just started
        self.assertGreater(cm.attack_lunge(cm.ATTACK_DUR / 2), 0.9)  # mid-thrust

    def test_facing_tracks_movement(self):
        anim = {}
        cm.update_facing(anim, (5, 5), (6, 5))
        self.assertEqual(cm.facing(anim), (1, 0))
        cm.update_facing(anim, (6, 5), (6, 6))
        self.assertEqual(cm.facing(anim), (0, 1))
        cm.update_facing(anim, (6, 6), (6, 6))             # no move → unchanged
        self.assertEqual(cm.facing(anim), (0, 1))


class TestRenderSmoke(unittest.TestCase):
    def test_draw_body_with_equipment_and_attack(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((64, 64))
        from ui.body_renderer import draw_body, update_anim, _ensure_anim
        from engine.game_engine import GameEngine
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        p.equipment = {"weapon": _Item("Shortbow", "ranged"),
                       "armor": _Item("Leather Armor"), "shield": None}
        p.metadata["_atk_seq"] = 3           # pretend it just struck
        update_anim(p, 1.0 / 30.0)
        _ensure_anim(p)["atk_t"] = cm.ATTACK_DUR / 2   # mid-lunge
        surf = pygame.Surface((64, 64))
        draw_body(surf, p, 16, 16, 32, is_player=True)   # must not raise
        e.end_game()


if __name__ == "__main__":
    unittest.main()
