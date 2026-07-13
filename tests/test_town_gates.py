"""P31.1d — town gates that close and lock.

The wall gates close at night and lock under an alarm; a closed gate turns
everyone back (its tile reverts to wall); forcing a shut gate is loud and a
crime. State persists.
"""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_gate_"))

import shutil
import tempfile
import unittest

from engine.game_engine import GameEngine
from engine.save_load import SaveManager
from world.world_map import TerrainType
from world.monsters import build_monster


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.tg = self.engine.town_gates
        self.wmap = self.engine.world.map
        self.gates = self.tg._gates()
        self.assertTrue(self.gates, "the walled town has gates")

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _time(self, period):
        self.engine.world.get_time_of_day = lambda: period


class TestOpenClose(_Base):
    def test_close_walls_the_gate_tile(self):
        n = self.tg.close_all()
        self.assertGreaterEqual(n, 1)
        for g in self.gates:
            if self.tg.state_of(g) == "closed":
                self.assertEqual(self.wmap.terrain[g[1]][g[0]],
                                 TerrainType.BUILDING)

    def test_a_closed_gate_turns_you_back(self):
        self.tg.close_all()
        g = next(x for x in self.gates if self.tg.state_of(x) == "closed")
        foe = build_monster("wolf", (g[0], g[1] + 1))
        self.engine.npc_manager.add_npc(foe)
        self.wmap.remove_character(foe)
        foe.position = (g[0], g[1] + 1)
        self.wmap.place_character(foe, *foe.position)
        self.assertFalse(self.wmap.move_character(foe, g[0], g[1]))

    def test_open_restores_the_road(self):
        self.tg.close_all()
        self.tg.open_all()
        for g in self.gates:
            self.assertEqual(self.tg.state_of(g), "open")
            self.assertIn(self.wmap.terrain[g[1]][g[0]],
                          (TerrainType.ROAD, TerrainType.BRIDGE))

    def test_never_shut_a_gate_on_someone(self):
        g = self.gates[0]
        occ = build_monster("wolf", g)
        self.engine.npc_manager.add_npc(occ)
        self.wmap.remove_character(occ)
        occ.position = g
        self.wmap.place_character(occ, *g)
        self.tg.close_all()
        self.assertEqual(self.tg.state_of(g), "open")   # couldn't shut it


class TestSync(_Base):
    def test_open_by_day(self):
        self._time("day")
        self.tg.close_all()
        self.tg.sync()
        self.assertTrue(all(self.tg.is_open(g) for g in self.gates))

    def test_closed_by_night(self):
        self._time("night")
        self.tg.sync()
        self.assertTrue(any(self.tg.state_of(g) == "closed"
                            for g in self.gates))

    def test_locked_under_alarm(self):
        self._time("day")
        # a tower guard sounds the alarm
        guard = next(iter(self.engine.npc_manager.npcs.values()))
        guard.metadata["alarmed"] = True
        self.tg.sync()
        self.assertTrue(any(self.tg.state_of(g) == "locked"
                            for g in self.gates))


class TestForce(_Base):
    def test_forcing_a_shut_gate_opens_it_loudly(self):
        self.tg.close_all(locked=True)
        g = next(x for x in self.gates if self.tg.state_of(x) == "locked")
        msg = self.tg.force_gate(g)
        self.assertIn("force", msg.lower())
        self.assertTrue(self.tg.is_open(g))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("[Law]", log)

    def test_an_open_gate_needs_no_forcing(self):
        self.tg.open_all()
        self.assertIn("open", self.tg.force_gate(self.gates[0]).lower())


class TestPersistence(_Base):
    def test_gate_state_round_trips(self):
        self.tg.close_all(locked=True)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="gates")
            eng2 = GameEngine(llm_provider="heuristic",
                              enable_npc_processes=False)
            sm.load(eng2, name="gates")
            for g in self.gates:
                self.assertEqual(eng2.town_gates.state_of(g),
                                 self.tg.state_of(g))
            eng2.end_game()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
