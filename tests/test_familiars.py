"""Familiars (George: wizards & witches). A caster binds one familiar that
trails them and lends a passive magical gift — mana, mana regen, or sight."""

import unittest

from engine.game_engine import GameEngine
from engine import familiars
from ui.character_creator import CharacterSpec
from characters.character_types import CharacterClass, CharacterRace


def _engine(cls=CharacterClass.WIZARD, intel=16):
    spec = CharacterSpec(name="Mage", race=CharacterRace.HUMAN,
                         character_class=cls,
                         stats={"strength": 8, "dexterity": 10,
                                "constitution": 10, "intelligence": intel,
                                "wisdom": 12, "charisma": 10})
    e = GameEngine(llm_provider="heuristic", enable_npc_processes=False,
                   player_spec=spec)
    e.start_game()
    return e


class TestFamiliars(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_casters_can_bind_others_cannot(self):
        self.assertTrue(familiars.can_bind(self.p))
        w = _engine(CharacterClass.WARRIOR, intel=8)
        self.assertFalse(familiars.can_bind(w.player))
        w.end_game()

    def test_available_is_class_gated(self):
        wiz = {s for s, _ in familiars.available(self.p)}
        self.assertIn("cat", wiz)
        self.assertNotIn("imp", wiz)                 # warlock-only
        wl = _engine(CharacterClass.WARLOCK)
        warlock = {s for s, _ in familiars.available(wl.player)}
        self.assertIn("imp", warlock)
        wl.end_game()

    def test_bind_sets_and_replaces(self):
        familiars.bind(self.engine, "owl")
        self.assertEqual(familiars.active(self.p)["species"], "owl")
        familiars.bind(self.engine, "raven")
        self.assertEqual(familiars.active(self.p)["species"], "raven")

    def test_mana_max_gift_is_delta_safe(self):
        import engine.spells as spells
        spells.ensure_mana(self.p)
        base = self.p.metadata["max_mana"]
        familiars.bind(self.engine, "owl")           # +6 max mana
        spells.ensure_mana(self.p)
        self.assertEqual(self.p.metadata["max_mana"], base + 6)
        familiars.bind(self.engine, "raven")         # no mana gift
        spells.ensure_mana(self.p)
        self.assertEqual(self.p.metadata["max_mana"], base)
        familiars.dismiss(self.engine)
        spells.ensure_mana(self.p)
        self.assertEqual(self.p.metadata["max_mana"], base)

    def test_sight_gift_widens_visibility(self):
        v0 = self.engine.effective_visibility()
        familiars.bind(self.engine, "raven")         # +2 sight
        self.assertEqual(self.engine.effective_visibility(), v0 + 2)

    def test_mana_regen_bonus(self):
        familiars.bind(self.engine, "cat")
        self.assertEqual(familiars.familiar_bonus(self.p, "mana_regen"), 1)

    def test_follow_trails_the_caster(self):
        familiars.bind(self.engine, "cat")
        familiars.follow(self.p, (7, 9))
        self.assertEqual(list(familiars.active(self.p)["pos"]), [7, 9])

    def test_overlay_and_bind_index(self):
        lines = self.engine.familiar_overlay_lines()
        self.assertTrue(any("familiar" in l.lower() for l in lines))
        self.engine.familiar_bind_index(0)
        self.assertIsNotNone(familiars.active(self.p))

    def test_non_caster_bind_refused(self):
        w = _engine(CharacterClass.WARRIOR, intel=8)
        msg = familiars.bind(w, "cat")
        self.assertIn("magic", msg.lower())
        self.assertIsNone(familiars.active(w.player))
        w.end_game()


if __name__ == "__main__":
    unittest.main()
