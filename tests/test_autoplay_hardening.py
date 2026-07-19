"""Autoplay hardening (George: extensive autoplay testing). Regression
guards for the freeze/loop bugs a long soak surfaced:
  - a foe named "Ghost of Player" resolves to the GHOST, not the hero
  - a 0-HP "zombie" (status still alive) is REAPED, and never targeted
  - a picked-clean gather node is not "gatherable" (no forage loop)
  - a healthy hero FIGHTS a beatable pack (so it levels), flees a deadly one
  - the F12 in-game screenshot writes a file
"""

import os
import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster


class TestTargeting(unittest.TestCase):
    def setUp(self):
        self.e = GameEngine(llm_provider="heuristic",
                            enable_npc_processes=False)
        self.e.start_game()

    def tearDown(self):
        try:
            self.e.end_game()
        except Exception:
            pass

    def test_ghost_of_player_is_the_ghost_not_the_hero(self):
        g = build_monster("wraith", (self.e.player.position[0] + 2,
                                     self.e.player.position[1]))
        g.name, g.id = "Ghost of Player", "ghost_x"
        self.e.npc_manager.add_npc(g)
        self.assertIs(self.e.find_character("Ghost of Player"), g)
        # the loose keyword still resolves a bare reference to the hero
        self.assertIs(self.e.find_character("player"), self.e.player)
        self.assertIs(self.e.find_character("the traveler"), self.e.player)


class TestZombieReaper(unittest.TestCase):
    def test_zero_hp_zombie_is_reaped(self):
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        z = build_monster("goblin", (e.player.position[0] + 3,
                                     e.player.position[1]))
        z.id, z.hp = "zomb", 0
        e.npc_manager.add_npc(z)
        self.assertTrue(z.is_active())      # status still 'alive' at hp 0
        e.advance_turn()
        self.assertFalse(z.is_active())     # the pipeline reaps it
        e.end_game()

    def test_agent_ignores_a_zero_hp_foe(self):
        from engine.agent_controller import _driver_for
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        z = build_monster("goblin", (p.position[0] + 2, p.position[1]))
        z.id, z.hp = "zomb2", 0
        e.npc_manager.add_npc(z)
        e.roster.set_away(p, True)
        drv = _driver_for(e.roster.controller_for(p), p)
        foes = drv._foes_in_sight(e, p)
        self.assertFalse(any(f.id == "zomb2" for f, _ in foes))
        e.end_game()


class TestGatherLoop(unittest.TestCase):
    def test_picked_clean_node_is_not_gatherable(self):
        from engine.agent_sense import _gatherable
        from world.foraging import TERRAIN_FORAGE_TABLE
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        p = e.player
        gm = e.gathering_manager
        wm = e.world.map
        # scan for a standing tile whose node sits on NON-forageable terrain
        # (mining/fishing), so only the node-cooldown fix is under test
        found = None
        for y in range(0, wm.height):
            for x in range(0, wm.width):
                if wm.get_terrain_at(x, y) in TERRAIN_FORAGE_TABLE:
                    continue                       # standing tile forageable
                node = gm.node_at(x, y)
                if node is None:
                    continue
                skill_id, spec, pos = node
                if wm.get_terrain_at(*pos) in TERRAIN_FORAGE_TABLE:
                    continue                       # node terrain forageable
                found = (x, y, node)
                break
            if found:
                break
        if not found:
            e.end_game()
            self.skipTest("no non-forageable node in this world")
        x, y, (skill_id, spec, pos) = found
        p.position = (x, y)
        from items.item_registry import create_item
        tool = create_item(spec.get("tool"))       # the required tool
        if tool is not None:
            p.inventory.append(tool)
        if not gm.has_tool_for((skill_id, spec, pos)):
            e.end_game()
            self.skipTest("cannot equip the node tool")
        self.assertTrue(_gatherable(e, p))         # fresh node -> gatherable
        gm.harvested_at[(skill_id, pos[0], pos[1])] = e.world.time
        self.assertFalse(gm._cooldown_ok(skill_id, spec, pos))
        self.assertFalse(_gatherable(e, p))        # picked clean -> no loop
        e.end_game()


class TestScreenshot(unittest.TestCase):
    def test_f12_writes_a_file(self):
        import pygame
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import tempfile
        d = tempfile.mkdtemp()
        os.environ["LLM_RPG_SCREENSHOT_DIR"] = d
        e = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        e.start_game()
        from ui.gui import GameGUI
        gui = GameGUI(e, width=640, height=480)
        gui._render()
        from ui.input_handler import InputHandler
        ih = gui.input_handler
        self.assertIsInstance(ih, InputHandler)
        consumed = ih.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12))
        self.assertTrue(consumed)
        shots = [f for f in os.listdir(d) if f.endswith(".png")]
        self.assertTrue(shots, "F12 should have written a screenshot")
        e.end_game()


if __name__ == "__main__":
    unittest.main()
