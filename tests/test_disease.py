"""Disease & contagion tests (P8.2)."""

import random
import unittest

from engine.game_engine import GameEngine
from engine.disease import DISEASES, is_infected, try_cure_with_item
from items.item_registry import create_item


class TestDisease(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.system = self.engine.disease
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _villager(self):
        return next(n for n in self.engine.npc_manager.npcs.values()
                    if getattr(n.character_class, "value", "") in
                    ("villager", "merchant") and n.is_active())

    def test_content_is_data(self):
        self.assertGreaterEqual(len(DISEASES), 4)
        from items.data_validate import _check_diseases
        self.assertEqual(_check_diseases(), [])

    def test_infect_and_metadata(self):
        npc = self._villager()
        self.assertTrue(self.system.infect(npc, "rot_cough"))
        self.assertTrue(is_infected(npc))
        self.assertEqual(npc.metadata["disease"]["id"], "rot_cough")
        self.assertFalse(self.system.infect(npc, "marsh_fever"),
                         "one sickness at a time")

    def test_recovery_leaves_immunity(self):
        npc = self._villager()
        self.system.infect(npc, "winter_grippe")
        days = DISEASES["winter_grippe"]["duration_days"]
        self.engine.world.time += days * 24 * 60
        self.system.run_day()
        self.assertFalse(is_infected(npc))
        self.assertIn("winter_grippe",
                      npc.metadata["disease_immunity"])
        self.assertFalse(self.system.infect(npc, "winter_grippe"),
                         "immunity must block reinfection")

    def test_contagion_spreads_to_neighbors(self):
        npc = self._villager()
        self.system.infect(npc, "winter_grippe")
        wmap = self.engine.world.map
        nx, ny = npc.position
        wmap.remove_character(npc)
        wmap.place_character(npc, nx, ny)     # firmly on the overworld
        wmap.remove_character(self.player)
        self.player.position = (nx + 1, ny)
        wmap.place_character(self.player, nx + 1, ny)
        self.system.rng = random.Random(0)
        for _ in range(30):
            if is_infected(self.player):
                break
            self.system._spread(npc, [npc, self.player])
        self.assertTrue(is_infected(self.player),
                        "adjacent spread never happened in 30 rolls")

    def test_player_symptoms_weaken_but_never_kill(self):
        self.system.infect(self.player, "marsh_fever")
        self.player.hp = 3
        for _ in range(6):
            self.system._player_symptoms()
        self.assertEqual(self.player.hp, 1,
                         "disease must weaken, not kill")

    def test_the_right_remedy_cures(self):
        self.system.infect(self.player, "marsh_fever")
        wrong = create_item("potion")
        self.assertIsNone(try_cure_with_item(
            self.engine, self.player, wrong))
        self.assertTrue(is_infected(self.player))
        right = create_item("herb_bundle")
        msg = try_cure_with_item(self.engine, self.player, right)
        self.assertIn("lift", msg)
        self.assertFalse(is_infected(self.player))

    def test_use_item_flow_cures(self):
        self.system.infect(self.player, "marsh_fever")
        remedy = create_item("herb_bundle")
        self.player.inventory.append(remedy)
        result = self.engine.use_item(remedy.name)
        self.assertFalse(is_infected(self.player), result)

    def test_outbreak_announces_itself(self):
        self.system.rng = random.Random(1)
        started = 0
        for _ in range(60):
            started += self.system._maybe_outbreak(
                self.system._people())
            if started:
                break
        self.assertTrue(started, "no outbreak in 60 quiet nights")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("[Realm]", log)
        self.assertIn("whisper", log)

    def test_nightly_stack_runs_disease_day(self):
        npc = self._villager()
        self.system.infect(npc, "rot_cough")
        days = DISEASES["rot_cough"]["duration_days"]
        now = self.engine.world.time
        self.engine.world.time = now + days * 24 * 60
        self.engine.advance_turn()
        self.assertFalse(is_infected(npc),
                         "advance_turn's nightly stack must progress "
                         "diseases")

    def test_infection_state_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        self.system.infect(self.player, "rot_cough")
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="sick")
            self.system.cure(self.player)
            self.assertTrue(sm.load(self.engine, name="sick"))
            self.assertTrue(is_infected(self.engine.player))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
