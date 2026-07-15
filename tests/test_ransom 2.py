"""Ransom & rescue tests (P13.2)."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from characters.factions import Faction, get_rep
from engine.game_engine import GameEngine
from engine.ransom import (BODY_SLOTS, carrying, hoist_or_deliver,
                           wake_in_arms)


class TestRansomRescue(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.player.inventory = []

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _ko_someone(self, klass="villager"):
        npc = next((n for n in self.engine.npc_manager.npcs.values()
                    if n.is_active() and
                    getattr(n.character_class, "value", "") == klass
                    and self.wmap.get_character_at(*n.position) is n),
                   None)
        if npc is None:
            npc = next(n for n in self.engine.npc_manager.npcs.values()
                       if n.is_active() and
                       self.wmap.get_character_at(*n.position) is n
                       and getattr(n.character_class, "value", "")
                       in ("villager", "bard", "merchant", "guard"))
        npc.hp = 1
        self.engine.combat_system._handle_defeat(
            self.player, npc, damage=5)
        # stand on the body
        self.wmap.remove_character(self.player)
        self.player.position = npc.position
        self.wmap.place_character(self.player, *self.player.position)
        return npc

    def _open_ground(self):
        """Carry the body clear of any footprint (presence rules)."""
        from world.world_map import TerrainType
        wmap = self.wmap
        ox, oy = wmap.width - 8, wmap.height - 6
        for y in range(oy - 2, oy + 3):
            for x in range(ox - 2, ox + 4):
                wmap.terrain[y][x] = TerrainType.GRASS
                ch = wmap.get_character_at(x, y)
                if ch is not None:
                    wmap.remove_character(ch)
        self.wmap.remove_character(self.player)
        self.player.position = (ox, oy)
        self.wmap.place_character(self.player, ox, oy)
        return ox, oy

    def _put_adjacent(self, npc):
        px, py = self.player.position
        self.wmap.remove_character(npc)
        npc.position = (px + 1, py)
        self.wmap.place_character(npc, px + 1, py)

    def test_hoist_carries_the_body(self):
        npc = self._ko_someone()
        msg = hoist_or_deliver(self.engine)
        self.assertIn("over your shoulder", msg)
        self.assertIs(carrying(self.engine), npc)
        ground = self.engine.world.get_items_at(
            *self.player.position)
        self.assertFalse(any(str(g) == f"{npc.name}'s body"
                             for g in ground),
                         "the body left the ground")

    def test_the_body_weighs_on_the_pack(self):
        from engine.carry import capacity, used_slots
        self._ko_someone()
        before = used_slots(self.player)
        hoist_or_deliver(self.engine)
        self.assertEqual(used_slots(self.player),
                         before + BODY_SLOTS)

    def test_a_full_pack_cannot_hoist(self):
        from engine.carry import capacity
        from items.item_registry import create_item
        npc = self._ko_someone()
        self.player.inventory = [create_item("bread")
                                 for _ in range(capacity(self.player))]
        msg = hoist_or_deliver(self.engine)
        self.assertIn("free pack slots", msg)
        self.assertIsNone(carrying(self.engine))

    def test_rescue_at_the_priests_side(self):
        npc = self._ko_someone()
        hoist_or_deliver(self.engine)
        self._open_ground()
        cleric = next(n for n in self.engine.npc_manager.npcs.values()
                      if n.is_active() and
                      getattr(n.character_class, "value", "")
                      == "cleric")
        self._put_adjacent(cleric)
        gold0 = self.player.gold
        rep0 = get_rep(self.player, Faction.VILLAGERS)
        msg = hoist_or_deliver(self.engine)
        self.assertIn("pressed into it", msg)
        self.assertGreater(self.player.gold, gold0)
        self.assertTrue(npc.is_active(), "rescued and awake")
        self.assertGreaterEqual(npc.hp, npc.max_hp // 2)
        self.assertGreater(
            npc.get_relationship(self.player.id), 0)

    def test_ransom_at_the_fences_side(self):
        npc = self._ko_someone(klass="guard")
        level = npc.level
        hoist_or_deliver(self.engine)
        self._open_ground()
        from characters.npc_presets import make_npc
        fence = make_npc("camp_taverner_01")
        self.engine.npc_manager.add_npc(fence)
        self._put_adjacent(fence)
        gold0 = self.player.gold
        rep0 = get_rep(self.player, Faction.GUARDS)
        bounty0 = self.engine.law.bounty_here()
        msg = hoist_or_deliver(self.engine)
        self.assertIn("counts out", msg)
        self.assertEqual(self.player.gold - gold0,
                         25 + 10 * level)
        self.assertLess(get_rep(self.player, Faction.GUARDS), rep0)
        self.assertGreater(self.engine.law.bounty_here(), bounty0,
                           "the victim saw your face")
        self.assertLess(npc.get_relationship(self.player.id), -50)

    def test_plain_ground_just_sets_them_down(self):
        npc = self._ko_someone()
        hoist_or_deliver(self.engine)
        self._open_ground()   # away from anyone special
        msg = hoist_or_deliver(self.engine)
        self.assertIn("set", msg.lower())
        self.assertIsNone(carrying(self.engine))
        ground = self.engine.world.get_items_at(
            *self.player.position)
        self.assertTrue(any(str(g) == f"{npc.name}'s body"
                            for g in ground))

    def test_waking_in_your_arms(self):
        npc = self._ko_someone()
        hoist_or_deliver(self.engine)
        npc.metadata["ko_until"] = self.engine.world.time - 1
        from engine.dying import wake_the_fallen
        woke = wake_the_fallen(self.engine)
        self.assertGreaterEqual(woke, 1)
        self.assertIsNone(carrying(self.engine))
        self.assertTrue(npc.is_active())
        self.assertGreaterEqual(
            npc.get_relationship(self.player.id), 0,
            "the benefit of the doubt")


if __name__ == "__main__":
    unittest.main()
