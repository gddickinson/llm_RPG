"""I1 — ambient character-to-character social interactions (headless).

Two adjacent, idle, friendly/hostile neighbours play a relationship-appropriate
coordinated interaction (handshake/hug/kiss/square-up), so the social graph becomes
visible in the world.
"""

import unittest

from engine import interactions


class _Char:
    def __init__(self, cid, name, pos, cls="villager"):
        self.id = cid
        self.name = name
        self.position = pos
        self.character_class = type("K", (), {"value": cls})()
        self.metadata = {}
        self.relationships = {}
        self._active = True

    def is_active(self):
        return self._active

    def get_relationship(self, other):
        return self.relationships.get(other, 0)

    def modify_relationship(self, other, delta):
        self.relationships[other] = max(
            -100, min(100, self.relationships.get(other, 0) + delta))

    def add_memory(self, event, importance=1):
        self.memories = getattr(self, "memories", [])
        self.memories.append(event)


class _MM:
    def __init__(self):
        self.events = []

    def add_event(self, e, *a, **k):
        self.events.append(e)


class _Engine:
    def __init__(self, chars, player_pos=(5, 5)):
        self.npc_manager = type("N", (), {"npcs": {c.id: c for c in chars}})()
        self.player = _Char("player", "You", player_pos)
        self.turn_counter = 0
        self.memory_manager = _MM()


def _pair(cls="villager"):
    return _Char("a", "Ann", (5, 5), cls), _Char("b", "Ben", (6, 5), cls)


