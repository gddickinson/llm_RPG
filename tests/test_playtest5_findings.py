"""Playtest Campaign 5 (P15.12) — a scripted, judged run across the P15
systems, and the regressions for what it found.

The exploratory session drove the new P15 mechanisms end to end. The one
real finding: the ONLY derelicts a fresh world produced were a well and a
shrine — neither a home — so the P15.7 homestead was both nonsensical
(you could "buy" the village well) AND unreachable (no derelict dwelling
existed). The fix: infrastructure isn't claimable, "Abandoned ..."
buildings stand genuinely derelict, and an Abandoned Cottage is seeded so
a real starter home is always within reach. These tests lock that in and
keep the rest of the P15 loop honest.
"""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine                # noqa: E402
from engine import homestead                             # noqa: E402
from engine.skill_progression import get_skill_xp        # noqa: E402
from items.item_registry import create_item              # noqa: E402
from world.monsters import build_monster                 # noqa: E402
from world.world_map import TerrainType                  # noqa: E402


class PlaytestCampaign5(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _derelict_homes(self):
        return [l for l in self.engine.world.locations
                if l.name in self.engine.interiors
                and l.get_property("derelict", False)
                and homestead._is_dwelling(l)]

    # ---- the finding: a reachable, sensible home --------------------

    def test_homestead_is_reachable(self):
        homes = self._derelict_homes()
        self.assertTrue(homes, "a fresh world must offer a derelict home")

    def test_a_well_is_not_a_home(self):
        well = next((l for l in self.engine.world.locations
                     if "well" in l.name.lower()), None)
        if well is not None:
            self.assertFalse(homestead._is_dwelling(well),
                             "a well is derelict but not a dwelling")

    def test_abandoned_building_is_derelict_and_empty(self):
        loc = next((l for l in self.engine.world.locations
                    if "abandoned cottage" in l.name.lower()), None)
        self.assertIsNotNone(loc, "the Abandoned Cottage should be seeded")
        self.assertTrue(loc.get_property("derelict", False))
        self.assertEqual(self.engine.homes.occupants_of(loc.name), [],
                         "an abandoned home has no residents")

    def test_full_homestead_loop_on_a_real_derelict(self):
        loc = self._derelict_homes()[0]
        self.engine.current_interior = self.engine.interiors[loc.name]
        self.p.position = (1, 1)
        self.p.gold = 500
        self.p.inventory.append(create_item("logs", 9))
        self.p.inventory.append(create_item("stone", 6))
        self.assertIn("buy", (self.engine.home_action() or "").lower())
        for _ in range(homestead.REPAIR_STAGES):
            self.engine.home_action()
        self.assertTrue(homestead.is_ready(self.p))
        from engine.rest import can_sleep_here
        self.assertIsNone(can_sleep_here(self.engine), "you can sleep home")

    # ---- roads earn their keep --------------------------------------

    def test_roads_save_time_on_the_real_move_path(self):
        wmap = self.engine.world.map
        # find a clear east-west corridor away from any building/NPC
        spot = None
        for y in range(2, wmap.height - 2):
            for x in range(2, wmap.width - 9):
                run = [(x + i, y) for i in range(8)]
                if all(wmap.terrain[ty][tx] == TerrainType.GRASS and
                       self.engine.world.get_location_at(tx, ty) is None and
                       wmap.get_character_at(tx, ty) is None
                       for tx, ty in run):
                    spot = (x, y)
                    break
            if spot:
                break
        self.assertIsNotNone(spot, "an open corridor should exist")
        wmap.remove_character(self.p)
        self.p.position = spot
        wmap.place_character(self.p, *spot)
        # clear any wandering hostile that could body-block the corridor —
        # P32.1 pursuit now walks foes toward the player; this test measures
        # road walkability, not a chase. Also silence fresh spawns during the
        # walk (P32.2 packs) so nothing steps into the lane mid-stride.
        self.engine.encounter_manager.maybe_spawn = lambda: None
        for npc in list(self.engine.npc_manager.npcs.values()):
            if abs(npc.position[0] - spot[0]) <= 16 and \
                    abs(npc.position[1] - spot[1]) <= 16:
                wmap.remove_character(npc)
        for i in range(1, 8):
            wmap.terrain[spot[1]][spot[0] + i] = TerrainType.ROAD
        self.p.metadata["road_steps"] = 0
        t0 = self.engine.world.time
        moved = sum(1 for _ in range(6) if self.engine.move_player(1, 0))
        self.assertGreaterEqual(moved, 6, "the road corridor is walkable")
        self.assertLess(self.engine.world.time - t0, moved,
                        "roads cost fewer minutes than steps")

    # ---- skill breadth in play --------------------------------------

    def test_a_trade_and_a_hunt_train_the_new_skills(self):
        merchant = self.engine.npc_manager.get_npc("blacksmith_01")
        merchant.inventory.append(create_item("bread"))
        self.p.gold = 500
        self.engine.economy_system._exec_buy_player("bread", merchant)
        self.assertGreater(get_skill_xp(self.p, "bartering"), 0)

        px, py = self.p.position
        wolf = build_monster("wolf", (px + 1, py))
        wolf.hp = 1
        self.engine.npc_manager.add_npc(wolf)
        for _ in range(20):
            if not wolf.is_active():
                break
            self.engine.attack_character(wolf.name)
        self.assertGreater(get_skill_xp(self.p, "hunting"), 0)

    # ---- visuals: a stormy conjunction night renders ----------------

    def test_night_atmosphere_renders(self):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 240))
        from ui.lighting import LightingOverlay
        from ui.hud import HUD
        from world.weather import Weather
        self.engine.world.time = 22 * 60
        self.engine.weather_system.state.current = Weather.SNOW
        px, py = self.p.position
        self.engine.npc_manager.add_npc(
            build_monster("marsh_wisp", (px + 2, py)))
        for line in ("[!] danger", "[Law] a bounty", "[DM] a portent"):
            self.engine.memory_manager.add_event(line)
        surf = pygame.Surface((320, 240))
        view = pygame.Rect(0, 0, 320, 240)
        LightingOverlay().apply(surf, view, self.engine, 0, 0, 16)
        hud = HUD()
        hud.draw_event_log(surf, self.engine, pygame.Rect(0, 0, 200, 200))
        hud.draw_minimap(surf, self.engine, pygame.Rect(0, 0, 160, 160))

    # ---- an agent hero keeps the world populated --------------------

    def test_an_agent_hero_acts_beside_you(self):
        from engine.player_roster import PlayerController, AGENT
        from engine.agent_controller import drive_agents
        from characters.npc_presets import make_npc
        bot = make_npc("guard_01")
        bot.id = "bot_hero"
        bot.name = "Botfriend"
        bot.position = (self.p.position[0] + 3, self.p.position[1])
        self.engine.roster.add(bot, PlayerController(AGENT, "Botfriend"))
        start = tuple(bot.position)
        self.engine._advancing = True
        try:
            for _ in range(8):
                drive_agents(self.engine)
        finally:
            self.engine._advancing = False
        self.assertNotEqual(tuple(bot.position), start,
                            "the agent hero should move on its own")


if __name__ == "__main__":
    unittest.main()
