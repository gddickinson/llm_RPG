"""Provocation tests — attacking a peaceful NPC makes it hostile
(George's playtest report, fixed alongside P9A.2)."""

import unittest

from engine.game_engine import GameEngine
from characters.factions import Faction, get_rep


class TestProvocation(unittest.TestCase):
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

    def _villager_beside_player(self):
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if getattr(n.character_class, "value", "") in
                   ("villager", "merchant") and n.is_active())
        wmap = self.engine.world.map
        px, py = self.player.position
        wmap.remove_character(npc)
        npc.position = (px + 1, py)
        wmap.place_character(npc, px + 1, py)
        return npc

    def test_attacking_a_villager_provokes_them(self):
        npc = self._villager_beside_player()
        self.engine.combat_system._resolve(self.player, npc)
        self.assertTrue(npc.metadata.get("provoked"))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertIn("turns on you", log)

    def test_assault_costs_villager_reputation(self):
        npc = self._villager_beside_player()
        npc.hp = npc.max_hp = 99   # a kill adds kill-rep on top
        before = get_rep(self.player, Faction.VILLAGERS)
        self.engine.combat_system._resolve(self.player, npc)
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before - 3)
        # ... but only once per provocation, not per swing
        self.engine.combat_system._resolve(self.player, npc)
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before - 3)

    def test_provoked_npc_fights_back(self):
        npc = self._villager_beside_player()
        npc.metadata["provoked"] = True
        from llm.providers.heuristic import HeuristicProvider
        provider = HeuristicProvider()
        response = provider.get_npc_action(
            npc, {}, [], "@ player nearby")
        self.assertEqual(response["action"], "attack")
        self.assertEqual(response["target"], "player")

    def test_provoked_npc_flees_at_low_hp(self):
        npc = self._villager_beside_player()
        npc.metadata["provoked"] = True
        npc.hp = max(1, int(npc.max_hp * 0.2))
        from llm.providers.heuristic import HeuristicProvider
        provider = HeuristicProvider()
        response = provider.get_npc_action(
            npc, {}, [], "@ player nearby")
        self.assertEqual(response["action"], "flee")

    def test_monsters_do_not_double_provoke(self):
        from world.monsters import build_monster
        wolf = build_monster("wolf", (self.player.position[0] + 1,
                                      self.player.position[1]))
        wolf.hp = wolf.max_hp = 99   # a kill would grant +rep instead
        self.engine.npc_manager.add_npc(wolf)
        before = get_rep(self.player, Faction.VILLAGERS)
        self.engine.combat_system._resolve(self.player, wolf)
        self.assertNotIn("provoked", wolf.metadata)
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before)

    def test_stand_down_when_player_leaves(self):
        npc = self._villager_beside_player()
        npc.metadata["provoked"] = True
        from llm.providers.heuristic import HeuristicProvider
        provider = HeuristicProvider()
        response = provider.get_npc_action(
            npc, {}, [], "empty street")
        self.assertNotEqual(response.get("action"), "attack")
        self.assertNotIn("provoked", npc.metadata)


if __name__ == "__main__":
    unittest.main()
