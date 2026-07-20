"""Dying & Wounded tests (P12.4)."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))


import unittest

from engine.dying import (DYING_MAX, dying_tick, enter_dying,
                          is_dying, is_person, wounded)
from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


class _FixedRng:
    def __init__(self, value, rand=0.5):
        self.value = value
        self.rand = rand

    def randint(self, a, b):
        return self.value

    def random(self):
        return self.rand


class TestDying(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.engine._has_gui = True
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 10, self.wmap.height - 8
        for y in range(self.oy - 2, self.oy + 3):
            for x in range(self.ox - 2, self.ox + 4):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _wolf(self):
        wolf = build_monster("wolf", (self.ox + 1, self.oy))
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        return wolf

    def test_zero_hp_starts_dying_not_defeat(self):
        wolf = self._wolf()
        self.player.hp = 1
        msg = self.engine.combat_system._handle_defeat(
            wolf, self.player, damage=5)
        self.assertIn("DYING 1/4", msg)
        self.assertTrue(is_dying(self.player))
        self.assertFalse(self.engine.player_dead)

    def test_recovery_checks_swing_both_ways(self):
        enter_dying(self.engine, self._wolf())
        self.engine.combat_system.rng = _FixedRng(5)   # fail: +1
        dying_tick(self.engine)
        self.assertEqual(self.player.metadata["dying"], 2)
        self.engine.combat_system.rng = _FixedRng(15)  # success: -1
        dying_tick(self.engine)
        self.assertEqual(self.player.metadata["dying"], 1)

    def test_stabilizing_wounds_and_resolves_gently(self):
        self.player.gold = 100
        enter_dying(self.engine, self._wolf())
        self.engine.combat_system.rng = _FixedRng(20, rand=0.4)
        dying_tick(self.engine)      # nat 20: -2 -> stabilized
        self.assertFalse(is_dying(self.player))
        self.assertEqual(wounded(self.player), 1)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertIn("stabilize", log.lower())
        self.assertFalse(self.engine.player_dead,
                         "stabilizing never slays")

    def test_wounded_starts_the_next_fall_deeper(self):
        self.player.metadata["wounded"] = 2
        msg = enter_dying(self.engine, self._wolf())
        self.assertIn("DYING 3/4", msg)

    def test_dying_four_hits_the_full_table(self):
        from engine.checkpoint import has_bloodstain
        enter_dying(self.engine, self._wolf())
        self.engine.combat_system.rng = _FixedRng(1, rand=0.05)
        dying_tick(self.engine)      # nat 1: +2 -> 3
        dying_tick(self.engine)      # -> 5 >= 4: the full table
        # soulslike: the bottom of the ladder is a bloodstain fall, not
        # a game-over
        self.assertFalse(self.engine.player_dead, "no game-over")
        self.assertTrue(has_bloodstain(self.engine),
                        "Dying 4 drops your pack and wakes you at sanctuary")

    def test_hits_while_down_worsen(self):
        wolf = self._wolf()
        enter_dying(self.engine, wolf)
        self.player.hp = 1
        msg = self.engine.combat_system._handle_defeat(
            wolf, self.player, damage=3)
        self.assertIn("DYING 2/4", msg)

    def test_downed_players_cannot_walk(self):
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)
        self.player.metadata["dying"] = 2
        self.engine.combat_system.rng = _FixedRng(15)
        moved = self.engine.player_actions.move(1, 0)
        self.assertFalse(moved)
        self.assertEqual(self.player.position, (self.ox, self.oy))

    def test_real_sleep_clears_wounded(self):
        from engine import rest
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self.wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        self.wmap.place_character(self.player, *self.player.position)
        self.player.gold = 100
        self.player.metadata["wounded"] = 2
        rest.sleep(self.engine)
        self.assertEqual(wounded(self.player), 0)


class TestKnockouts(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _person(self):
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if n.is_active() and is_person(n)
                   and self.wmap.get_character_at(*n.position) is n)
        npc.hp = 1
        npc.gold = 25
        return npc

    def test_people_are_knocked_out_not_killed(self):
        npc = self._person()
        pos = npc.position
        msg = self.engine.combat_system._handle_defeat(
            self.player, npc, damage=5)
        self.assertIn("senseless", msg)
        self.assertIn("ko_until", npc.metadata)
        ground = self.engine.world.get_items_at(*pos)
        self.assertTrue(any(str(g) == f"{npc.name}'s body"
                            for g in ground),
                        "the fight ends in a body")

    def test_bodies_can_be_robbed_and_remembered(self):
        npc = self._person()
        pos = npc.position
        self.engine.combat_system._handle_defeat(
            self.player, npc, damage=5)
        self.wmap.remove_character(self.player)
        self.player.position = pos
        self.wmap.place_character(self.player, *pos)
        gold0 = self.player.gold
        msg = self.engine.pickup_item()
        self.assertIn("pockets", msg)
        self.assertEqual(self.player.gold, gold0 + 25)
        self.assertEqual(npc.gold, 0)
        self.assertLess(npc.get_relationship(self.player.id), 0)

    def test_the_beaten_wake_with_grudges(self):
        from engine.dying import wake_the_fallen
        npc = self._person()
        pos = npc.position
        self.engine.combat_system._handle_defeat(
            self.player, npc, damage=5)
        self.engine.world.advance_time(7 * 60)
        woke = wake_the_fallen(self.engine)
        self.assertGreaterEqual(woke, 1)
        self.assertTrue(npc.is_active())
        self.assertGreaterEqual(npc.hp, 1)
        ground = self.engine.world.get_items_at(*pos)
        self.assertFalse(any(str(g) == f"{npc.name}'s body"
                             for g in ground),
                         "the body walked away")

    def test_monsters_still_die(self):
        wolf = build_monster("wolf", self.player.position)
        px, py = self.player.position
        wolf.position = (px + 1, py)
        wolf.hp = 1
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *wolf.position)
        msg = self.engine.combat_system._handle_defeat(
            self.player, wolf, damage=5)
        self.assertIn("defeated", msg)
        self.assertNotIn("ko_until", wolf.metadata)


class TestZombiePlayerReaper(unittest.TestCase):
    """A player dropped to 0 HP by a NON-combat leak (a mis-guarded hazard)
    must go DOWN the dying ladder, not walk the world at 0 HP — the bug an
    away/agent hero hit deep in the wild (George)."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.engine._has_gui = True     # survive-as-story, no headless end_game

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_zero_hp_player_is_routed_into_dying(self):
        p = self.engine.player
        p.hp = 0                        # simulate a non-combat leak to 0
        p.metadata.pop("dying", None)
        self.engine.advance_turn()      # the end-of-pipeline reaper runs
        # never a 0-HP 'alive, not dying' zombie afterward
        self.assertFalse(p.is_active() and p.hp <= 0
                         and p.metadata.get("dying", 0) <= 0,
                         "a 0-HP player must be dying, healed, or dead")

    def test_it_resolves_within_a_few_turns(self):
        p = self.engine.player
        p.hp = 0
        p.metadata.pop("dying", None)
        for _ in range(30):
            self.engine.advance_turn()
            if not (p.is_active() and p.hp <= 0):
                break
        self.assertFalse(p.is_active() and p.hp <= 0,
                         "the down player stabilizes, heals or dies — never "
                         "a permanent 0-HP wanderer")


if __name__ == "__main__":
    unittest.main()
