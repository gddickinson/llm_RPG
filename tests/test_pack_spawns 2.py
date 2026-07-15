"""P32.2 — wolves hunt in packs, brigands ride in gangs.

A wilderness sighting of a pack/gang template brings companions from turn one
(the template's `group` block), all under one `pack:` tag so the P19.3 pack
brain coordinates them. Solitary creatures still come alone.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_pack_"))

import random
import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.monsters import group_spec


class TestGroupSpec(unittest.TestCase):
    def test_wolf_runs_in_a_pack(self):
        g = group_spec("wolf")
        self.assertIsNotNone(g)
        self.assertGreaterEqual(g["min"], 2)
        self.assertGreaterEqual(g["max"], g["min"])

    def test_bandit_rides_in_a_gang(self):
        self.assertEqual(group_spec("bandit")["word"], "gang")

    def test_a_troll_walks_alone(self):
        self.assertIsNone(group_spec("wandering_troll"))

    def test_unknown_template_has_no_group(self):
        self.assertIsNone(group_spec("no_such_beast"))


class _SpawnBase(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.em = self.engine.encounter_manager
        self.wmap = self.engine.world.map
        # a wide open wilderness patch far from any settlement, so a spawn is
        # allowed and companions have room to stand
        self.px, self.py = self.wmap.width // 2, self.wmap.height // 2
        for y in range(self.py - 8, self.py + 8):
            for x in range(self.px - 8, self.px + 8):
                if 0 <= x < self.wmap.width and 0 <= y < self.wmap.height:
                    self.wmap.terrain[y][x] = TerrainType.GRASS
        self.wmap.remove_character(self.engine.player)
        self.engine.player.position = (self.px, self.py)
        self.wmap.place_character(self.engine.player, self.px, self.py)
        # clear the world's pre-seeded lair hostiles so a test sees only the
        # pack it spawns
        from engine.pursuit import HOSTILE_CLASSES
        for n in list(self.engine.npc_manager.npcs.values()):
            if getattr(getattr(n, "character_class", None), "value", "") \
                    in HOSTILE_CLASSES:
                self.wmap.remove_character(n)
                self.engine.npc_manager.remove_npc(n.id)
        # neutralise the settlement-safe-zone + chance gates for a forced roll
        self.em._nearest_settlement_dist = lambda pos: 999.0
        self.em.spawn_chance = lambda: 1.0
        self.em.rng = random.Random(1)
        self.em._cooldown_until = 0

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _hostiles(self):
        from engine.pursuit import HOSTILE_CLASSES
        return [n for n in self.engine.npc_manager.npcs.values()
                if getattr(getattr(n, "character_class", None), "value", "")
                in HOSTILE_CLASSES]


class TestPackSpawn(_SpawnBase):
    def test_a_pack_template_spawns_more_than_one(self):
        # force the table to wolves so the pack block fires
        self.em.rng = random.Random(0)
        from world import monsters
        self.engine.world.map.get_terrain_at = lambda x, y: TerrainType.GRASS
        # pin the pick to wolf
        import world.encounters as enc
        orig = enc._weighted_pick
        enc._weighted_pick = lambda table, rng: "wolf"
        try:
            msg = self.em.maybe_spawn()
        finally:
            enc._weighted_pick = orig
        self.assertIsNotNone(msg)
        self.assertGreaterEqual(len(self._hostiles()), 2)

    def test_the_pack_shares_one_tag(self):
        import world.encounters as enc
        orig = enc._weighted_pick
        enc._weighted_pick = lambda table, rng: "wolf"
        try:
            self.em.maybe_spawn()
        finally:
            enc._weighted_pick = orig
        tags = {n.metadata.get("lair") for n in self._hostiles()}
        tags.discard(None)
        self.assertEqual(len(tags), 1, "the whole pack shares one tag")

    def test_pack_message_reads_as_a_group(self):
        import world.encounters as enc
        orig = enc._weighted_pick
        enc._weighted_pick = lambda table, rng: "bandit"
        try:
            msg = self.em.maybe_spawn()
        finally:
            enc._weighted_pick = orig
        self.assertIn("gang", msg.lower())


if __name__ == "__main__":
    unittest.main()
