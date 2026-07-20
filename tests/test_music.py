"""Procedural adaptive music (the score layer). The synthesis + mood
policy are pure and tested here; playback degrades silently headless."""

import unittest

import numpy as np

from ui import music_synth
from ui.music import select_mood, read_state


class TestSynth(unittest.TestCase):
    def test_midi_to_freq(self):
        self.assertAlmostEqual(music_synth.midi_to_freq(69), 440.0, places=3)
        # an octave up doubles the frequency
        self.assertAlmostEqual(music_synth.midi_to_freq(81), 880.0, places=3)

    def test_render_shape_and_range(self):
        params = {"scale": "dorian", "root": 57, "bpm": 66, "bars": 2,
                  "layers": ["pad", "bass", "arp"]}
        buf = music_synth.render_mood(params, seed=3)
        self.assertEqual(buf.dtype, np.float32)
        expect = music_synth._samples_for(66, 2)
        self.assertEqual(len(buf), expect)
        self.assertLessEqual(float(np.max(np.abs(buf))), 1.0)
        self.assertGreater(float(np.max(np.abs(buf))), 0.1)  # not silence

    def test_loop_boundary_is_seamless(self):
        params = {"scale": "minor", "root": 45, "bpm": 120, "bars": 2,
                  "layers": ["pad", "bass"]}
        buf = music_synth.render_mood(params, seed=1)
        peak = float(np.max(np.abs(buf)))
        # the wrap sample-to-sample jump should be small vs the peak
        self.assertLess(abs(float(buf[0]) - float(buf[-1])), 0.25 * peak)

    def test_arp_is_deterministic(self):
        p = {"scale": "minor", "root": 57, "bpm": 90, "bars": 2,
             "layers": ["arp"]}
        a = music_synth.render_mood(p, seed=7)
        b = music_synth.render_mood(p, seed=7)
        self.assertTrue(np.array_equal(a, b))
        c = music_synth.render_mood(p, seed=8)
        self.assertFalse(np.array_equal(a, c))

    def test_all_scales_render(self):
        for name in music_synth.SCALES:
            buf = music_synth.render_mood(
                {"scale": name, "bars": 1, "bpm": 100}, seed=0)
            self.assertTrue(np.all(np.isfinite(buf)))


class TestMoodPolicy(unittest.TestCase):
    def _s(self, **kw):
        base = {"in_combat": False, "threat_dist": None,
                "in_dungeon": False, "in_town": False, "is_night": False}
        base.update(kw)
        return select_mood(**base)

    def test_combat_beats_everything(self):
        self.assertEqual(self._s(in_combat=True, in_town=True,
                                 in_dungeon=True), "combat")

    def test_near_threat_is_tension(self):
        self.assertEqual(self._s(threat_dist=4, in_town=True), "tension")
        # a distant hostile does not raise tension
        self.assertEqual(self._s(threat_dist=20, in_town=True), "town")

    def test_dungeon_over_night(self):
        self.assertEqual(self._s(in_dungeon=True, is_night=True), "dungeon")

    def test_town_over_night(self):
        self.assertEqual(self._s(in_town=True, is_night=True), "town")

    def test_night_and_default(self):
        self.assertEqual(self._s(is_night=True), "night")
        self.assertEqual(self._s(), "explore")


class TestReadStateAndManager(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_read_state_shape(self):
        st = read_state(self.engine)
        self.assertEqual(set(st), {"in_combat", "threat_dist", "in_dungeon",
                                   "in_town", "is_night"})
        self.assertIsInstance(st["in_combat"], bool)

    def test_manager_constructs_and_is_safe(self):
        from ui.music import MusicManager
        m = MusicManager()                 # must not raise headless
        m.update_mood(self.engine, 1.0)    # throttled pick, safe
        m.update(0.05)
        m.shutdown()


if __name__ == "__main__":
    unittest.main()
