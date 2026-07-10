"""Trespass tests (P9A.4) — uninvited entry is witnessed."""

import unittest

from engine.game_engine import GameEngine
from characters.factions import Faction, get_rep, set_rep


class TestTrespass(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.engine.world.time = 12 * 60          # noon

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _home(self):
        return next(l for l in self.engine.world.locations
                    if "farmhouse" in l.name.lower()
                    and l.name in self.engine.interiors)

    def _enter(self, loc, forced=False):
        door = self.engine.door_manager.door(loc.name)
        if forced:
            door["state"] = "broken"
            day = self.engine.world.time // (24 * 60)
            self.player.metadata["forced_entry_day"] = day
        else:
            door["state"] = "open"
        wmap = self.engine.world.map
        wmap.remove_character(self.player)
        self.player.position = (loc.x, loc.y)
        wmap.place_character(self.player, loc.x, loc.y)
        return self.engine.enter_building(loc)

    def _owner_at(self, loc, dx, dy):
        owner = self.engine.homes.owner_of(loc.name)
        wmap = self.engine.world.map
        wmap.remove_character(owner)
        owner.position = (loc.x + dx, loc.y + dy)
        wmap.place_character(owner, *owner.position)
        return owner

    def test_public_houses_cost_nothing(self):
        tavern = next(l for l in self.engine.world.locations
                      if "tavern" in l.name.lower()
                      and l.name in self.engine.interiors)
        before = get_rep(self.player, Faction.VILLAGERS)
        self._enter(tavern)
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before)

    def test_witnessed_trespass_objected_and_costs(self):
        loc = self._home()
        owner = self._owner_at(loc, 1, 1)     # home
        before = get_rep(self.player, Faction.VILLAGERS)
        rel_before = owner.relationships.get(self.player.id, 0)
        msg_log_len = len(self.engine.memory_manager.game_history)
        self._enter(loc)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager
                       .game_history[msg_log_len:])
        self.assertIn("no business", log)
        self.assertLess(get_rep(self.player, Faction.VILLAGERS),
                        before)
        self.assertLess(owner.relationships.get(self.player.id, 0),
                        rel_before)
        self.assertIn("broke into my home",
                      " ".join(owner.memories))

    def test_unwitnessed_daytime_sneak_is_free_but_counted(self):
        loc = self._home()
        owner = self._owner_at(loc, 20, 15)   # far away, daytime
        before = get_rep(self.player, Faction.VILLAGERS)
        self._enter(loc)
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before)
        self.assertEqual(
            self.player.metadata.get("unseen_break_ins"), 1)

    def test_night_means_everyone_is_home(self):
        self.engine.world.time = \
            (self.engine.world.time // (24 * 60)) * 24 * 60 + 23 * 60
        loc = self._home()
        self._owner_at(loc, 20, 15)  # position irrelevant at night
        before = get_rep(self.player, Faction.VILLAGERS)
        self._enter(loc)
        self.assertLess(get_rep(self.player, Faction.VILLAGERS),
                        before)

    def test_breaking_in_is_a_crime_guards_hear(self):
        loc = self._home()
        self._owner_at(loc, 1, 1)
        guard = next(n for n in self.engine.npc_manager.npcs.values()
                     if getattr(n.character_class, "value", "") ==
                     "guard")
        wmap = self.engine.world.map
        wmap.remove_character(guard)
        guard.position = (loc.x + 5, loc.y)
        wmap.place_character(guard, *guard.position)
        v_before = get_rep(self.player, Faction.VILLAGERS)
        g_before = get_rep(self.player, Faction.GUARDS)
        self._enter(loc, forced=True)
        self.assertLess(get_rep(self.player, Faction.VILLAGERS),
                        v_before)
        self.assertLess(get_rep(self.player, Faction.GUARDS),
                        g_before)
        self.assertEqual(guard.metadata.get("alert"),
                         [loc.x + loc.width // 2,
                          loc.y + loc.height - 1])
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-8:])
        self.assertIn("THE WATCH", log)

    def test_alerted_guard_converges_then_challenges(self):
        from llm.providers.heuristic import HeuristicProvider
        guard = next(n for n in self.engine.npc_manager.npcs.values()
                     if getattr(n.character_class, "value", "") ==
                     "guard")
        gx, gy = guard.position
        guard.metadata["alert"] = [gx + 3, gy]
        provider = HeuristicProvider()
        response = provider.get_npc_action(guard, {}, [], "street")
        self.assertEqual(response["action"], "move")
        guard.metadata["alert"] = [gx + 1, gy]
        response = provider.get_npc_action(guard, {}, [], "street")
        self.assertIn("Who goes there", response["dialog"])
        self.assertNotIn("alert", guard.metadata)

    def test_repeat_break_ins_reach_the_bounty_ladder(self):
        from engine.retaliation import THRESHOLD
        loc = self._home()
        self._owner_at(loc, 1, 1)
        set_rep(self.player, Faction.GUARDS, -25)
        self._enter(loc, forced=True)
        self.assertLessEqual(get_rep(self.player, Faction.GUARDS),
                             THRESHOLD)
        # two crimes past the line: the watch posts the bounty
        self.engine.world.time += 24 * 60
        notes = self.engine.retaliation.run_night()
        self.assertTrue(any("price on your head" in n for n in notes),
                        f"rep {get_rep(self.player, Faction.GUARDS)}: "
                        f"{notes}")

    def test_derelict_buildings_have_no_one_to_care(self):
        derelicts = [l for l in self.engine.world.locations
                     if l.get_property("derelict", False)
                     and l.name in self.engine.interiors]
        if not derelicts:
            self.skipTest("no derelict building this world")
        before = get_rep(self.player, Faction.VILLAGERS)
        self._enter(derelicts[0])
        self.assertEqual(get_rep(self.player, Faction.VILLAGERS),
                         before)


if __name__ == "__main__":
    unittest.main()
