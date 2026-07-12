"""Monster packs that fight as a group (P19.3).

Overworld hostiles near the player band into packs: they crown the
strongest as leader, pile onto one shared focus (the softest reachable
target), and break and flee when the leader falls. Solo monsters and
party-less fights are untouched."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

import unittest

from engine.game_engine import GameEngine
from world.monsters import build_monster
from world.world_map import TerrainType
from characters.character_types import CharacterClass
from llm.providers.heuristic import HeuristicProvider


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        for yy in range(4, 22):
            for xx in range(4, 22):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self.engine.world.map.remove_character(self.p)
        self.p.position = (13, 13)
        self.engine.world.map.place_character(self.p, 13, 13)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _mob(self, template, pos, mid, **over):
        m = build_monster(template, pos)
        m.id = mid
        for k, v in over.items():
            setattr(m, k, v)
        self.engine.npc_manager.add_npc(m)
        self.engine.world.map.place_character(m, *pos)
        return m


class TestPackFormation(_Base):
    def test_two_of_a_kind_form_a_pack(self):
        a = self._mob("wolf", (10, 10), "enc_a")
        b = self._mob("wolf", (11, 10), "enc_b")
        self.engine.monster_packs.update()
        self.assertIsNotNone(a.metadata.get("pack_id"))
        self.assertEqual(a.metadata.get("pack_id"), b.metadata.get("pack_id"))

    def test_a_lone_beast_is_no_pack(self):
        # a lone wolf of a unique kind gets no pack (other world hostiles
        # may band among themselves — assert this beast's own state)
        solo = self._mob("bog_lurker", (10, 10), "enc_solo")
        self.engine.monster_packs.update()
        self.assertIsNone(solo.metadata.get("pack_id"))
        self.assertIsNone(solo.metadata.get("focus_name"))

    def test_lair_kin_band_even_across_kinds(self):
        g = self._mob("goblin", (10, 10), "enc_g")
        b = self._mob("bandit", (11, 10), "enc_b")
        g.metadata["lair"] = "goblin_warren"
        b.metadata["lair"] = "goblin_warren"
        self.engine.monster_packs.update()
        self.assertIsNotNone(g.metadata.get("pack_id"))
        self.assertEqual(g.metadata.get("pack_id"), b.metadata.get("pack_id"))

    def test_leader_is_the_strongest(self):
        weak = self._mob("wolf", (10, 10), "enc_weak")
        strong = self._mob("wolf", (11, 10), "enc_strong",
                            max_hp=40, hp=40)
        self.engine.monster_packs.update()
        self.assertEqual(strong.metadata.get("pack_leader_id"), strong.id)
        self.assertEqual(weak.metadata.get("pack_leader_id"), strong.id)

    def test_stale_tags_are_cleared(self):
        a = self._mob("wolf", (10, 10), "enc_a")
        self._mob("wolf", (11, 10), "enc_b")
        self.engine.monster_packs.update()
        self.assertIsNotNone(a.metadata.get("focus_name"))
        # move the mate far off; the pack dissolves and the tag clears
        a.metadata["_gone"] = True
        for n in list(self.engine.npc_manager.npcs.values()):
            if n.id == "enc_b":
                n.position = (50, 50)
        self.engine.monster_packs.update()
        self.assertIsNone(a.metadata.get("focus_name"))


class TestPackFocus(_Base):
    def test_a_pack_shares_one_focus(self):
        a = self._mob("goblin", (10, 10), "enc_a")
        b = self._mob("goblin", (11, 10), "enc_b")
        self.engine.monster_packs.update()
        self.assertEqual(a.metadata.get("focus_name"), "player")
        self.assertEqual(b.metadata.get("focus_name"), "player")

    def test_focus_falls_on_the_softest_ally(self):
        ally = self._mob("wolf", (14, 13), "ally1",
                         name="Ally", hp=3, max_hp=30)
        ally.character_class = CharacterClass.RANGER   # a friend, not prey-kin
        self.engine.companion_manager.party.append(ally.id)
        g1 = self._mob("goblin", (10, 10), "enc_g1")
        g2 = self._mob("goblin", (11, 10), "enc_g2")
        self.engine.monster_packs.update()
        self.assertEqual(g1.metadata.get("focus_name"), "Ally")
        self.assertEqual(g2.metadata.get("focus_name"), "Ally",
                         "the whole pack piles onto the soft target")

    def test_a_healthy_party_draws_no_special_focus(self):
        ally = self._mob("wolf", (14, 13), "ally1", name="Ally",
                         hp=30, max_hp=30)
        ally.character_class = CharacterClass.RANGER
        self.engine.companion_manager.party.append(ally.id)
        g1 = self._mob("goblin", (10, 10), "enc_g1")
        self._mob("goblin", (11, 10), "enc_g2")
        self.engine.monster_packs.update()
        self.assertEqual(g1.metadata.get("focus_name"), "player")


class TestPackMorale(_Base):
    def _pack(self):
        leader = self._mob("wolf", (10, 10), "enc_lead", max_hp=40, hp=40)
        m1 = self._mob("wolf", (11, 10), "enc_m1")
        m2 = self._mob("wolf", (10, 11), "enc_m2")
        self.engine.monster_packs.update()
        self.assertEqual(m1.metadata.get("pack_leader_id"), leader.id)
        return leader, [m1, m2]

    def test_leader_death_breaks_the_pack(self):
        leader, mates = self._pack()
        leader.hp = 0
        if hasattr(leader, "defeat"):
            leader.defeat()
        self.engine.monster_packs.update()
        for m in mates:
            self.assertTrue(m.metadata.get("pack_broken"),
                            "the survivors lose their nerve")

    def test_a_broken_beast_flees(self):
        leader, mates = self._pack()
        leader.hp = 0
        if hasattr(leader, "defeat"):
            leader.defeat()
        self.engine.monster_packs.update()
        act = HeuristicProvider()._hostile_action(
            mates[0], {"player_position": self.p.position}, True)
        self.assertEqual(act["action"], "move")
        self.assertIn("breaks", act["dialog"])

    def test_a_living_leader_keeps_the_pack_steady(self):
        leader, mates = self._pack()
        self.engine.monster_packs.update()
        for m in mates:
            self.assertIsNone(m.metadata.get("pack_broken"))
        mates[0].metadata["howled"] = True     # past the first-sighting howl
        act = HeuristicProvider()._hostile_action(
            mates[0], {"player_position": self.p.position}, True)
        self.assertEqual(act["action"], "attack")


if __name__ == "__main__":
    unittest.main()
