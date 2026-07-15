"""NPC-vs-NPC conflict tests (P7.1) — the world fights its own battles."""

import unittest

from engine.game_engine import GameEngine
from engine.npc_conflict import TICK_INTERVAL, RAID_MULTIPLE
from world.monsters import build_monster


class TestNPCConflict(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put(self, char, x, y):
        char.position = (x, y)
        self.wmap.place_character(char, x, y)
        return char

    def _spawn(self, template, x, y):
        npc = build_monster(template, (x, y))
        self.engine.npc_manager.add_npc(npc)
        self.wmap.place_character(npc, x, y)
        return npc

    def _guard(self):
        guard = next(n for n in self.engine.npc_manager.npcs.values()
                     if getattr(n.character_class, "value", "") == "guard"
                     and n.is_active())
        return guard

    def _park_player_far(self):
        self.engine.player.position = (self.wmap.width - 2,
                                       self.wmap.height - 2)

    def _clear_other_hostiles(self):
        # seeded lair/wilderness beasts (P19.2) would steal the guard's eye —
        # remove them so the test bandit is the only visible foe (hermetic)
        from engine.agent_controller import _is_hostile
        for nid in list(self.engine.npc_manager.npcs):
            if _is_hostile(self.engine.npc_manager.npcs[nid]):
                self.wmap.remove_character(self.engine.npc_manager.npcs[nid])
                self.engine.npc_manager.remove_npc(nid)

    def test_guard_closes_on_and_fights_visible_hostile(self):
        from world.world_map import TerrainType
        self._park_player_far()
        self._clear_other_hostiles()
        for x in range(3, 12):          # an open lane the guard can walk
            self.wmap.terrain[5][x] = TerrainType.GRASS
        guard = self._put(self._guard(), 5, 5)
        bandit = self._spawn("bandit", 9, 5)
        hp_before = bandit.hp
        for _ in range(30):
            self.engine.turn_counter += 1
            self.engine.npc_conflict.update()
            if not bandit.is_active():
                break
        dist = abs(guard.position[0] - bandit.position[0]) + \
            abs(guard.position[1] - bandit.position[1])
        self.assertTrue(bandit.hp < hp_before or not bandit.is_active()
                        or dist <= 1,
                        f"guard never engaged (dist {dist}, "
                        f"hp {bandit.hp}/{hp_before})")

    def test_hostile_raids_nearby_civilian(self):
        from world.world_map import TerrainType
        self._park_player_far()
        self._clear_other_hostiles()       # no rival hostile steals/blocks it
        villager = next(
            n for n in self.engine.npc_manager.npcs.values()
            if getattr(n.character_class, "value", "") in
            ("villager", "merchant") and n.is_active())
        # No guards in sight: clear an open, walkable lane for the ambush so
        # the bandit's approach never stalls on worldgen terrain or a bystander
        vx, vy = 3, self.wmap.height - 4
        for x in range(1, 8):
            self.wmap.terrain[vy][x] = TerrainType.GRASS
            occ = self.wmap.get_character_at(x, vy)
            if occ is not None and occ is not villager:
                self.wmap.remove_character(occ)
        self._put(villager, vx, vy)
        bandit = self._spawn("bandit", vx + 2, vy)
        hp_before = villager.hp
        for _ in range(TICK_INTERVAL * RAID_MULTIPLE * 8):
            self.engine.turn_counter += 1
            self.engine.npc_conflict.update()
            if villager.hp < hp_before or not villager.is_active():
                break
        moved = abs(bandit.position[0] - vx) + \
            abs(bandit.position[1] - vy) <= 1
        self.assertTrue(villager.hp < hp_before or moved
                        or not villager.is_active(),
                        "hostile never moved on the civilian")

    def test_players_duel_is_left_alone(self):
        guard = self._put(self._guard(), 5, 5)
        px, py = 7, 5
        self.engine.player.position = (px, py)
        wolf = self._spawn("wolf", px + 1, py)
        hp_before = wolf.hp
        for _ in range(12):
            self.engine.turn_counter += 1
            self.engine.npc_conflict.update()
        self.assertEqual(wolf.hp, hp_before,
                         "guards must not steal the player's duel")
        self.assertTrue(wolf.is_active())

    def test_clash_logged_only_near_player(self):
        self._park_player_far()
        self._put(self._guard(), 5, 5)
        bandit = self._spawn("bandit", 6, 5)  # adjacent: resolves now
        bandit.hp = bandit.max_hp = 99   # must survive both phases
        self.engine.turn_counter = TICK_INTERVAL - 1
        self.engine.turn_counter += 1
        self.engine.npc_conflict.update()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-6:])
        self.assertNotIn("[Clash]", log,
                         "far-away swings must not spam the log")
        # Within earshot but outside duel-protection range: audible
        self.engine.player.position = (12, 5)
        for _ in range(TICK_INTERVAL * 4):
            self.engine.turn_counter += 1
            self.engine.npc_conflict.update()
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-12:])
        self.assertIn("[Clash]", log)

    def test_companions_are_not_hijacked(self):
        self._park_player_far()
        guard = self._put(self._guard(), 5, 5)
        self.engine.companion_manager.party.append(guard.id)
        bandit = self._spawn("bandit", 6, 5)
        hp = bandit.hp
        self.engine.turn_counter = TICK_INTERVAL
        self.engine.npc_conflict.update()
        self.assertEqual(bandit.hp, hp,
                         "party members act via companion_manager")

    def test_repelled_raid_spawns_visible_straggler(self):
        self._park_player_far()
        before = len(self.engine.npc_manager.npcs)
        spawned = self.engine.faction_ticker._spawn_raider()
        self.assertTrue(spawned)
        self.assertEqual(len(self.engine.npc_manager.npcs), before + 1)
        bandits = [n for n in self.engine.npc_manager.npcs.values()
                   if n.name == "Bandit"]
        self.assertTrue(bandits)
        px, py = self.engine.player.position
        bx, by = bandits[-1].position
        self.assertGreaterEqual(abs(bx - px) + abs(by - py), 6)

    def test_advance_turn_runs_the_system(self):
        self._park_player_far()
        self._put(self._guard(), 5, 5)
        bandit = self._spawn("bandit", 6, 5)
        hp = bandit.hp
        for _ in range(TICK_INTERVAL * 6):
            self.engine.advance_turn()
            if bandit.hp < hp or not bandit.is_active():
                break
        self.assertTrue(bandit.hp < hp or not bandit.is_active(),
                        "conflict must run from the game loop")


if __name__ == "__main__":
    unittest.main()
