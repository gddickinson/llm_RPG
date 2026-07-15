"""Boss set-piece tests (P15.6): telegraphs + phase changes."""

import unittest

from engine.bosses import (boss_on_damaged, boss_tick, is_boss)
from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


class TestBosses(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 14, self.wmap.height - 10
        for y in range(self.oy - 4, self.oy + 6):
            for x in range(self.ox - 4, self.ox + 10):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _spawn(self, template, dx=5, dy=0):
        b = build_monster(template, (self.ox + dx, self.oy + dy))
        self.engine.npc_manager.add_npc(b)
        self.wmap.place_character(b, *b.position)
        return b

    def _put_player(self, x, y):
        self.wmap.remove_character(self.player)
        self.player.position = (x, y)
        self.wmap.place_character(self.player, x, y)

    def test_the_bosses_are_bosses(self):
        for t in ("giant_warlord", "tyrant_depths", "wisp_queen"):
            self.assertTrue(is_boss(self._spawn(t)),
                            f"{t} carries a boss block")
        self.assertFalse(is_boss(build_monster("wolf", (0, 0))))

    def test_telegraph_marks_then_blasts(self):
        warlord = self._spawn("giant_warlord", dx=5)
        self._put_player(self.ox, self.oy)
        # first tick: no prior mark -> aims at the player
        boss_tick(self.engine, warlord)
        self.assertEqual(warlord.metadata.get("boss_mark"),
                         [self.ox, self.oy])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-2:])
        self.assertIn("MOVE", log)
        # the player steps off; the next tick blasts empty ground
        self._put_player(self.ox, self.oy + 2)
        boss_tick(self.engine, warlord)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-3:])
        self.assertIn("empty ground", log)

    def test_standing_in_the_mark_hurts(self):
        warlord = self._spawn("giant_warlord", dx=5)
        self._put_player(self.ox, self.oy)
        boss_tick(self.engine, warlord)       # marks the player tile
        self.player.hp = self.player.max_hp
        boss_tick(self.engine, warlord)       # still there -> blast
        self.assertLess(self.player.hp, self.player.max_hp,
                        "you ate the telegraphed hit")

    def test_the_blast_maims_never_kills(self):
        warlord = self._spawn("giant_warlord", dx=5)
        self._put_player(self.ox, self.oy)
        boss_tick(self.engine, warlord)
        self.player.hp = 2
        boss_tick(self.engine, warlord)
        self.assertEqual(self.player.hp, 1)

    def test_the_tyrant_floods_its_den_at_half(self):
        tyrant = self._spawn("tyrant_depths", dx=3)
        n0 = len(self.engine.flood_system.floods)
        tyrant.hp = int(tyrant.max_hp * 0.9)
        boss_on_damaged(self.engine, tyrant)  # not yet
        self.assertEqual(len(self.engine.flood_system.floods), n0)
        tyrant.hp = int(tyrant.max_hp * 0.5)
        boss_on_damaged(self.engine, tyrant)
        self.assertGreater(len(self.engine.flood_system.floods), n0,
                           "half health opens the flood")

    def test_a_phase_fires_once(self):
        tyrant = self._spawn("tyrant_depths", dx=3)
        tyrant.hp = int(tyrant.max_hp * 0.5)
        boss_on_damaged(self.engine, tyrant)
        n1 = len(self.engine.flood_system.floods)
        tyrant.hp = int(tyrant.max_hp * 0.45)
        boss_on_damaged(self.engine, tyrant)
        self.assertEqual(len(self.engine.flood_system.floods), n1,
                         "the flood doesn't re-trigger")

    def test_the_wisp_queen_electrifies_and_summons(self):
        queen = self._spawn("wisp_queen", dx=3)
        n0 = sum(1 for m in self.engine.npc_manager.npcs.values()
                 if "Wisp" in m.name and m.is_active())
        queen.hp = int(queen.max_hp * 0.5)
        boss_on_damaged(self.engine, queen)
        # her pool is charged
        charged = any(s["kind"] == "electrified" for s in
                      self.engine.surfaces_layer.surfaces.values())
        self.assertTrue(charged, "the pool lit up")
        n1 = sum(1 for m in self.engine.npc_manager.npcs.values()
                 if "Wisp" in m.name and m.is_active())
        self.assertGreater(n1, n0, "her court answered")

    def test_the_warlord_enrages(self):
        warlord = self._spawn("giant_warlord", dx=5)
        str0 = warlord.strength
        warlord.hp = int(warlord.max_hp * 0.4)
        boss_on_damaged(self.engine, warlord)
        self.assertEqual(warlord.strength, str0 + 4,
                         "the warlord hits harder in his rage")

    def test_a_slain_boss_is_a_legend(self):
        queen = self._spawn("wisp_queen", dx=1)
        self._put_player(self.ox, self.oy)
        queen.hp = 1
        msg = self.engine.combat_system._handle_defeat(
            self.player, queen, damage=5)
        self.assertIn("defeated", msg.lower())
        self.assertFalse(queen.is_active())


if __name__ == "__main__":
    unittest.main()
