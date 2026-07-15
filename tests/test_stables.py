"""P28.2d — stables near settlements: buy and ride a mount (George)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_stable_"))

import unittest

import pygame

from engine import mounts


class TestStableSeeding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_a_stable_is_seeded_near_oakvale(self):
        st = self.engine.stables
        self.assertTrue(st.stables, "at least one stable should seed")
        names = {s["name"] for s in st.stables}
        self.assertTrue(any("Oakvale" in n for n in names),
                        f"a stable should stand by Oakvale, got {names}")

    def test_the_stable_marker_is_a_location(self):
        st = self.engine.stables
        pos = tuple(st.stables[0]["pos"])
        loc = self.engine.world.get_location_at(*pos)
        self.assertIsNotNone(loc)
        self.assertEqual((loc.properties or {}).get("type"), "stable")

    def test_stable_at_detects_the_player(self):
        st = self.engine.stables
        sx, sy = st.stables[0]["pos"]
        self.assertIsNotNone(st.stable_at((sx, sy)))
        self.assertIsNone(st.stable_at((sx + 20, sy + 20)))


class TestBuyAndRide(unittest.TestCase):
    def setUp(self):
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        sx, sy = self.engine.stables.stables[0]["pos"]
        self.engine.player.position = (sx, sy)
        self.engine.player.gold = 1000

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_buying_a_horse_mounts_you(self):
        self.assertTrue(self.engine.at_stable())
        msg = self.engine.mount_stable_buy(0)      # 0 = horse (stable order)
        self.assertIn("horse", msg.lower())
        p = self.engine.player
        self.assertTrue(mounts.is_riding(p))
        self.assertEqual(mounts.active_mount(p), "horse")
        self.assertTrue(p.metadata.get("mounted"), "the road-pace lever is on")
        self.assertGreater(mounts.carry_bonus(p), 0)

    def test_the_menu_lists_stable_mounts(self):
        lines = "\n".join(self.engine.mount_stable_lines()).lower()
        for word in ("horse", "mule", "donkey", "purse"):
            self.assertIn(word, lines)

    def test_cannot_buy_away_from_a_stable(self):
        self.engine.player.position = (2, 2)       # far from any stable
        self.assertFalse(self.engine.at_stable())
        msg = mounts.buy_mount(self.engine, "horse")
        self.assertNotIn("you buy", msg.lower())
        self.assertFalse(mounts.is_riding(self.engine.player))

    def test_the_mount_and_stables_ride_the_save(self):
        self.engine.mount_stable_buy(0)
        # StableSystem round-trip
        st = self.engine.stables
        d = st.to_dict()
        st.stables = []
        st.from_dict(d)
        self.assertTrue(st.stables)
        # the bought mount is player metadata (rides the normal player save)
        self.assertEqual(self.engine.player.metadata["mount"]["kind"], "horse")


class TestMountRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_draw_mount_paints(self):
        from ui.renderer_overlays import draw_mount
        surf = pygame.Surface((64, 64))
        surf.fill((0, 0, 0))
        draw_mount(surf, "horse", 0, 0, 48)
        painted = sum(1 for x in range(0, 64, 3) for y in range(0, 64, 3)
                      if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(painted, 10, "the horse should draw")


if __name__ == "__main__":
    unittest.main()
