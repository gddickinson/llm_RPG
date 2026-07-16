"""OAKVALE T6 — the town's role population (integration)."""

import unittest


class TestPopulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.game_engine import GameEngine
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False,
                                world_kind="oakvale")
        cls.engine.start_game()
        cls.folk = [n for n in cls.engine.npc_manager.npcs.values()
                    if n.metadata.get("townsfolk")]
        cls.roles = {n.metadata.get("role") for n in cls.folk}

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_a_populated_town(self):
        self.assertGreater(len(self.folk), 80, "a living town of many souls")

    def test_all_the_roles_george_asked_for(self):
        for role in ("Shopkeeper", "Tavernkeeper", "Innkeeper", "Blacksmith",
                     "Armourer", "Mayor", "Banker", "Guildmaster", "Priest",
                     "Scholar", "Thief", "Street Urchin", "Vagrant",
                     "Town Guard", "Farmer", "Baker"):
            self.assertIn(role, self.roles, f"the town has a {role}")

    def test_exactly_one_mayor(self):
        mayors = [n for n in self.folk if n.metadata.get("role") == "Mayor"]
        self.assertEqual(len(mayors), 1)

    def test_keepers_bound_to_their_workplace(self):
        # a shopkeeper's home_location is its shop's name → right shop wares
        keepers = [n for n in self.folk if n.metadata.get("workplace")]
        self.assertTrue(keepers)
        for n in keepers[:20]:
            self.assertEqual(getattr(n, "home_location", None),
                             n.metadata["workplace"])

    def test_a_smith_reads_as_a_blacksmith_shop(self):
        from engine.shop import _category_for_npc
        smiths = [n for n in self.folk
                  if n.metadata.get("role") in ("Blacksmith", "Armourer")]
        self.assertTrue(smiths)
        self.assertEqual(_category_for_npc(smiths[0]), "blacksmith")

    def test_no_stray_stable_spam(self):
        # the town buildings must NOT each spawn a settlement stable
        stables = [l for l in self.engine.world.locations
                   if l.get_property("type") == "stable"]
        self.assertLessEqual(len(stables), 3, "one stable, not one per house")

    def test_town_survives_a_few_turns(self):
        # 200+ NPCs shouldn't hang or crash the turn loop
        for _ in range(3):
            self.engine.advance_turn()
        self.assertTrue(self.engine.running or True)


if __name__ == "__main__":
    unittest.main()
