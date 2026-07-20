"""Combat depth tests (P12.7): concentration, cover, weapon actions."""

import unittest

from characters.status_effects import has_effect
from engine.combat_depth import (cover_penalty, weapon_action)
from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.monsters import build_monster
from world.world_map import TerrainType


class _Rng:
    def __init__(self, roll=10, rand=0.5):
        self.roll = roll
        self.rand = rand

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def random(self):
        return self.rand


class TestCombatDepth(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.ox, self.oy = self.wmap.width - 12, self.wmap.height - 10
        for y in range(self.oy - 3, self.oy + 4):
            for x in range(self.ox - 3, self.ox + 8):
                self.wmap.terrain[y][x] = TerrainType.GRASS
                ch = self.wmap.get_character_at(x, y)
                if ch is not None:
                    self.wmap.remove_character(ch)
        # Also purge the NPC MANAGER of anyone in the box: `adjacent_hostiles`
        # reads the manager, so a world/pack hostile the grid-clear missed (one
        # not on the spatial index) would linger as a PHANTOM adjacent foe and
        # steal the primary strike — a rare full-suite flake (an interloping
        # Bandit stealing a Cleave's primary target).
        for npc in list(self.engine.npc_manager.npcs.values()):
            nx, ny = npc.position
            if (self.ox - 3 <= nx < self.ox + 8
                    and self.oy - 3 <= ny < self.oy + 4):
                self.wmap.remove_character(npc)
                self.engine.npc_manager.remove_npc(npc.id)
        self.wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        self.wmap.place_character(self.player, self.ox, self.oy)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _foe(self, dx=1, dy=0, hp=99):
        foe = build_monster("wolf", (self.ox + dx, self.oy + dy))
        foe.hp = foe.max_hp = hp
        self.engine.npc_manager.add_npc(foe)
        self.wmap.place_character(foe, *foe.position)
        return foe

    def _learn(self, *spells):
        self.player.metadata["spells_known"] = list(spells)
        self.player.metadata["mana"] = 50
        self.player.metadata["max_mana"] = 50

    # -------------------------------------------- concentration

    def test_one_sustained_spell_at_a_time(self):
        self._learn("haste", "frost_armor")
        self.engine.cast_spell("haste")
        self.assertTrue(has_effect(self.player, "hasted"))
        self.engine.cast_spell("frost_armor")
        self.assertFalse(has_effect(self.player, "hasted"),
                         "the second concentration drops the first")
        conc = self.player.metadata.get("concentrating")
        self.assertEqual(conc["spell"], "frost_armor")

    def test_damage_forces_the_keep_it_check(self):
        self._learn("haste")
        self.engine.cast_spell("haste")
        foe = self._foe()

        class _Seq:
            def __init__(self, vals):
                self.vals = list(vals)

            def randint(self, a, b):
                v = self.vals.pop(0) if len(self.vals) > 1 \
                    else self.vals[0]
                return min(b, max(a, v))

            def random(self):
                return 0.5

        # crit hit lands damage, then the keep-it d20 comes up 1
        self.engine.combat_system.rng = _Seq([20, 3, 1])
        self.player.hp = self.player.max_hp
        self.engine.combat_system._resolve(foe, self.player)
        self.assertFalse(has_effect(self.player, "hasted"),
                         "pain scatters focus")
        self.assertIsNone(self.player.metadata.get("concentrating"))

    def test_concentration_survives_on_a_good_roll(self):
        self._learn("haste")
        self.engine.cast_spell("haste")
        from engine.combat_depth import concentration_check
        self.engine.combat_system.rng = _Rng(roll=20)
        concentration_check(self.engine, self.player, 12)
        self.assertTrue(has_effect(self.player, "hasted"))

    # ---------------------------------------------------- cover

    def test_forest_between_grants_cover(self):
        self.assertEqual(
            cover_penalty(self.engine, self.ox, self.oy,
                          self.ox + 4, self.oy), 0.0)
        self.wmap.terrain[self.oy][self.ox + 2] = TerrainType.FOREST
        self.assertEqual(
            cover_penalty(self.engine, self.ox, self.oy,
                          self.ox + 4, self.oy), 0.10,
            "one tree is half cover")
        self.wmap.terrain[self.oy][self.ox + 3] = TerrainType.FOREST
        self.assertEqual(
            cover_penalty(self.engine, self.ox, self.oy,
                          self.ox + 4, self.oy), 0.25,
            "two is three-quarters")

    def test_cover_rides_the_projectile(self):
        self.wmap.terrain[self.oy][self.ox + 2] = TerrainType.FOREST
        foe = self._foe(dx=4)
        proj = self.engine.projectile_manager.spawn(
            self.player, foe, 5, weapon_type="bow")
        self.assertEqual(proj.cover, 0.10)

    # ------------------------------------------- weapon actions

    def _arm(self, weapon_id):
        weapon = create_item(weapon_id)
        self.player.inventory.append(weapon)
        from characters.equipment import equip
        equip(self.player, weapon)

    def test_topple_knocks_prone_once_per_rest(self):
        self._arm("warhammer")
        foe = self._foe()
        self.engine.combat_system.rng = _Rng(roll=20)
        msg = weapon_action(self.engine)
        self.assertIn("crash", msg)
        self.assertTrue(has_effect(foe, "prone"))
        msg2 = weapon_action(self.engine)
        self.assertIn("spent", msg2, "once per rest")

    def test_cleave_carries_into_a_second_enemy(self):
        self._arm("battleaxe")
        a = self._foe(dx=1)
        b = self._foe(dx=0, dy=1)
        self.engine.combat_system.rng = _Rng(roll=20)
        weapon_action(self.engine)
        self.assertLess(a.hp, 99)
        self.assertLess(b.hp, 99, "the swing carries through")

    def test_lacerate_bleeds(self):
        self._arm("dagger")
        foe = self._foe()
        self.engine.combat_system.rng = _Rng(roll=20)
        # capture the event index BEFORE the action: a fixed last-N window is too
        # small now that advance_turn emits ambient [Town]/wildlife/etc. beats
        # (count varies with global-RNG order → a full-suite flake).
        n0 = len(self.engine.memory_manager.game_history)
        weapon_action(self.engine)
        # the action's own turn tick may roll the flat end-check
        # (unrigged), so assert the wound bled, not that it persists
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[n0:])
        self.assertIn("red line", log)
        self.assertIn("bleeding", log.lower(),
                      "the wound bled at least once")

    def test_rest_restores_the_move(self):
        self._arm("warhammer")
        self._foe()
        self.engine.combat_system.rng = _Rng(roll=20)
        weapon_action(self.engine)
        self.assertTrue(
            self.player.metadata.get("weapon_action_used"))
        from engine import rest
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      or "inn" in l.name.lower())
        self.wmap.remove_character(self.player)
        self.player.position = (tavern.x + tavern.width // 2,
                                tavern.y + tavern.height // 2)
        self.wmap.place_character(self.player, *self.player.position)
        self.player.gold = 100
        rest.sleep(self.engine)
        self.assertFalse(
            self.player.metadata.get("weapon_action_used"),
            "a night's rest restores the special")

    def test_actions_are_data_on_the_weapons(self):
        for wid, action in (("warhammer", "topple"),
                            ("battleaxe", "cleave"),
                            ("sword", "pommel_strike"),
                            ("dagger", "lacerate")):
            item = create_item(wid)
            self.assertEqual(item.use_effect.get("weapon_action"),
                             action)


if __name__ == "__main__":
    unittest.main()
