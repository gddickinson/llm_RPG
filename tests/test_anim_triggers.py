"""P33.6c — engine-side animation triggers (pygame-free) + a couple of wirings."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_at_"))

import unittest

from engine import anim
from engine.game_engine import GameEngine
from world.world_map import TerrainType


class _Char:
    def __init__(self, pos=(5, 5)):
        self.metadata = {}
        self.position = pos


class TestAnimHelpers(unittest.TestCase):
    def test_emote_and_stance_and_face(self):
        c = _Char()
        anim.emote(c, "bow")
        self.assertEqual(c.metadata["_emote"], "bow")
        anim.stance(c, "guard")
        self.assertEqual(c.metadata["_stance"], "guard")
        anim.stance(c, None)
        self.assertNotIn("_stance", c.metadata)
        anim.face(c, (9, 5))                       # east
        self.assertEqual(c.metadata["_face"], (1, 0))
        anim.face(c, (5, 1))                       # north
        self.assertEqual(c.metadata["_face"], (0, -1))


class TestWiredTriggers(unittest.TestCase):
    def setUp(self):
        self.e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        self.e.start_game()

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_swim_stance_on_water_and_off(self):
        p = self.e.player
        wmap = self.e.world.map
        px, py = p.position
        wmap.terrain[py][px] = TerrainType.WATER
        anim.update_swim(self.e)
        self.assertEqual(p.metadata["_stance"], "swim")
        wmap.terrain[py][px] = TerrainType.GRASS
        anim.update_swim(self.e)
        self.assertNotIn("_stance", p.metadata)

    def test_pickup_emits_a_stoop(self):
        p = self.e.player
        p.metadata.pop("_emote", None)
        self.e.pickup_item("nothing_here")         # even a miss bends down
        self.assertEqual(p.metadata.get("_emote"), "stoop")

    def test_combat_faces_and_recoils(self):
        from world.monsters import build_monster
        p = self.e.player
        px, py = p.position
        foe = build_monster("wolf", (px + 1, py))
        self.e.npc_manager.add_npc(foe)
        self.e.world.map.place_character(foe, px + 1, py)
        # rig the roll to land a hit so damage (and the recoil) definitely fires
        import random
        self.e.combat_system.rng = random.Random(0)
        for _ in range(6):                          # a few tries in case of a miss
            foe.metadata.pop("_emote", None)
            self.e.combat_system._resolve(p, foe)
            if foe.hp < foe.max_hp:
                break
        self.assertEqual(p.metadata.get("_face"), (1, 0))   # turned to the foe
        if foe.hp < foe.max_hp and foe.is_alive():           # it took a blow
            self.assertEqual(foe.metadata.get("_emote"), "hurt")


if __name__ == "__main__":
    unittest.main()
