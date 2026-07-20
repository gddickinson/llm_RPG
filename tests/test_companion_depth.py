"""Companion depth tests (P15.5): banter, orders, bonds, the watch."""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.world_map import TerrainType


class TestCompanionDepth(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.melody = self.engine.npc_manager.get_npc("minstrel_01")
        self.engine.companion_manager.party.append("minstrel_01")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_the_road_talks(self):
        from characters.companions import BANTER_EVERY
        self.player.metadata["banter_turn"] = 0
        self.engine.turn_counter = BANTER_EVERY + 1
        self.engine.companion_manager.banter_tick()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-2:])
        self.assertIn("Melody", log, "an authored line, hers")

    def test_banter_is_rare_not_spam(self):
        self.player.metadata["banter_turn"] = self.engine.turn_counter
        n0 = len(self.engine.memory_manager.game_history)
        self.engine.companion_manager.banter_tick()
        self.assertEqual(len(self.engine.memory_manager.game_history),
                         n0, "quiet between lines")

    def test_orders_hold_and_flee(self):
        cm = self.engine.companion_manager
        msg = cm.set_order(self.melody, "hold")
        self.assertIn("hold", msg.lower())
        self.assertEqual(self.melody.metadata["order"], "hold")
        msg = cm.set_order(self.melody, "waltz")
        self.assertIn("/order", msg, "unknown orders teach the menu")

    def test_holding_companions_do_not_follow(self):
        ox, oy = self.wmap.width - 8, self.wmap.height - 6
        for x in range(ox - 6, ox + 2):
            self.wmap.terrain[oy][x] = TerrainType.GRASS
            ch = self.wmap.get_character_at(x, oy)
            if ch is not None:
                self.wmap.remove_character(ch)
        self.wmap.remove_character(self.melody)
        self.melody.position = (ox - 5, oy)
        self.wmap.place_character(self.melody, ox - 5, oy)
        self.wmap.remove_character(self.player)
        self.player.position = (ox, oy)
        self.wmap.place_character(self.player, ox, oy)
        # full HP so M.10b self-preservation (a badly-hurt companion breaks off
        # even on hold) doesn't fire — this test is about ORDER obedience, and
        # the preset's HP can otherwise vary by RNG order (a suite flake)
        self.melody.hp = self.melody.max_hp
        self.melody.metadata["order"] = "hold"
        pos0 = self.melody.position
        self.engine.companion_manager.update()
        self.assertEqual(self.melody.position, pos0,
                         "held ground is held")
        self.melody.metadata["order"] = "follow"
        self.engine.companion_manager.update()
        self.assertNotEqual(self.melody.position, pos0,
                            "follow resumes on the word")

    def test_ordering_a_stranger_fails(self):
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        px, py = self.player.position
        self.wmap.remove_character(goren)
        goren.position = (px + 1, py)
        self.wmap.place_character(goren, px + 1, py)
        msg = self.engine.dialog_system.player_to_npc(
            "tavernkeeper_01", "/order hold")
        self.assertIn("doesn't take orders", msg)

    def test_personal_quest_hides_until_the_bond(self):
        qm = self.engine.quest_manager
        offered = [q.id for q in qm.offered_by("minstrel_01")]
        self.assertNotIn("melodys_lost_ballad", offered,
                         "strangers don't hear the lost ballad")
        # share the cup and mint enough bond
        self.melody.metadata.pop("bonded", None)
        self.melody.relationships[self.player.id] = 40
        self.player.inventory.append(create_item("ale"))
        from engine.bonds import share_drink
        share_drink(self.engine, self.melody)   # 30 bond, high-water
        offered = [q.id for q in qm.offered_by("minstrel_01")]
        self.assertIn("melodys_lost_ballad", offered,
                      "the bond opens her story")

    def test_spending_bond_keeps_the_quest_open(self):
        self.melody.metadata.pop("bonded", None)
        self.melody.relationships[self.player.id] = 40
        self.player.inventory.append(create_item("ale"))
        from engine.bonds import share_drink, spend
        share_drink(self.engine, self.melody)   # 30
        spend(self.engine, self.melody, "skill")  # down to 5
        offered = [q.id for q in
                   self.engine.quest_manager.offered_by("minstrel_01")]
        self.assertIn("melodys_lost_ballad", offered,
                      "trust once earned is not unearned by spending")

    def test_a_companion_stands_watch(self):
        from engine.camping import camp
        ox, oy = self.wmap.width - 8, self.wmap.height - 6
        for y in range(oy - 1, oy + 2):
            for x in range(ox - 1, ox + 2):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (ox, oy)
        self.wmap.place_character(self.player, ox, oy)
        self.player.inventory = [create_item("bread")
                                 for _ in range(3)]

        class _R:
            def random(self):
                return 0.15    # ambush at 0.25, safe at 0.10

            def randint(self, a, b):
                return a

        self.engine.combat_system.rng = _R()
        lines = camp(self.engine)
        joined = " ".join(lines)
        self.assertIn("first watch", joined)
        self.assertNotIn("prowled the camp", joined,
                         "the watch kept the wolf off")


if __name__ == "__main__":
    unittest.main()
