"""Crime & law II tests (P12.9): the ledger and the guard menu."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType


class _Rng:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestLaw(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.law = self.engine.law
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _confront(self, bounty=20):
        """Stage: bounty on the ledger, a guard at the elbow."""
        settlement = self.law.settlement_here()
        self.player.metadata["bounties"] = {settlement: bounty}
        self.player.metadata.pop("law_grace_until", None)
        guard = next(n for n in self.engine.npc_manager.npcs.values()
                     if n.is_active() and
                     getattr(n.character_class, "value", "")
                     in ("guard", "paladin"))
        px, py = self.player.position
        self.wmap.remove_character(guard)
        guard.position = (px + 1, py)
        self.wmap.place_character(guard, px + 1, py)
        self.law.check_contact()
        return guard, settlement

    def test_crimes_feed_the_ledger(self):
        self.law.add_bounty(10, reason="a test crime")
        self.assertEqual(self.law.bounty_here(), 10)
        self.law.add_bounty(5)
        self.assertEqual(self.law.bounty_here(), 15,
                         "the ledger accumulates")

    def test_forcing_a_door_is_on_the_books(self):
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors)
        self.engine.trespass._crime(loc, None, witnessed=False)
        self.assertGreater(self.law.bounty_here(), 0)

    def test_guard_contact_opens_the_menu(self):
        self._confront()
        self.assertIsNotNone(self.law.active)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("price on your head", log)

    def test_pay_clears_the_slate(self):
        self._confront(bounty=20)
        self.player.gold = 50
        self.law.resolve(1)
        self.assertEqual(self.player.gold, 30)
        self.assertEqual(self.law.bounty_here(), 0)
        self.assertIsNone(self.law.active)

    def test_jail_costs_time_and_skill(self):
        from engine.skill_progression import add_skill_xp
        add_skill_xp(self.player, "mining", 500)
        self._confront(bounty=20)
        t0 = self.engine.world.time
        gold0 = self.player.gold
        self.law.resolve(2)
        self.assertGreaterEqual(self.engine.world.time - t0,
                                12 * 60, "the day passes in a cell")
        self.assertEqual(self.player.gold, gold0, "jail keeps gold")
        self.assertEqual(self.law.bounty_here(), 0)
        self.assertLess(
            self.player.metadata["skills"]["mining"], 500,
            "idle hands dull the sharpest skill")

    def test_bribe_can_offend(self):
        self._confront(bounty=20)
        self.player.gold = 100
        self.engine.combat_system.rng = _Rng(roll=1)   # refused
        self.law.resolve(3)
        self.assertEqual(self.player.gold, 100,
                         "a refused bribe costs nothing but face")
        self.assertEqual(self.law.active["amount"], 25,
                         "the fine grows a quarter")
        self.engine.combat_system.rng = _Rng(roll=20)  # accepted
        self.law.resolve(3)
        self.assertEqual(self.law.bounty_here(), 0)
        self.assertEqual(self.player.gold, 85, "60% of 25 = 15g")

    def test_talk_once_with_degrees(self):
        self._confront(bounty=20)
        self.engine.combat_system.rng = _Rng(roll=20)  # crit story
        self.law.resolve(4)
        self.assertEqual(self.law.bounty_here(), 0,
                         "a crit story clears it free")
        guard, _ = self._confront(bounty=20)
        self.engine.combat_system.rng = _Rng(roll=5)   # heard it all
        self.law.resolve(4)
        msg = self.law.resolve(4)
        self.assertIn("done listening", msg,
                      "one story per confrontation")

    def test_resist_raises_the_price_in_blood(self):
        guard, settlement = self._confront(bounty=20)
        self.player.hp = self.player.max_hp
        self.engine.combat_system.rng = _Rng(roll=15)
        self.law.resolve(5)
        self.assertEqual(
            self.player.metadata["bounties"][settlement], 30,
            "resisting grows the bounty half again")
        self.assertLess(guard.get_relationship(self.player.id), 0)
        self.assertIsNone(self.law.active,
                          "you broke contact — for now")

    def test_walking_away_shelves_not_clears(self):
        guard, settlement = self._confront(bounty=20)
        self.wmap.remove_character(guard)
        guard.position = (2, 2)
        self.wmap.place_character(guard, 2, 2)
        self.law.check_contact()
        self.assertIsNone(self.law.active)
        self.assertEqual(
            self.player.metadata["bounties"][settlement], 20,
            "the ledger remembers")


if __name__ == "__main__":
    unittest.main()
