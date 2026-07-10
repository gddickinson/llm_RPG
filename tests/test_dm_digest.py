"""World digest tests (P6.2)."""

import json
import unittest

from engine.game_engine import GameEngine


class TestDMDigest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_digest_shape_and_serializability(self):
        digest = self.engine.dm.digest()
        for key in ("meta", "player", "npcs", "world",
                    "recent_events", "dm"):
            self.assertIn(key, digest)
        # Must round-trip as JSON — the bridge writes this to disk
        encoded = json.dumps(digest)
        self.assertEqual(json.loads(encoded)["player"]["name"],
                         self.player.name)

    def test_player_section(self):
        from engine.skill_progression import add_skill_xp, BASE_XP
        add_skill_xp(self.player, "mining", BASE_XP)
        self.engine.quest_manager.accept_quest("tavern_intro")
        digest = self.engine.dm.digest()
        p = digest["player"]
        self.assertEqual(p["level"], self.player.level)
        self.assertEqual(p["skills"]["mining"], 2)
        self.assertTrue(any(q["id"] == "tavern_intro"
                            for q in p["active_quests"]))
        self.assertIn("weapon", p["equipment"])

    def test_npc_roster_excludes_spawns_and_shows_feelings(self):
        from world.monsters import build_monster
        self.engine.npc_manager.add_npc(build_monster("wolf", (50, 50)))
        goren = self.engine.npc_manager.get_npc("tavernkeeper_01")
        goren.modify_relationship(self.player.id, 40)
        goren.metadata["opinions"] = ["A fine customer."]
        digest = self.engine.dm.digest()
        ids = [n["id"] for n in digest["npcs"]]
        self.assertIn("tavernkeeper_01", ids)
        self.assertFalse(any(i.startswith("enc_") for i in ids))
        entry = next(n for n in digest["npcs"]
                     if n["id"] == "tavernkeeper_01")
        self.assertEqual(entry["feeling_toward_player"], 40)
        self.assertEqual(entry["latest_opinion"], "A fine customer.")

    def test_world_section_reflects_systems(self):
        self.engine.world_director._apply(
            {"type": "shortage", "item_id": "ale"})
        self.engine.world_director.rumors = ["The fen glows at night."]
        digest = self.engine.dm.digest()
        w = digest["world"]
        self.assertIn("ale", w["shortages_minutes_left"])
        self.assertIn("The fen glows at night.", w["rumors"])
        self.assertIn("brigands", w["factions"])
        self.assertTrue(any(loc["name"] == "The Murkfen"
                            for loc in w["locations"]))

    def test_monster_census(self):
        from world.monsters import build_monster
        for _ in range(2):
            self.engine.npc_manager.add_npc(
                build_monster("wolf", (50, 50)))
        digest = self.engine.dm.digest()
        self.assertGreaterEqual(
            digest["world"]["monsters_at_large"].get("Wolf", 0), 2)

    def test_dm_section_tracks_notebook_and_budget(self):
        self.engine.dm.narrate("The mist thickens.")
        self.engine.dm.adjust_faction("villagers", 2)
        digest = self.engine.dm.digest()
        d = digest["dm"]
        self.assertLess(d["budget_remaining"], 12)
        self.assertTrue(any(e["command"] == "narrate"
                            for e in d["notebook_tail"]))

    def test_digest_is_compact(self):
        digest = self.engine.dm.digest()
        size = len(json.dumps(digest))
        self.assertLess(size, 20000,
                        f"digest is {size} bytes — keep it promptable")


if __name__ == "__main__":
    unittest.main()
