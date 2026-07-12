"""M.10c — personality-driven AID.

How freely a character helps another depends on WHO they are: the
relationship they hold, their personality traits, and their alignment.
A healer companion mends a wounded ally it's willing to help — and
withholds from one it dislikes.
"""

import unittest

from engine.game_engine import GameEngine
from engine import party_aid
from world.world_map import TerrainType


class _Char:
    """A tiny stand-in for willingness scoring (no engine needed)."""
    def __init__(self, cid, rels=None, traits=(), align=""):
        self.id = cid
        self.relationships = dict(rels or {})
        self.personality = {"traits": list(traits)}
        self.metadata = {"alignment": align} if align else {}

    def get_relationship(self, other):
        return self.relationships.get(other, 0)


class TestWillingness(unittest.TestCase):
    def test_always_helps_itself(self):
        me = _Char("me")
        self.assertEqual(party_aid.aid_willingness(me, me), 100)

    def test_neutral_stranger_is_baseline(self):
        a, b = _Char("a"), _Char("b")
        self.assertEqual(party_aid.aid_willingness(a, b), party_aid.BASE)
        self.assertTrue(party_aid.will_aid(a, b))

    def test_a_loyal_soul_helps_more(self):
        loyal = _Char("l", traits=["loyal", "kind"])
        selfish = _Char("s", traits=["selfish", "greedy"])
        b = _Char("b")
        self.assertGreater(party_aid.aid_willingness(loyal, b),
                           party_aid.aid_willingness(selfish, b))

    def test_a_soured_relationship_withholds_aid(self):
        giver = _Char("g", rels={"foe": -60})
        foe = _Char("foe")
        self.assertFalse(party_aid.will_aid(giver, foe))

    def test_a_friend_is_readily_helped(self):
        giver = _Char("g", rels={"pal": 40})
        pal = _Char("pal")
        self.assertTrue(party_aid.will_aid(giver, pal))

    def test_alignment_shifts_willingness(self):
        good = _Char("good", align="lawful good")
        evil = _Char("evil", align="neutral evil")
        b = _Char("b")
        self.assertGreater(party_aid.aid_willingness(good, b),
                           party_aid.aid_willingness(evil, b))


class _PartyBase(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.healer = self.engine.npc_manager.get_npc("minstrel_01")
        self.engine.companion_manager.party.append("minstrel_01")
        px, py = self.player.position
        for yy in range(py - 2, py + 3):
            for xx in range(px - 2, px + 3):
                if 0 <= xx < self.wmap.width and 0 <= yy < self.wmap.height:
                    self.wmap.terrain[yy][xx] = TerrainType.GRASS
        self.wmap.remove_character(self.healer)
        self.healer.position = (px, py + 1)
        self.wmap.place_character(self.healer, px, py + 1)
        # make it a real healer: knows Heal, has mana
        self.healer.metadata["spells_known"] = ["heal"]
        self.healer.metadata["mana"] = 20
        self.healer.relationships[self.player.id] = 30   # fond of the hero

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestHealerMendsAllies(_PartyBase):
    def test_a_healer_mends_a_wounded_hero(self):
        self.player.hp = int(self.player.max_hp * 0.3)
        before = self.player.hp
        self.engine.companion_manager.update()
        self.assertGreater(self.player.hp, before)

    def test_mending_spends_mana(self):
        self.player.hp = int(self.player.max_hp * 0.3)
        m0 = self.healer.metadata["mana"]
        self.engine.companion_manager.update()
        self.assertLess(self.healer.metadata["mana"], m0)

    def test_a_healer_withholds_from_a_disliked_ally(self):
        self.healer.relationships[self.player.id] = -60   # can't stand them
        self.player.hp = int(self.player.max_hp * 0.3)
        before = self.player.hp
        self.engine.companion_manager.update()
        self.assertEqual(self.player.hp, before)          # no mending

    def test_no_mana_no_mending(self):
        self.healer.metadata["mana"] = 0
        self.player.hp = int(self.player.max_hp * 0.3)
        before = self.player.hp
        self.engine.companion_manager.update()
        self.assertEqual(self.player.hp, before)

    def test_a_non_healer_does_not_mend(self):
        self.healer.metadata["spells_known"] = []          # no Heal
        self.player.hp = int(self.player.max_hp * 0.3)
        before = self.player.hp
        self.engine.companion_manager.update()
        self.assertEqual(self.player.hp, before)

    def test_a_hale_hero_is_not_mended(self):
        self.player.hp = self.player.max_hp
        m0 = self.healer.metadata["mana"]
        self.engine.companion_manager.update()
        self.assertEqual(self.healer.metadata["mana"], m0)  # no mana spent


if __name__ == "__main__":
    unittest.main()
