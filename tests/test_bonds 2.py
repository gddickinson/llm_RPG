"""Bond ceremony + faction threshold tests (P12.11)."""

import unittest

from characters.factions import Faction, set_rep, threshold
from engine.bonds import (JOIN_BASE, SECRET_COST, SKILL_COST, points,
                          share_drink, spend)
from engine.game_engine import GameEngine
from items.item_registry import create_item


class TestBondCeremony(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.goren = self.engine.npc_manager.get_npc("tavernkeeper_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _bond(self, npc=None, rel=40):
        npc = npc or self.goren
        npc.metadata.pop("bonded", None)
        npc.relationships[self.player.id] = rel
        self.player.inventory.append(create_item("ale"))
        return share_drink(self.engine, npc)

    def test_the_ceremony_needs_a_drink(self):
        self.player.inventory = []
        msg = share_drink(self.engine, self.goren)
        self.assertIn("needs a drink", msg)
        self.assertFalse(self.goren.metadata.get("bonded"))

    def test_sharing_the_cup_mints_bond(self):
        msg = self._bond(rel=40)
        self.assertIn("[Bond]", msg)
        self.assertEqual(points(self.engine, self.goren), 30,
                         "10 for the gesture + rel//2")
        self.assertFalse(any(getattr(i, "id", "") == "ale"
                             for i in self.player.inventory),
                         "the drink is shared, not kept")

    def test_once_per_npc_ever(self):
        self._bond()
        self.player.inventory.append(create_item("ale"))
        msg = share_drink(self.engine, self.goren)
        self.assertIn("already shared the cup", msg)
        self.assertEqual(points(self.engine, self.goren), 30,
                         "no double minting")

    def test_bond_buys_a_gated_secret(self):
        self._bond(rel=40)      # 30 points; Goren's secret gate is 15
        self.goren.relationships[self.player.id] = 0   # gate locked
        msg = spend(self.engine, self.goren, "secret")
        self.assertIn("[Secret]", msg)
        self.assertIn("silver", msg.lower(),
                      "trust opens what affinity gates lock")
        self.assertEqual(points(self.engine, self.goren),
                         30 - SECRET_COST)

    def test_bond_buys_a_lesson(self):
        self._bond(rel=70)      # 45 points
        xp0 = self.player.metadata.get("skills", {}).get("smithing", 0)
        msg = spend(self.engine, self.goren, "skill")
        self.assertIn("[Lesson]", msg)
        self.assertGreater(
            self.player.metadata["skills"]["smithing"], xp0)
        self.assertEqual(points(self.engine, self.goren),
                         45 - SKILL_COST)

    def test_bond_buys_company_past_the_trust_gate(self):
        bard = self.engine.npc_manager.get_npc("minstrel_01")
        self._bond(npc=bard, rel=60)     # 40 points
        bard.relationships[self.player.id] = 0   # no trust at all
        msg = spend(self.engine, bard, "join")
        self.assertIn("join you", msg)
        self.assertIn(bard.id, self.engine.companion_manager.party)
        gap = max(0, bard.level - self.player.level)
        self.assertEqual(points(self.engine, bard),
                         40 - (JOIN_BASE + 12 * gap))

    def test_spending_needs_the_ceremony_first(self):
        npc = self.engine.npc_manager.get_npc("blacksmith_01")
        npc.metadata.pop("bonded", None)
        msg = spend(self.engine, npc, "secret")
        self.assertIn("Share the cup first", msg)

    def test_insufficient_bond_refuses(self):
        self._bond(rel=0)       # 10 points < 15
        msg = spend(self.engine, self.goren, "secret")
        self.assertIn("Deepen the friendship", msg)
        self.assertEqual(points(self.engine, self.goren), 10,
                         "nothing charged on refusal")


class TestFactionThresholds(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_the_five_thresholds(self):
        for score, label in ((70, "revered"), (30, "favored"),
                             (0, "indifferent"), (-30, "disliked"),
                             (-80, "despised")):
            set_rep(self.player, Faction.VILLAGERS, score)
            self.assertEqual(threshold(self.player,
                                       Faction.VILLAGERS), label)

    def test_despised_merchants_refuse_trade(self):
        merchant = self.engine.npc_manager.get_npc("blacksmith_01")
        set_rep(self.player, Faction.MERCHANTS, -80)
        refusal = self.engine.shop_manager.trade_refusal(
            self.player, merchant)
        self.assertIsNotNone(refusal)
        self.assertIn("OUT", refusal)
        set_rep(self.player, Faction.MERCHANTS, 0)
        self.assertIsNone(self.engine.shop_manager.trade_refusal(
            self.player, merchant))

    def test_disliked_factions_refuse_recruitment(self):
        bard = self.engine.npc_manager.get_npc("minstrel_01")
        bard.relationships[self.player.id] = 90
        set_rep(self.player, Faction.BARDIC, -40)
        reason = self.engine.companion_manager.can_recruit(bard)
        self.assertIn("think too little", reason)

    def test_revered_guards_wave_off_petty_bounties(self):
        set_rep(self.player, Faction.GUARDS, 80)
        settlement = self.engine.law.settlement_here()
        self.player.metadata["bounties"] = {settlement: 10}
        from engine.law import outfit_signature
        self.player.metadata["crime_outfits"] = {
            settlement: outfit_signature(self.player)}
        self.player.metadata.pop("law_grace_until", None)
        guard = next(n for n in self.engine.npc_manager.npcs.values()
                     if n.is_active() and
                     getattr(n.character_class, "value", "")
                     == "guard")
        px, py = self.player.position
        self.engine.world.map.remove_character(guard)
        guard.position = (px + 1, py)
        self.engine.world.map.place_character(guard, px + 1, py)
        self.engine.law.check_contact()
        self.assertIsNone(self.engine.law.active)
        self.assertEqual(self.engine.law.bounty_here(), 0,
                         "forgotten, not just ignored")


if __name__ == "__main__":
    unittest.main()