class TestSocialKind(unittest.TestCase):
    def test_couple_kisses(self):
        a, b = _pair()
        a.metadata["partner"] = "b"
        b.metadata["partner"] = "a"
        self.assertEqual(interactions.social_kind(a, b), "kiss")

    def test_friends_hug(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        b.modify_relationship("a", 60)
        self.assertEqual(interactions.social_kind(a, b), "hug")

    def test_social_friend_latch_hugs(self):
        a, b = _pair()
        a.metadata["social"] = {"friend:b": True}
        self.assertEqual(interactions.social_kind(a, b), "hug")

    def test_acquaintances_shake_hands(self):
        a, b = _pair()
        a.modify_relationship("b", 20)
        self.assertEqual(interactions.social_kind(a, b), "handshake")

    def test_feud_latch_squares_up(self):
        a, b = _pair()
        a.metadata["social"] = {"feud:b": True}
        self.assertEqual(interactions.social_kind(a, b), "squareup")

    def test_low_regard_squares_up(self):
        a, b = _pair()
        a.modify_relationship("b", -50)
        self.assertEqual(interactions.social_kind(a, b), "squareup")

    def test_strangers_do_nothing(self):
        a, b = _pair()
        self.assertIsNone(interactions.social_kind(a, b))

    def test_couple_kisses_even_when_soured(self):
        # the partner link wins over a momentary negative reading
        a, b = _pair()
        a.metadata["partner"] = "b"
        a.modify_relationship("b", -50)
        self.assertEqual(interactions.social_kind(a, b), "kiss")


class TestPerformSocial(unittest.TestCase):
    def test_plays_both_halves_faces_and_bumps_regard(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        b.modify_relationship("a", 60)
        eng = _Engine([a, b])
        kind = interactions.perform_social(eng, a, b)
        self.assertEqual(kind, "hug")
        self.assertEqual(a.metadata.get("_emote"), "hug")
        self.assertEqual(b.metadata.get("_emote"), "hug")
        self.assertIn("_face", a.metadata)          # turned to face b
        self.assertIn("_face", b.metadata)
        self.assertGreater(a.get_relationship("b"), 60)  # regard nudged up
        self.assertGreater(b.get_relationship("a"), 60)

    def test_square_up_lowers_regard(self):
        a, b = _pair()
        a.modify_relationship("b", -50)
        b.modify_relationship("a", -50)
        eng = _Engine([a, b])
        self.assertEqual(interactions.perform_social(eng, a, b), "squareup")
        self.assertLess(a.get_relationship("b"), -50)

    def test_strangers_no_op(self):
        a, b = _pair()
        eng = _Engine([a, b])
        self.assertIsNone(interactions.perform_social(eng, a, b))
        self.assertNotIn("_emote", a.metadata)

    def test_stamps_the_cooldown_turn(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        eng = _Engine([a, b])
        eng.turn_counter = 42
        interactions.perform_social(eng, a, b)
        self.assertEqual(a.metadata.get("_social_turn"), 42)
        self.assertEqual(b.metadata.get("_social_turn"), 42)


class TestUpdateSocial(unittest.TestCase):
    def test_adjacent_friends_interact(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        b.modify_relationship("a", 60)
        eng = _Engine([a, b])
        interactions.update_social(eng, chance=1.0)   # force the pass
        self.assertEqual(a.metadata.get("_emote"), "hug")
        self.assertEqual(b.metadata.get("_emote"), "hug")

    def test_distant_pair_does_not_interact(self):
        a, b = _pair()
        b.position = (20, 20)                          # far apart
        a.modify_relationship("b", 60)
        eng = _Engine([a, b])
        interactions.update_social(eng, chance=1.0)
        self.assertNotIn("_emote", a.metadata)

    def test_hostiles_excluded(self):
        a = _Char("a", "Grak", (5, 5), cls="monster")
        b = _Char("b", "Snik", (6, 5), cls="monster")
        a.modify_relationship("b", 60)
        eng = _Engine([a, b])
        interactions.update_social(eng, chance=1.0)
        self.assertNotIn("_emote", a.metadata)

    def test_cooldown_blocks_immediate_repeat(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        b.modify_relationship("a", 60)
        eng = _Engine([a, b])
        interactions.update_social(eng, chance=1.0)
        a.metadata.pop("_emote", None)                 # clear the played clip
        b.metadata.pop("_emote", None)
        interactions.update_social(eng, chance=1.0)     # same turn — cooled down
        self.assertNotIn("_emote", a.metadata)

    def test_busy_character_not_interrupted(self):
        a, b = _pair()
        a.modify_relationship("b", 60)
        a.metadata["_stance"] = "sit"                   # a is busy
        eng = _Engine([a, b])
        interactions.update_social(eng, chance=1.0)
        self.assertNotIn("_emote", b.metadata)


class TestPlayerSocial(unittest.TestCase):
    """I2 — the player offers an adjacent NPC a warm gesture from the menu."""

    def _eng_npc(self, rel=0, romance=None, partner=False):
        npc = _Char("npc", "Bess", (6, 5))
        eng = _Engine([npc])                 # eng.player has id "player"
        npc.modify_relationship("player", rel)
        if romance:
            npc.metadata["romance"] = romance
        if partner:
            npc.metadata["partner"] = "player"
        return eng, npc

    def test_stranger_offers_a_handshake(self):
        eng, npc = self._eng_npc(rel=0)
        opt = interactions.player_social_option(eng, npc)
        self.assertEqual(opt[0], "handshake")
        self.assertIn("Bess", opt[1])

    def test_friend_offers_an_embrace(self):
        eng, npc = self._eng_npc(rel=45)
        self.assertEqual(interactions.player_social_option(eng, npc)[0], "hug")

    def test_sweetheart_offers_a_kiss(self):
        eng, npc = self._eng_npc(romance="sweetheart")
        self.assertEqual(interactions.player_social_option(eng, npc)[0], "kiss")

    def test_cold_npc_offers_nothing(self):
        eng, npc = self._eng_npc(rel=-10)
        self.assertIsNone(interactions.player_social_option(eng, npc))

    def test_player_social_plays_warms_and_replies(self):
        eng, npc = self._eng_npc(rel=45)
        reply = interactions.player_social(eng, npc, "hug")
        self.assertEqual(eng.player.metadata.get("_emote"), "hug")
        self.assertEqual(npc.metadata.get("_emote"), "hug")
        self.assertGreater(npc.get_relationship("player"), 45)  # bond warmed
        self.assertIn("Bess", reply)
        self.assertTrue(getattr(npc, "memories", []))           # fond memory


if __name__ == "__main__":
    unittest.main()
