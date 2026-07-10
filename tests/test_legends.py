"""History with residue — relics + legends (P4.6)."""

import unittest

from engine.game_engine import GameEngine
from engine.legends import known_ids, overlay_lines, on_item_picked_up


class TestLegends(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _ground_relics(self):
        out = []
        for (x, y), items in self.engine.world.ground_items.items():
            for it in items:
                if getattr(it, "metadata", {}).get("legend_id"):
                    out.append(((x, y), it))
        return out

    def test_every_history_event_left_a_relic(self):
        history = self.engine.world_history
        self.assertGreaterEqual(len(history), 4)
        relic_ids = {it.id for _, it in self._ground_relics()}
        for ev in history:
            self.assertIn(ev["relic_id"], relic_ids,
                          f"event '{ev['event_id']}' left no relic")

    def test_picking_up_relic_reveals_legend(self):
        (pos, relic) = self._ground_relics()[0]
        legend_id = relic.metadata["legend_id"]
        self.player.position = pos
        msg = self.engine.pickup_item()
        self.assertIn("pick up", msg)
        self.assertIn(legend_id, known_ids(self.player))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("[Legend]", log)

    def test_reveal_only_once(self):
        (pos, relic) = self._ground_relics()[0]
        on_item_picked_up(self.engine, relic)
        self.assertEqual(len(known_ids(self.player)), 1)
        self.assertIsNone(on_item_picked_up(self.engine, relic))
        self.assertEqual(len(known_ids(self.player)), 1)

    def test_overlay_hides_unfound_legend_text(self):
        history = self.engine.world_history
        lines = "\n".join(overlay_lines(self.engine))
        self.assertIn("still out there", lines)
        # No legend body should appear before its relic is found
        for ev in history:
            self.assertNotIn(ev["legend"], lines)
        # Find one and it appears
        (pos, relic) = self._ground_relics()[0]
        on_item_picked_up(self.engine, relic)
        lines = "\n".join(overlay_lines(self.engine))
        found = next(ev for ev in history
                     if ev["event_id"] == relic.metadata["legend_id"])
        self.assertIn(found["legend"], lines)

    def test_legend_pickup_can_teach_topics(self):
        """A legend mentioning the silver blade feeds the topic journal."""
        silver = next((ev for ev in self.engine.world_history
                       if ev["event_id"] == "silver_commission"), None)
        if silver is None:
            self.skipTest("silver commission not in this world's history")
        relic = next(it for _, it in self._ground_relics()
                     if it.metadata["legend_id"] == "silver_commission")
        on_item_picked_up(self.engine, relic)
        self.assertIn("silver_blade",
                      self.engine.topic_journal.known())

    def test_gossip_can_cite_history(self):
        from engine.legends import gossip_line
        import random
        forced = random.Random()
        forced.random = lambda: 0.0
        line = gossip_line(self.engine, forced)
        self.assertIsNotNone(line)
        self.assertIn("still tell of", line)

    def test_history_and_legends_persist(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        (pos, relic) = self._ground_relics()[0]
        on_item_picked_up(self.engine, relic)
        history_before = list(self.engine.world_history)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="lg")
            self.engine.world_history = []
            self.player.metadata["legends_known"] = []
            self.assertTrue(sm.load(self.engine, name="lg"))
            self.assertEqual(self.engine.world_history, history_before)
            self.assertTrue(known_ids(self.engine.player))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
