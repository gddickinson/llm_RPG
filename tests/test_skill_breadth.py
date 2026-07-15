"""Skill breadth (P15.9b): new lattice skills, pets, teachers, use-sites."""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine                # noqa: E402
from engine.skill_progression import (SKILLS, get_skill_xp, train_skill,
                                      train_hunting, skill_name)  # noqa: E402
from engine.pets import PETS                             # noqa: E402
from engine.bonds import CLASS_TEACHES                   # noqa: E402
from items.item_registry import create_item             # noqa: E402
from world.monsters import build_monster                # noqa: E402
from world.location import Location                     # noqa: E402
from world.interiors import Interior                    # noqa: E402

NEW = ("bartering", "hunting", "carpentry")


class TestRegistration(unittest.TestCase):
    def test_new_skills_defined(self):
        for s in NEW:
            self.assertIn(s, SKILLS)
            self.assertTrue(skill_name(s))

    def test_each_has_a_pet(self):
        for s in NEW:
            self.assertIn(s, PETS)
            self.assertIn("name", PETS[s])

    def test_each_has_a_teacher(self):
        teaches = set(CLASS_TEACHES.values())
        for s in NEW:
            self.assertIn(s, teaches)
        self.assertEqual(CLASS_TEACHES["rogue"], "bartering")
        self.assertEqual(CLASS_TEACHES["barbarian"], "hunting")
        self.assertEqual(CLASS_TEACHES["artificer"], "carpentry")


class TestUseSites(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_train_skill_awards_xp(self):
        before = get_skill_xp(self.p, "bartering")
        train_skill(self.engine, "bartering", 10)
        self.assertEqual(get_skill_xp(self.p, "bartering"), before + 10)

    # ---- bartering: a completed trade -------------------------------

    def test_buying_trains_bartering(self):
        merchant = self.engine.npc_manager.get_npc("blacksmith_01")
        merchant.inventory.append(create_item("bread"))
        self.p.gold = 500
        before = get_skill_xp(self.p, "bartering")
        self.engine.economy_system._exec_buy_player("bread", merchant)
        self.assertGreater(get_skill_xp(self.p, "bartering"), before)

    def test_selling_trains_bartering(self):
        merchant = self.engine.npc_manager.get_npc("blacksmith_01")
        merchant.gold = 500
        self.p.inventory.append(create_item("bread"))
        before = get_skill_xp(self.p, "bartering")
        self.engine.economy_system._exec_sell_player("bread", merchant)
        self.assertGreater(get_skill_xp(self.p, "bartering"), before)

    # ---- hunting: felling a beast -----------------------------------

    def test_train_hunting_only_for_beasts(self):
        wolf = build_monster("wolf", (0, 0))
        before = get_skill_xp(self.p, "hunting")
        train_hunting(self.engine, wolf)
        self.assertGreater(get_skill_xp(self.p, "hunting"), before)

    def test_train_hunting_ignores_people(self):
        guard = self.engine.npc_manager.get_npc("blacksmith_01")
        before = get_skill_xp(self.p, "hunting")
        train_hunting(self.engine, guard)          # a person, not a beast
        self.assertEqual(get_skill_xp(self.p, "hunting"), before)

    def test_killing_a_beast_in_combat_trains_hunting(self):
        px, py = self.p.position
        wolf = build_monster("wolf", (px + 1, py))
        wolf.hp = 1
        self.engine.npc_manager.add_npc(wolf)
        before = get_skill_xp(self.p, "hunting")
        for _ in range(20):
            if not wolf.is_active():
                break
            self.engine.attack_character(wolf.name)
        self.assertFalse(wolf.is_active(), "the wolf should be slain")
        self.assertGreater(get_skill_xp(self.p, "hunting"), before)

    # ---- carpentry: repairing a home --------------------------------

    def test_repairing_a_home_trains_carpentry(self):
        from engine import homestead
        loc = Location("Old Shed", "A leaning shed.", 5, 5, 6, 5)
        loc.add_property("derelict", True)
        self.engine.world.locations.append(loc)
        inter = Interior(name="Old Shed", width=6, height=5,
                         description="Dust lies thick.", door=(3, 4))
        inter.init_grid()
        self.engine.interiors["Old Shed"] = inter
        self.engine.current_interior = inter
        self.p.position = (1, 1)
        self.p.gold = 500
        self.p.inventory.append(create_item("logs", 9))
        self.p.inventory.append(create_item("stone", 6))
        homestead.claim(self.engine)
        before = get_skill_xp(self.p, "carpentry")
        homestead.repair(self.engine)
        self.assertGreater(get_skill_xp(self.p, "carpentry"), before)


if __name__ == "__main__":
    unittest.main()
