"""Bones tests (P12.13): failures become the world's content."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))


import os
import random
import unittest

from engine.bones import (load_all, maybe_load_bones, on_equip_haunted,
                          record_bones)
from engine.game_engine import GameEngine
from items.item_registry import create_item


class _Rng:
    """rand drives the 1/3 roll; choice picks the first entry."""

    def __init__(self, rand=0.0):
        self.rand = rand

    def random(self):
        return self.rand

    def choice(self, seq):
        return seq[0]


class TestBones(unittest.TestCase):
    def setUp(self):
        # clean the bones file BEFORE the engine starts — start_game
        # itself rolls maybe_load_bones against whatever is on disk
        try:
            os.remove(os.path.join(
                os.environ["LLM_RPG_DM_LIBRARY"], "bones.json"))
        except OSError:
            pass
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass
        # leave no bones behind: later test modules start engines
        # with real rng and would roll ghosts nondeterministically
        try:
            os.remove(os.path.join(
                os.environ["LLM_RPG_DM_LIBRARY"], "bones.json"))
        except OSError:
            pass

    def _fall(self):
        self.player.name = "Aldric"
        self.player.level = 4
        self.player.inventory = [create_item("sword"),
                                 create_item("rope")]
        from world.monsters import build_monster
        wolf = build_monster("wolf", self.player.position)
        return record_bones(self.engine, wolf)

    def test_death_snapshots_the_site(self):
        entry = self._fall()
        self.assertEqual(entry["name"], "Aldric")
        self.assertEqual(entry["slayer"], "Wolf")
        self.assertIn("sword", entry["gear"])
        self.assertEqual(load_all()[-1]["name"], "Aldric")

    def test_the_cap_holds(self):
        for i in range(14):
            self.player.name = f"Hero {i}"
            record_bones(self.engine)
        self.assertEqual(len(load_all()), 10, "bones are capped")

    def test_a_new_world_can_be_haunted(self):
        self._fall()
        msg = maybe_load_bones(self.engine, rng=_Rng(rand=0.0))
        self.assertIsNotNone(msg)
        self.assertIn("[Legend]", msg)
        self.assertIn("Aldric", msg)
        ghost = self.engine.npc_manager.get_npc("ghost_aldric")
        self.assertIsNotNone(ghost, "the shade walks")
        self.assertTrue(ghost.metadata["behavior"]["flying"],
                        "ghosts fly (P11.4 pays again)")
        self.assertGreater(ghost.level, 4,
                           "scaled past the fallen hero")

    def test_the_roll_can_spare_you(self):
        self._fall()
        msg = maybe_load_bones(self.engine, rng=_Rng(rand=0.9))
        self.assertIsNone(msg, "two worlds in three rest easy")
        self.assertIsNone(
            self.engine.npc_manager.get_npc("ghost_aldric"))

    def test_the_gear_rises_mostly_haunted(self):
        self._fall()
        maybe_load_bones(self.engine, rng=_Rng(rand=0.0))
        ghost = self.engine.npc_manager.get_npc("ghost_aldric")
        gx, gy = ghost.position
        found = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                found += list(self.engine.world.get_items_at(
                    gx + dx, gy + dy))
        real = [it for it in found if hasattr(it, "id")]
        self.assertGreaterEqual(len(real), 2, "the gear scattered")
        self.assertTrue(any("Haunted" in it.name for it in real),
                        "rand 0.0 < 0.7 haunts everything")

    def test_haunted_gear_curses_the_wearer(self):
        from characters.equipment import equip
        from characters.status_effects import has_effect
        sword = create_item("sword")
        sword.name = "Haunted Shortsword"
        sword.use_effect["haunted"] = True
        self.player.inventory.append(sword)
        msg = equip(self.player, sword)
        self.assertIn("remembers its dead", msg)
        self.assertTrue(has_effect(self.player, "cursed"))

    def test_clean_gear_equips_clean(self):
        self.assertIsNone(on_equip_haunted(
            self.player, create_item("sword")))

    def test_true_death_writes_bones(self):
        from engine.dying import enter_dying, dying_tick
        from world.monsters import build_monster
        self.engine._has_gui = True
        wolf = build_monster("wolf", self.player.position)
        self.player.name = "Doomed"
        enter_dying(self.engine, wolf)

        class _Doom:
            def randint(self, a, b):
                return 1        # nat 1s: +2 per tick

            def random(self):
                return 0.05     # the slain leg of the table

        self.engine.combat_system.rng = _Doom()
        dying_tick(self.engine)
        dying_tick(self.engine)
        self.assertTrue(self.engine.player_dead)
        self.assertTrue(any(b["name"] == "Doomed"
                            for b in load_all()),
                        "the fall was recorded")


if __name__ == "__main__":
    unittest.main()
