"""Squad tactics tests (P7.3) — surrounds, focus fire, flanking."""

import unittest

from engine.game_engine import GameEngine
from engine.squad_tactics import (surround_step, flank_tile,
                                  player_focus_target, greedy_step)
from world.monsters import build_monster
from world.world_map import TerrainType


class TestSquadTactics(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map
        # A clear parade ground far from town
        self.ox, self.oy = self.wmap.width - 16, self.wmap.height - 16
        for y in range(self.oy, self.oy + 12):
            for x in range(self.ox, self.ox + 12):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put(self, char, x, y):
        self.wmap.remove_character(char)
        char.position = (x, y)
        self.wmap.place_character(char, x, y)
        return char

    def _spawn(self, template, x, y):
        npc = build_monster(template, (x, y))
        self.engine.npc_manager.add_npc(npc)
        self.wmap.place_character(npc, x, y)
        return npc

    def _mid(self, dx=0, dy=0):
        return self.ox + 6 + dx, self.oy + 6 + dy

    def test_pack_surrounds_instead_of_queueing(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        # Two wolves approaching from the same direction, in a line
        w1 = self._spawn("wolf", px + 2, py)
        w2 = self._spawn("wolf", px + 3, py)
        combat = self.engine.combat_system
        for _ in range(6):
            combat._step_toward(w1, self.engine.player)
            combat._step_toward(w2, self.engine.player)
        d1 = max(abs(w1.position[0] - px), abs(w1.position[1] - py))
        d2 = max(abs(w2.position[0] - px), abs(w2.position[1] - py))
        self.assertEqual(d1, 1, f"w1 not adjacent: {w1.position}")
        self.assertEqual(d2, 1, f"w2 must SURROUND, not queue behind "
                                f"w1: {w2.position}")
        self.assertNotEqual(w1.position, w2.position)

    def test_player_attack_records_focus_target(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        # Unique name — a same-named encounter wolf elsewhere on the
        # map would make name lookup ambiguous
        troll = self._spawn("wandering_troll", px + 1, py)
        self.engine.combat_system.player_attack(troll.name)
        self.assertIs(player_focus_target(self.engine), troll)

    def test_dead_target_clears_focus(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        wolf = self._spawn("wolf", px + 1, py)
        self.engine.player_target_id = wolf.id
        wolf.defeat()
        self.assertIsNone(player_focus_target(self.engine))

    def test_companion_focus_fires_players_target(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        comp = self.engine.npc_manager.get_npc("minstrel_01")
        comp.relationships[self.engine.player.id] = 50
        self._put(comp, px, py + 1)
        self.engine.recruit("minstrel_01")
        bystander = self._spawn("wolf", px - 1, py + 1)  # adjacent to comp
        target = self._spawn("wolf", px + 1, py + 1)     # also adjacent
        self.engine.player_target_id = target.id
        hp_target, hp_by = target.hp, bystander.hp
        # Swings can miss; keep updating until one lands on the target
        for _ in range(15):
            self.engine.companion_manager.update()
            self.assertEqual(bystander.hp, hp_by,
                             "companion must prefer the player's target")
            if target.hp < hp_target or not target.is_active():
                break
        self.assertTrue(target.hp < hp_target or not target.is_active(),
                        "companion never landed a hit in 15 swings")

    def test_companion_takes_the_flanking_tile(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        comp = self.engine.npc_manager.get_npc("minstrel_01")
        comp.relationships[self.engine.player.id] = 50
        self._put(comp, px + 4, py + 2)
        self.engine.recruit("minstrel_01")
        target = self._spawn("wolf", px + 1, py)   # east of player
        target.hp = target.max_hp = 99   # must survive the swings
        self.engine.player_target_id = target.id
        for _ in range(8):
            self.engine.companion_manager.update()
        self.assertEqual(comp.position, (px + 2, py),
                         "companion should stand opposite the player")
        bonus = self.engine.combat_system._flanking_bonus(
            self.engine.player, target)
        self.assertEqual(bonus, 2)

    def test_flank_tile_falls_back_when_blocked(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        target = self._spawn("wolf", px + 1, py)
        blocker = self._spawn("goblin", px + 2, py)   # on the flank spot
        comp = self.engine.npc_manager.get_npc("minstrel_01")
        self._put(comp, px + 1, py + 3)
        goal = flank_tile(self.engine, comp, target)
        self.assertIsNotNone(goal)
        self.assertNotEqual(goal, (px + 2, py))
        self.assertEqual(max(abs(goal[0] - (px + 1)),
                             abs(goal[1] - py)), 1,
                         "fallback must still be adjacent to the target")

    def test_greedy_step_slides_around_obstacles(self):
        px, py = self._mid()
        wolf = self._spawn("wolf", px, py)
        for y in (py - 1, py, py + 1):
            self.wmap.terrain[y][px + 1] = TerrainType.WATER
        moved = greedy_step(self.wmap, wolf, (px + 4, py))
        self.assertTrue(moved)
        self.assertNotEqual(wolf.position, (px, py))

    def test_surround_step_prefers_own_position(self):
        px, py = self._mid()
        self._put(self.engine.player, px, py)
        wolf = self._spawn("wolf", px + 1, py)
        self.assertEqual(
            surround_step(self.wmap, wolf, self.engine.player),
            (px + 1, py),
            "an attacker already adjacent must hold its ground")


if __name__ == "__main__":
    unittest.main()
