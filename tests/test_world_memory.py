"""T2.1 — NPCs ingest world events into memory."""

import unittest

from engine import world_memory


class _NPC:
    def __init__(self, nid, pos):
        self.id = nid
        self.position = pos
        self.metadata = {}
        self.memories = []

    def is_active(self):
        return True

    def add_memory(self, event, importance=1):
        self.memories.append(event)


class _Eng:
    def __init__(self, npcs, ppos=(0, 0)):
        self.npc_manager = type("N", (), {"npcs": {n.id: n for n in npcs}})()
        self.player = type("P", (), {"position": ppos})()


class TestWorldMemory(unittest.TestCase):
    def test_realm_beat_reaches_nearby_npcs(self):
        npcs = [_NPC(f"n{i}", (i, 0)) for i in range(6)]
        world_memory.make_observer(_Eng(npcs, (0, 0)))(
            "[Realm] Ironhold and the Free Cities are at war!")
        heard = [n for n in npcs if n.memories]
        self.assertGreaterEqual(len(heard), 4, "the nearest folk hear the news")
        self.assertTrue(all("war" in m for n in heard for m in n.memories))

    def test_non_world_beat_is_ignored(self):
        npcs = [_NPC("n0", (0, 0))]
        world_memory.make_observer(_Eng(npcs))("You pick up a coin.")
        self.assertEqual(npcs[0].memories, [])

    def test_recent_world_beat_recall(self):
        n = _NPC("n0", (0, 0))
        world_memory._remember(n, "[Realm] A shortage grips Riverside.")
        self.assertIn("shortage", world_memory.recent_world_beat(n))
        self.assertIsNone(world_memory.recent_world_beat(_NPC("x", (0, 0))))

    def test_per_npc_beats_are_capped(self):
        n = _NPC("n0", (0, 0))
        for i in range(20):
            world_memory._remember(n, f"[Realm] event {i}")
        self.assertLessEqual(len(n.metadata["_world_beats"]), 8)


if __name__ == "__main__":
    unittest.main()
