"""Ranged targeting tests (P8.7)."""

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType
from items.item_registry import create_item
from characters.equipment import equip


class TestTargeting(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        # Clear range on open ground
        self.ox, self.oy = self.wmap.width - 18, self.wmap.height - 12
        for y in range(self.oy, self.oy + 8):
            for x in range(self.ox, self.ox + 16):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox + 1, self.oy + 4)
        self.wmap.place_character(self.player, *self.player.position)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _spawn(self, template, dx, dy):
        npc = build_monster(template,
                            (self.ox + 1 + dx, self.oy + 4 + dy))
        npc.hp = npc.max_hp = 99
        self.engine.npc_manager.add_npc(npc)
        self.wmap.place_character(npc, *npc.position)
        return npc

    def test_cycle_locks_nearest_first(self):
        near = self._spawn("wolf", 3, 0)
        far = self._spawn("goblin", 7, 0)
        msg = self.engine.targeting.cycle()
        self.assertIn(near.name, msg)
        self.assertEqual(self.engine.player_target_id, near.id)
        msg = self.engine.targeting.cycle()
        self.assertEqual(self.engine.player_target_id, far.id)
        self.assertIn("tiles", msg)

    def test_cycle_wraps_and_reverses(self):
        a = self._spawn("wolf", 3, 0)
        b = self._spawn("goblin", 6, 0)
        self.engine.targeting.cycle()          # a
        self.engine.targeting.cycle()          # b
        self.engine.targeting.cycle()          # wraps to a
        self.assertEqual(self.engine.player_target_id, a.id)
        self.engine.targeting.cycle(-1)        # back to b
        self.assertEqual(self.engine.player_target_id, b.id)

    def test_dead_lock_falls_back_to_nearest(self):
        a = self._spawn("wolf", 3, 0)
        b = self._spawn("goblin", 6, 0)
        self.engine.player_target_id = a.id
        a.defeat()
        self.assertIs(self.engine.targeting.current(), b)

    def test_no_lock_through_a_wall(self):
        wolf = self._spawn("wolf", 6, 0)
        for dy in (-1, 0, 1):
            self.wmap.terrain[self.oy + 4 + dy][self.ox + 4] = \
                TerrainType.MOUNTAIN
        ok, why = self.engine.targeting.can_hit(wolf)
        self.assertFalse(ok)
        self.assertIn("in the way", why)
        self.assertEqual(self.engine.targeting.candidates(), [])

    def test_out_of_range_refused(self):
        wolf = self._spawn("wolf", 14, 0)
        ok, why = self.engine.targeting.can_hit(wolf)
        self.assertFalse(ok)
        self.assertIn("out of range", why)

    def test_bow_fires_at_the_lock(self):
        near = self._spawn("wolf", 3, 0)
        far = self._spawn("goblin", 6, 0)
        bow = create_item("bow")
        self.player.inventory.append(bow)
        equip(self.player, bow)
        ammo = create_item("arrow")
        if ammo is not None:
            ammo.quantity = 10
            self.player.inventory.append(ammo)
        self.engine.player_target_id = far.id
        msg = self.engine.shoot_ranged()
        self.assertIn(far.name, msg,
                      "the shot must go at the LOCK, not the nearest")

    def test_attack_spell_respects_los(self):
        wolf = self._spawn("wolf", 5, 0)
        for dy in (-1, 0, 1):
            self.wmap.terrain[self.oy + 4 + dy][self.ox + 4] = \
                TerrainType.MOUNTAIN
        self.player.metadata.setdefault("spells_known", []).append(
            "magic_missile")
        self.player.metadata["mana"] = 50
        self.player.metadata["max_mana"] = 50
        msg = self.engine.cast_spell("magic_missile", wolf.name)
        self.assertIn("in the way", msg)
        self.assertEqual(wolf.hp, 99, "spell must not land")

    def test_provoked_civilians_are_targetable(self):
        npc = next(n for n in self.engine.npc_manager.npcs.values()
                   if getattr(n.character_class, "value", "") ==
                   "merchant" and n.is_active())
        self.wmap.remove_character(npc)
        npc.position = (self.ox + 4, self.oy + 4)
        self.wmap.place_character(npc, *npc.position)
        self.assertNotIn(npc, self.engine.targeting.candidates())
        npc.metadata["provoked"] = True
        self.assertIn(npc, self.engine.targeting.candidates())


if __name__ == "__main__":
    unittest.main()
