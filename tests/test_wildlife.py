"""P32.3 — neutral wildlife: a bestiary of prey (and a fox).

Animals spawn in the wilderness, wander and FLEE the player, never attack
(ANIMAL is not a HOSTILE_CLASS, so pursuit/conflict/hostile-AI ignore them),
and are huntable — a felled beast drops its own loot table (hide/meat) and
trains Hunting.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_wild_"))

import random
import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world import wildlife


class TestRoster(unittest.TestCase):
    def test_roster_loads(self):
        self.assertIn("deer", wildlife.ROSTER)
        self.assertIn("fox", wildlife.species_ids())

    def test_build_is_a_neutral_animal(self):
        a = wildlife.build_wildlife("deer", (5, 5))
        self.assertEqual(a.character_class.value, "animal")
        self.assertTrue(a.metadata["wildlife"])
        self.assertTrue(a.metadata["loot_table"])

    def test_a_fox_preys_on_something(self):
        self.assertTrue(wildlife.ROSTER["fox"].get("preys_on"))


class TestNotHostile(unittest.TestCase):
    def test_animal_is_not_a_pursuit_target(self):
        from engine.pursuit import HOSTILE_CLASSES
        self.assertNotIn("animal", HOSTILE_CLASSES)


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.wl = self.engine.wildlife
        self.wmap = self.engine.world.map
        self.px, self.py = self.wmap.width // 2, self.wmap.height // 2
        for y in range(self.py - 10, self.py + 10):
            for x in range(self.px - 10, self.px + 10):
                if 0 <= x < self.wmap.width and 0 <= y < self.wmap.height:
                    self.wmap.terrain[y][x] = TerrainType.GRASS
        self.wmap.remove_character(self.engine.player)
        self.engine.player.position = (self.px, self.py)
        self.wmap.place_character(self.engine.player, self.px, self.py)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _animals(self):
        return [n for n in self.engine.npc_manager.npcs.values()
                if (n.metadata or {}).get("wildlife")]


class TestSpawn(_Base):
    def test_a_sighting_appears_in_the_wild(self):
        self.wl.rng = random.Random(0)
        self.wl.rng.random = lambda: 0.0     # force the roll
        got = None
        for _ in range(10):
            got = self.wl.maybe_spawn()
            if got:
                break
        self.assertIsNotNone(got)
        self.assertTrue(self._animals())

    def test_spawn_is_capped(self):
        self.wl.rng.random = lambda: 0.0
        for _ in range(40):
            self.wl.maybe_spawn()
        self.assertLessEqual(len(self._animals()), wildlife.MAX_NEARBY)


class TestBehaviour(_Base):
    def _place(self, species, pos):
        a = wildlife.build_wildlife(species, pos)
        self.engine.npc_manager.add_npc(a)
        self.wmap.place_character(a, *pos)
        return a

    def test_it_flees_the_player(self):
        deer = self._place("deer", (self.px + 2, self.py))   # inside timid range
        d0 = max(abs(deer.position[0] - self.px),
                 abs(deer.position[1] - self.py))
        self.wl.rng = random.Random(3)
        for _ in range(4):
            self.wl.run_turn()
        d1 = max(abs(deer.position[0] - self.px),
                 abs(deer.position[1] - self.py))
        self.assertGreater(d1, d0, "a spooked deer opens distance")

    def test_it_never_moves_onto_the_player(self):
        self._place("rabbit", (self.px + 1, self.py))
        for _ in range(8):
            self.wl.run_turn()
        occupant = self.wmap.get_character_at(self.px, self.py)
        self.assertIs(occupant, self.engine.player)


class TestHuntable(_Base):
    def test_a_felled_deer_drops_meat_and_hide(self):
        deer = wildlife.build_wildlife("deer", (self.px + 3, self.py))
        from items.loot_tables import generate_loot
        drops = generate_loot(deer, rng=random.Random(1), drop_count=6)
        names = " ".join(str(d).lower() for d in drops)
        self.assertTrue(drops)
        self.assertTrue("meat" in names or "hide" in names)

    def test_felling_a_beast_trains_hunting(self):
        from engine.skill_progression import train_hunting, get_skill_xp
        deer = wildlife.build_wildlife("deer", (self.px + 3, self.py))
        before = get_skill_xp(self.engine.player, "hunting")
        train_hunting(self.engine, deer)
        self.assertGreater(get_skill_xp(self.engine.player, "hunting"), before)


class TestPredatorPrey(_Base):
    """P32.4 — the fox hunts, the prey flees the fox (player kept far away)."""

    def _place(self, species, pos):
        a = wildlife.build_wildlife(species, pos)
        self.engine.npc_manager.add_npc(a)
        self.wmap.place_character(a, *pos)
        return a

    def setUp(self):
        super().setUp()
        # the wildlife brain only manages animals within SIGHT_RADIUS of the
        # player, so keep it CLOSE enough to manage the pair but far enough
        # (> each animal's timid radius) not to spook them itself
        near = (self.px, self.py + 9)
        self.wmap.remove_character(self.engine.player)
        self.engine.player.position = near
        self.wmap.place_character(self.engine.player, *near)
        self.wl.rng = random.Random(5)

    def test_a_fox_closes_on_a_rabbit(self):
        fox = self._place("fox", (self.px, self.py))
        rabbit = self._place("rabbit", (self.px + 6, self.py))
        d0 = self.wl._cheb(fox.position, rabbit.position)
        # rabbit held still so we measure the fox's approach
        self.wl._flee = lambda a, p: None
        for _ in range(3):
            self.wl.run_turn()
        # either it closed the gap or already made the kill (rabbit gone)
        gone = rabbit.id not in self.engine.npc_manager.npcs
        self.assertTrue(gone or
                        self.wl._cheb(fox.position, rabbit.position) < d0)

    def test_the_fox_makes_the_kill(self):
        fox = self._place("fox", (self.px, self.py))
        rabbit = self._place("rabbit", (self.px + 1, self.py))
        self.wl._make_kill(fox, rabbit)
        self.assertNotIn(rabbit.id, self.engine.npc_manager.npcs)
        self.assertTrue(fox.metadata.get("fed"))

    def test_prey_flees_a_predator(self):
        fox = self._place("fox", (self.px, self.py))
        rabbit = self._place("rabbit", (self.px + 2, self.py))
        threat = self.wl._nearest_predator(rabbit)
        self.assertIs(threat, fox)


class TestPopulation(_Base):
    """P32.4b — the nightly herd rises and falls."""

    def _place(self, species, pos):
        a = wildlife.build_wildlife(species, pos)
        self.engine.npc_manager.add_npc(a)
        self.wmap.place_character(a, *pos)
        return a

    def _count(self, species=None):
        return len([a for a in self._animals()
                    if species is None or
                    (a.metadata or {}).get("species") == species])

    def test_a_fed_predator_breeds(self):
        fox = self._place("fox", (self.px, self.py))
        fox.metadata["fed"] = True
        self.wl.rng = random.Random(1)
        self.wl.rng.random = lambda: 0.0            # force the breed roll
        before = self._count("fox")
        self.wl.run_day()
        self.assertGreater(self._count("fox"), before)
        self.assertNotIn("fed", fox.metadata)       # the flag is consumed

    def test_a_starving_predator_dies(self):
        fox = self._place("fox", (self.px, self.py))   # no `fed` flag → hungry
        self.wl.rng = random.Random(1)
        self.wl.rng.random = lambda: 0.0            # force the starve roll
        self.wl.run_day()
        self.assertEqual(self._count("fox"), 0)

    def test_a_lone_prey_does_not_breed(self):
        self._place("deer", (self.px, self.py))
        self.wl.rng.random = lambda: 0.0
        self.wl.run_day()
        self.assertEqual(self._count("deer"), 1)    # needs company

    def test_game_near_a_town_stocks_its_larder(self):
        prod = self.engine.production
        settlements = prod._settlements()
        if not settlements:
            self.skipTest("world has no settlements")
        s = settlements[0]
        try:
            cx, cy = s.center()
        except Exception:
            cx, cy = s.x, s.y
        # drop a few deer right by the town
        for dx in (-1, 0, 1):
            self._place("deer", (cx + dx, cy + 2))
        store = prod.store_of(s.name)
        before = store.get("raw_meat", 0)
        self.wl.run_day()
        self.assertGreater(prod.store_of(s.name).get("raw_meat", 0), before)

    def test_breeding_stops_at_the_cap(self):
        # seed a herd just under the cap, then let it breed every night — it
        # rises TO the cap and holds there, never past it
        placed = 0
        for i in range(wildlife.MAX_POPULATION - 2):
            x = self.px - 5 + (i % 6)
            y = self.py - 4 + (i // 6)
            if self.wl._walkable(x, y):
                self._place("deer", (x, y))
                placed += 1
        self.wl.rng.random = lambda: 0.0        # force every breed roll
        for _ in range(6):
            self.wl.run_day()
        self.assertLessEqual(self._count(), wildlife.MAX_POPULATION)
        self.assertGreater(self._count(), placed)   # it did grow toward the cap


if __name__ == "__main__":
    unittest.main()
