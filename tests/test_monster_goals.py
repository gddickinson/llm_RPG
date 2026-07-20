"""Monsters have GOALS & tribal AMBITIONS (George: monsters should have goals
and ambitions for themselves and their tribes). Individual drive-flavoured
goal strings on the templates + a shifting collective agenda per wild tribe."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster


class TestMonsterGoals(unittest.TestCase):
    def test_monsters_carry_drive_goals(self):
        # a built monster reads its own template goals, not the bare default
        for mid in ("wolf", "goblin", "elder_dragon", "vampire", "lich",
                    "bandit_chief", "ogre"):
            m = build_monster(mid, (1, 1))
            self.assertTrue(m.goals, mid)
            self.assertNotEqual(m.goals, ["Attack the player"], mid)

    def test_undead_and_predator_flavours_differ(self):
        wolf = build_monster("wolf", (1, 1))
        zombie = build_monster("zombie", (1, 1))
        self.assertNotEqual(wolf.goals, zombie.goals)
        self.assertTrue(any("pack" in g.lower() or "hunt" in g.lower()
                            or "weak" in g.lower() for g in wolf.goals))
        self.assertTrue(any("living" in g.lower() or "flesh" in g.lower()
                            for g in zombie.goals))


class TestTribalAgendas(unittest.TestCase):
    def setUp(self):
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()
        self.mt = self.e.monster_tribes
        self.mt._ensure()
        self.tid = list(self.mt._tribes().keys())[0]
        self.spec = self.mt._tribes()[self.tid]

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_every_tribe_has_an_agenda(self):
        for tid in self.mt._tribes():
            self.assertIn(self.mt.agenda_of(tid),
                          ("expand", "raid", "fortify", "plunder"))

    def test_agenda_shifts_with_fortune(self):
        # beaten low -> FORTIFY; war-ready -> RAID; dominant -> PLUNDER
        self.mt.strength[self.tid] = 10
        self.mt._shift_agenda(self.tid, self.spec)
        self.assertEqual(self.mt.agenda_of(self.tid), "fortify")
        self.mt.strength[self.tid] = self.spec.get("raid_threshold", 55)
        self.mt._shift_agenda(self.tid, self.spec)
        self.assertEqual(self.mt.agenda_of(self.tid), "raid")
        self.mt.strength[self.tid] = 90
        self.mt._shift_agenda(self.tid, self.spec)
        self.assertEqual(self.mt.agenda_of(self.tid), "plunder")

    def test_fortified_tribe_resists_defeat(self):
        from characters.character import Character
        raider = build_monster(self.spec.get("raider", "goblin"), (1, 1))
        raider.metadata["tribe"] = self.tid
        # fortify halves the hit
        self.mt.strength[self.tid] = 40
        self.mt.agenda[self.tid] = "fortify"
        self.mt.on_defeat(raider)
        fort_loss = 40 - self.mt.strength[self.tid]
        self.mt.strength[self.tid] = 40
        self.mt.agenda[self.tid] = "raid"
        self.mt.on_defeat(raider)
        raid_loss = 40 - self.mt.strength[self.tid]
        self.assertLess(fort_loss, raid_loss)

    def test_agenda_persists(self):
        self.mt.agenda[self.tid] = "plunder"
        d = self.mt.to_dict()
        mt2 = type(self.mt)(self.e)
        mt2.from_dict(d)
        self.assertEqual(mt2.agenda_of(self.tid), "plunder")


if __name__ == "__main__":
    unittest.main()
