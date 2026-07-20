"""Tactical verbs: opportunity attacks, disengage, shove, aimed shot (P5.3)."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType


def _open_ground(engine, need=4):
    """A run of open grass tiles; returns the west end."""
    wmap = engine.world.map
    for y in range(2, wmap.height - 2):
        for x in range(2, wmap.width - 2 - need):
            if all(wmap.get_terrain_at(x + i, y) == TerrainType.GRASS
                   for i in range(need)):
                return (x, y)
    return None


class TestTactics(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        spot = _open_ground(self.engine)
        if spot is None:
            self.skipTest("no open ground")
        self.spot = spot
        self.engine.world.map.remove_character(self.player)
        self.player.position = spot
        self.engine.world.map.place_character(self.player, *spot)
        # Clear any WORLD npc near the spot: adjacent_hostiles reads the NPC
        # MANAGER, so a wandering interloper (e.g. a goblin) would steal the shove
        # target or block the push tile — a full-suite flake, same class as the
        # cleave phantom-foe one (test_combat_depth).
        for n in list(self.engine.npc_manager.npcs.values()):
            if (abs(n.position[0] - spot[0]) <= 3
                    and abs(n.position[1] - spot[1]) <= 3):
                self.engine.world.map.remove_character(n)
                self.engine.npc_manager.remove_npc(n.id)
        # A wolf adjacent to the east
        self.wolf = build_monster("wolf", (spot[0] + 1, spot[1]))
        self.engine.npc_manager.add_npc(self.wolf)
        self.engine.world.map.place_character(self.wolf,
                                              *self.wolf.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _log_since(self, n0):
        # Only the events THIS action added — a fixed last-N window is too
        # small once the move-turn also emits encounter/weather/attack noise
        # that buries the opportunity-attack line (the historic flake).
        return " ".join(str(e) for e in
                        self.engine.memory_manager.game_history[n0:])

    def test_retreat_provokes_opportunity_attack(self):
        n0 = len(self.engine.memory_manager.game_history)
        moved = self.engine.move_player(-1, 0)   # step away west
        self.assertTrue(moved)
        self.assertIn("lashes out", self._log_since(n0))

    def test_careful_disengage_avoids_the_strike(self):
        t0 = self.engine.world.time
        n0 = len(self.engine.memory_manager.game_history)
        moved = self.engine.move_player(-1, 0, careful=True)
        self.assertTrue(moved)
        self.assertNotIn("lashes out", self._log_since(n0))
        self.assertGreaterEqual(self.engine.world.time - t0, 2,
                                "care costs extra time")

    def test_moving_within_melee_does_not_provoke(self):
        # Step north: wolf is still within 1 (diagonal) — no strike
        n0 = len(self.engine.memory_manager.game_history)
        self.engine.move_player(0, -1)
        self.assertNotIn("lashes out", self._log_since(n0))

    def test_shove_pushes_enemy_back(self):
        from engine.tactics import shove
        import random
        rig = random.Random()
        rolls = iter([15, 8])   # player wins by 7 — a plain success
        rig.randint = lambda a, b: next(rolls)
        before = self.wolf.position
        msg = shove(self.engine, rng=rig)
        self.assertIn("staggering", msg)
        self.assertEqual(self.wolf.position,
                         (before[0] + 1, before[1]))

    def test_failed_shove_holds_ground(self):
        from engine.tactics import shove
        import random
        rig = random.Random()
        rolls = iter([8, 15])   # player loses by 7 — no counter-crit
        rig.randint = lambda a, b: next(rolls)
        before = self.wolf.position
        msg = shove(self.engine, rng=rig)
        self.assertIn("hold", msg)
        self.assertEqual(self.wolf.position, before)

    def test_shove_without_adjacent_enemy(self):
        from engine.tactics import shove
        self.wolf.position = (self.spot[0] + 20, self.spot[1])
        # clear any OTHER creature the world seeded near this spot (a lair
        # occupant / bones ghost), so "no adjacent enemy" really holds
        for n in list(self.engine.npc_manager.npcs.values()):
            if abs(n.position[0] - self.spot[0]) <= 2 and \
                    abs(n.position[1] - self.spot[1]) <= 2:
                self.engine.world.map.remove_character(n)
        msg = shove(self.engine)
        self.assertIn("No enemy", msg)

    def test_aimed_shot_bonus_damage_and_time(self):
        from items.item_registry import create_item
        from characters import equipment as eq
        bow = create_item("bow")
        arrows = create_item("arrow", quantity=5)
        self.player.inventory += [bow, arrows]
        eq.equip(self.player, bow)
        t0 = self.engine.world.time
        n0 = len(self.engine.memory_manager.game_history)
        msg = self.engine.shoot_ranged(aimed=True)
        self.assertIn("loose", msg)
        self.assertGreaterEqual(self.engine.world.time - t0, 2)
        self.assertIn("careful aim", self._log_since(n0))


class TestGrappleThrow(TestTactics):
    """I3 — grapple (clinch) and throw an adjacent foe (wrestling / throwing)."""

    def _prep(self):
        # deterministic contest: pin the combatants' stats + freeze the world
        # tick (so pursuit/predation can't perturb positions mid-assert)
        self.player.strength = 14
        self.wolf.strength = 10
        self.wolf.dexterity = 10
        self.engine.advance_turn = lambda *a, **k: None
        px, py = self.player.position       # the wolf is the ONLY adjacent foe
        for n in list(self.engine.npc_manager.npcs.values()):
            if n is self.wolf:
                continue
            if max(abs(n.position[0] - px), abs(n.position[1] - py)) <= 1:
                self.engine.world.map.remove_character(n)
                self.engine.npc_manager.remove_npc(n.id)

    def _rig(self, rolls):
        import random
        rig = random.Random()
        it = iter(rolls)
        rig.randint = lambda a, b: next(it)
        return rig

    def test_grapple_seizes_the_foe(self):
        from engine.tactics import grapple, is_grappling
        from characters.status_effects import has_effect
        self._prep()
        msg = grapple(self.engine, rng=self._rig([10, 6]))   # margin +6, plain win
        self.assertIn("grapple", msg.lower())
        self.assertTrue(has_effect(self.wolf, "off_guard"))
        self.assertEqual(self.player.metadata.get("grappling"), self.wolf.id)
        self.assertTrue(is_grappling(self.engine))

    def test_firm_grapple_pins_prone(self):
        from engine.tactics import grapple
        from characters.status_effects import has_effect
        self._prep()
        msg = grapple(self.engine, rng=self._rig([19, 1]))   # a decisive win
        self.assertTrue(has_effect(self.wolf, "prone"))
        self.assertIn("pin", msg.lower())

    def test_failed_grapple_gives_no_hold(self):
        from engine.tactics import grapple, is_grappling
        self._prep()
        grapple(self.engine, rng=self._rig([3, 12]))         # player loses
        self.assertIsNone(self.player.metadata.get("grappling"))
        self.assertFalse(is_grappling(self.engine))

    def test_throw_hurls_a_grabbed_foe(self):
        from engine.tactics import grapple, throw
        from characters.status_effects import has_effect
        self._prep()
        grapple(self.engine, rng=self._rig([10, 6]))         # grab first
        before = self.wolf.position
        msg = throw(self.engine, rng=self._rig([10, 6]))     # +4 grab bonus → win
        self.assertIn("hurl", msg.lower())
        self.assertTrue(has_effect(self.wolf, "prone"))
        self.assertNotEqual(self.wolf.position, before)      # sailed away
        self.assertIsNone(self.player.metadata.get("grappling"))  # released

    def test_throw_without_target(self):
        from engine.tactics import throw
        self._prep()
        self.engine.world.map.remove_character(self.wolf)
        self.engine.npc_manager.remove_npc(self.wolf.id)
        self.assertIn("No one", throw(self.engine))

    def test_grapple_verb_throws_when_already_clinched(self):
        # the SHIFT+C dispatch: while clinching, the key THROWS instead
        import pygame
        from ui.input_actions import grapple_verb
        self._prep()
        self.player.metadata["grappling"] = self.wolf.id
        self.wolf.metadata["grappled_by"] = self.player.id
        self.assertTrue(grapple_verb(self.engine, pygame.K_c))
        # a throw always releases the clinch (win or lose)
        self.assertIsNone(self.player.metadata.get("grappling"))

    def test_grapple_verb_ignores_other_keys(self):
        import pygame
        from ui.input_actions import grapple_verb
        self.assertFalse(grapple_verb(self.engine, pygame.K_x))


if __name__ == "__main__":
    unittest.main()
