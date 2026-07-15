"""Regression tests for playtest session 1 findings (P6.8)."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.world_map import TerrainType


class TestPlaytestFindings(unittest.TestCase):
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

    def _forest(self):
        wmap = self.engine.world.map
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.get_terrain_at(x, y) == TerrainType.FOREST:
                    return (x, y)
        return None

    def test_axe_owner_can_still_forage_herbs(self):
        """Finding 1: the woodcutting node shadowed forest foraging
        even on cooldown — buying an axe locked you out of herbs."""
        spot = self._forest()
        if spot is None:
            self.skipTest("no forest")
        self.player.inventory.append(create_item("crude_axe"))
        self.player.position = spot
        first = self.engine.forage()
        self.assertIn("chop", first.lower(), "axe chops first — fine")
        second = self.engine.forage()
        self.assertIn("forage", second.lower(),
                      "on chop cooldown, Z must fall through to herbs")

    def test_mining_cooldown_message_where_no_forage(self):
        """Mountains have no forage table — cooldown message remains."""
        wmap = self.engine.world.map
        spot = None
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.get_terrain_at(x, y) == TerrainType.ROAD and \
                        wmap.get_terrain_at(x + 1, y) == \
                        TerrainType.MOUNTAIN:
                    spot = (x, y)
                    break
            if spot:
                break
        if spot is None:
            self.skipTest("no road beside mountain")
        self.player.inventory.append(create_item("pickaxe"))
        self.player.position = spot
        self.engine.forage()
        msg = self.engine.forage()
        self.assertIn("picked clean", msg.lower())

    def test_tavern_intro_reachable_from_board(self):
        """Finding 2: tavern_intro had no giver and wasn't posted —
        completely unreachable."""
        board = self.engine.quest_board_manager.board_at(
            "Oakvale Tavern")
        available = [q.id for q in
                     self.engine.quest_board_manager.list_available(
                         board)]
        self.assertIn("tavern_intro", available)


if __name__ == "__main__":
    unittest.main()
