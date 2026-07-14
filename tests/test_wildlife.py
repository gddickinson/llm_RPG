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


if __name__ == "__main__":
    unittest.main()
