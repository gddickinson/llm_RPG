"""PUX.1 — a major GUI gameplay integration test.

Drives the ENGINE through the same calls the GUI/input_handler makes
(heuristic provider, SDL dummy from tests/__init__), exercising the
whole core loop end-to-end: boot a world, move, fight, level, handle
items, talk, take a quest, trade, cast a spell, enter a building, and
survive a save/load round-trip. This is the regression net for "the
playable game still works together", complementing the many unit
tests that check one system in isolation.

Setups are deterministic — enemies and merchants are spawned adjacent
to the player rather than hunted for in the procedural world, so the
test never depends on worldgen layout.
"""

import os as _os
import tempfile as _tempfile
import unittest

# start_game / save-load touch the DM Legendarium; pin it to a temp dir
# (discover imports test files as top-level modules — self-pin here).
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine          # noqa: E402
from engine.leveling import award_xp               # noqa: E402
from engine.save_load import SaveManager           # noqa: E402
from items.item_registry import create_item        # noqa: E402
from world.monsters import build_monster           # noqa: E402
from characters.npc_presets import make_npc        # noqa: E402


class TestGuiPlaythrough(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    # ---- helpers -------------------------------------------------

    def _place_adjacent(self, entity):
        """Put an entity on a tile the presence-aware adjacency check
        accepts — worldgen varies, so search rather than assume (a
        building footprint next door would read as 'indoors')."""
        from engine.presence import npc_adjacent_to_player
        px, py = self.player.position
        for off in ((1, 0), (-1, 0), (0, 1), (0, -1),
                    (1, 1), (-1, -1), (1, -1), (-1, 1), (0, 0)):
            entity.position = (px + off[0], py + off[1])
            if npc_adjacent_to_player(self.engine, entity):
                return entity
        return entity

    def _spawn_monster(self, template="wolf"):
        m = build_monster(template, self.player.position)
        self.engine.npc_manager.add_npc(m)
        return self._place_adjacent(m)

    def _spawn_npc(self, npc_id="blacksmith_01"):
        npc = make_npc(npc_id, self.player.position)
        self.engine.npc_manager.add_npc(npc)
        return self._place_adjacent(npc)

    def _kill(self, target, swings=60):
        for _ in range(swings):
            if not target.is_active():
                break
            self.engine.combat_system.player_attack(target.name)
        return not target.is_active()

    # ---- the core loop, slice by slice ---------------------------

    def test_new_game_boots_a_world(self):
        self.assertTrue(self.player.is_active())
        self.assertIsNotNone(self.player.position)
        for sysname in ("combat_system", "economy_system",
                        "quest_manager", "npc_manager", "world",
                        "interiors"):
            self.assertTrue(hasattr(self.engine, sysname), sysname)
        self.assertGreater(len(self.engine.world.locations), 0)

    def test_moving_runs_the_turn_pipeline(self):
        start = self.player.position
        moved = any(self.engine.move_player(dx, dy)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        self.assertTrue(moved, "the player can walk somewhere")
        self.assertNotEqual(self.player.position, start)
        for _ in range(3):                     # the per-turn pipeline
            self.engine.advance_turn()
        self.assertTrue(self.player.is_active())

    def test_combat_kills_and_awards_xp(self):
        xp0 = self.player.metadata.get("xp", 0)
        wolf = self._spawn_monster("wolf")
        self.assertTrue(self._kill(wolf), "the wolf should fall")
        self.assertGreater(self.player.metadata.get("xp", 0), xp0,
                           "a kill grants experience")

    def test_experience_levels_the_hero_up(self):
        lvl0, hp0 = self.player.level, self.player.max_hp
        msgs = award_xp(self.player, 5000)
        self.assertGreater(self.player.level, lvl0, "the hero levels")
        self.assertGreater(self.player.max_hp, hp0, "and grows tougher")
        self.assertTrue(msgs)

    def test_items_pick_up_equip_and_use(self):
        blade = create_item("sword")
        self.player.inventory.append(blade)
        self.engine.equip_item(blade.name)
        equipped = self.engine.get_equipment()
        self.assertTrue(any(equipped.values()), "something is worn")

        potion = create_item("potion")
        self.player.inventory.append(potion)
        self.player.take_damage(8)
        hurt = self.player.hp
        self.engine.use_item(potion.name)
        self.assertGreater(self.player.hp, hurt, "the potion healed")

    def test_talk_to_an_npc(self):
        npc = self._spawn_npc("blacksmith_01")
        reply = self.engine.interact_with_npc(npc.id, "hello")
        self.assertIsInstance(reply, str)
        self.assertTrue(reply.strip(), "the NPC says something")

    def test_accept_a_quest(self):
        ok = self.engine.accept_quest("herb_gathering")
        self.assertTrue(ok, "the quest is accepted")
        active_ids = [q.id for q in self.engine.quest_manager.active()]
        self.assertIn("herb_gathering", active_ids)

    def test_buy_and_sell_with_a_merchant(self):
        merchant = self._spawn_npc("blacksmith_01")
        ware = create_item("dagger")
        merchant.inventory.append(ware)
        self.player.gold = 500
        gold0 = self.player.gold
        self.engine.economy_system.player_buy(ware.name, merchant.name)
        self.assertLess(self.player.gold, gold0, "gold was spent")
        self.assertTrue(any(i.name == ware.name
                            for i in self.player.inventory),
                        "the ware is now the player's")
        gold1 = self.player.gold
        self.engine.economy_system.player_sell(ware.name, merchant.name)
        self.assertGreater(self.player.gold, gold1, "and sells back")

    def test_cast_a_spell(self):
        self.player.metadata.setdefault("spells_known", []).append("heal")
        self.player.metadata["mana"] = 10
        self.player.metadata["max_mana"] = 10
        self.player.take_damage(6)
        mana0 = self.player.metadata["mana"]
        self.engine.cast_spell("heal")
        self.assertLess(self.player.metadata["mana"], mana0,
                        "casting spends mana")

    def test_enter_and_leave_a_building(self):
        loc = next((l for l in self.engine.world.locations
                    if l.name in self.engine.interiors), None)
        self.assertIsNotNone(loc, "the world has enterable buildings")
        self.player.position = (loc.x, loc.y)
        self.engine.enter_building(loc, via_breach=True)
        self.assertIsNotNone(self.engine.current_interior, "went inside")
        self.engine.exit_building()
        self.assertIsNone(self.engine.current_interior, "and back out")

    def test_save_and_load_preserve_state(self):
        self.player.gold = 777
        self.player.take_damage(4)
        hp, gold, pos = self.player.hp, self.player.gold, \
            self.player.position
        with _tempfile.TemporaryDirectory() as tmp:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, "playthrough")
            self.player.gold = 0            # scribble over live state
            self.player.hp = 1
            self.assertTrue(sm.load(self.engine, "playthrough"))
        self.assertEqual(self.engine.player.gold, gold)
        self.assertEqual(self.engine.player.hp, hp)
        self.assertEqual(self.engine.player.position, pos)

    def test_full_core_loop(self):
        """One chained playthrough — the whole game in one run."""
        # fight at the clean start (spawn adjacency is reliable here),
        # take the loot's worth of xp, then walk a little
        xp0 = self.player.metadata.get("xp", 0)
        wolf = self._spawn_monster("wolf")
        self.assertTrue(self._kill(wolf))
        self.assertGreater(self.player.metadata.get("xp", 0), xp0)
        for dx, dy in ((1, 0), (0, 1), (-1, 0)):
            self.engine.move_player(dx, dy)
        # trade
        merchant = self._spawn_npc("blacksmith_01")
        ware = create_item("dagger")
        merchant.inventory.append(ware)
        self.player.gold = 200
        self.engine.economy_system.player_buy(ware.name, merchant.name)
        # and it all survives a save/load
        with _tempfile.TemporaryDirectory() as tmp:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, "loop")
            self.assertTrue(sm.load(self.engine, "loop"))
        self.assertTrue(self.engine.player.is_active())


if __name__ == "__main__":
    unittest.main()
