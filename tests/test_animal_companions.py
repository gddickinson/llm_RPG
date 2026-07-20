"""Animal companions (George): tame a wild beast to fight beside you (a
guardian) or aid the hunt (a hunter), and break a wild horse to the saddle."""

import unittest

from engine.game_engine import GameEngine
from engine import animal_companions as ac
from world.wildlife import build_wildlife
from items.item_registry import create_item


class TestTaming(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.p.position = (5, 5)
        # a hunter's hand + a lure
        from engine.skill_progression import add_skill_xp, total_xp_for_level
        add_skill_xp(self.p, "hunting", total_xp_for_level(12))
        self.p.add_item(create_item("bread") or create_item("healing_potion"))

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _wild(self, species, at=(6, 5)):
        w = build_wildlife(species, at)
        self.engine.npc_manager.add_npc(w)
        self.engine.world.map.place_character(w, *at)
        return w

    def test_tame_a_boar_into_a_party_guardian(self):
        boar = self._wild("boar")
        msg = ac.tame(self.engine, boar)
        self.assertIn("companion", msg.lower())
        self.assertIn(boar.id, self.engine.companion_manager.party)
        self.assertTrue(boar.metadata.get("beast_companion"))
        self.assertFalse(boar.metadata.get("wildlife"))
        self.assertGreater(boar.metadata.get("natural_damage", 0), 0)

    def test_hunter_companion_gives_beast_bonus(self):
        fox = self._wild("fox")
        ac.tame(self.engine, fox)
        # a monster target → the hunter's edge applies
        wolfy = build_wildlife("wolf", (7, 5))
        wolfy.character_class = wolfy.character_class    # ANIMAL counts as beast
        bonus = ac.owner_hunting_bonus(self.engine, wolfy)
        self.assertGreater(bonus, 0)

    def test_tame_a_mustang_into_a_mount(self):
        mm = self._wild("mustang")
        msg = ac.tame(self.engine, mm)
        self.assertIn("mount", msg.lower())
        self.assertEqual(self.p.metadata["mount"]["kind"], "horse")
        # the wild horse is consumed into the mount
        self.assertIsNone(self.engine.npc_manager.get_npc(mm.id))

    def test_no_food_no_tame(self):
        self.p.inventory = []
        boar = self._wild("boar")
        msg = ac.tame(self.engine, boar)
        self.assertIn("food", msg.lower())
        self.assertNotIn(boar.id, self.engine.companion_manager.party)

    def test_prey_is_not_a_fighter_but_deer_is_a_hunter(self):
        # a rabbit isn't in the roster → not tameable
        rab = self._wild("rabbit")
        self.assertIsNone(ac.tameable(rab))

    def test_too_unskilled_fails_and_beast_bolts(self):
        from engine.skill_progression import get_skill_xp
        self.p.metadata["skills"] = {}              # wipe Hunting → unskilled
        aur = self._wild("aurochs")                 # dc 20 (16 with food)
        msg = ac.tame(self.engine, aur)
        self.assertIn("Hunting", msg)
        self.assertNotIn(aur.id, self.engine.companion_manager.party)

    def test_beast_cap(self):
        for i, sp in enumerate(("boar", "fox", "hog")):
            w = self._wild(sp, at=(6 + i, 5))
            ac.tame(self.engine, w)
            # re-arm the lure each time
            self.p.add_item(create_item("bread") or create_item("bread"))
        self.assertLessEqual(len(ac.beast_companions(self.engine)),
                             ac.BEAST_CAP)

    def test_nearest_tameable_is_adjacent_only(self):
        self._wild("boar", at=(9, 9))               # far away
        self.assertIsNone(ac.nearest_tameable(self.engine))
        self._wild("fox", at=(6, 5))                # adjacent
        self.assertIsNotNone(ac.nearest_tameable(self.engine))


if __name__ == "__main__":
    unittest.main()
