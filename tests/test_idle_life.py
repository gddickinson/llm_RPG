"""P34.4 — individuality & idle life: seeded idle desync + ambient fidgets +
startle reactions."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_idle_"))

import unittest

from engine import anim


class _E:
    def __init__(self, v):
        self.value = v


class _Char:
    def __init__(self, cid, role="villager", pos=(5, 5)):
        self.id = cid
        self.character_class = _E(role)
        self.position = pos
        self.metadata = {}

    def is_active(self):
        return True


class _NPCMgr:
    def __init__(self, npcs):
        self.npcs = {n.id: n for n in npcs}


class _Engine:
    def __init__(self, npcs, player):
        self.npc_manager = _NPCMgr(npcs)
        self.player = player


class _RNG:
    """A deterministic rng: random() = a fixed value, choice() = first item."""
    def __init__(self, val=0.0):
        self.val = val

    def random(self):
        return self.val

    def choice(self, seq):
        return seq[0]


# --------------------------------------------------------------- idle desync

class TestIdleDesync(unittest.TestCase):
    def test_seeds_differ_between_characters(self):
        from ui.body_renderer import _ensure_anim
        a = _ensure_anim(_Char("alice"))
        b = _ensure_anim(_Char("bob"))
        self.assertNotEqual((a["idle_phase"], a["idle_rate"]),
                            (b["idle_phase"], b["idle_rate"]))
        self.assertGreaterEqual(a["idle_rate"], 0.80)
        self.assertLessEqual(a["idle_rate"], 1.30)

    def test_idle_phase_advances_by_its_rate(self):
        from ui.body_renderer import _ensure_anim, update_anim
        c = _Char("carol")
        anim0 = _ensure_anim(c)
        p0, rate = anim0["idle_phase"], anim0["idle_rate"]
        update_anim(c, 0.1)                       # not moving → idle advances
        p1 = c.metadata["_anim"]["idle_phase"]
        self.assertAlmostEqual((p1 - p0) % (2 * 3.14159), 0.1 * 1.6 * rate,
                               delta=0.02)


# --------------------------------------------------------------- ambient life

class TestIdleFidgets(unittest.TestCase):
    def test_idle_villager_fidgets(self):
        v = _Char("villager1")
        eng = _Engine([v], _Char("hero"))
        anim.update_idle_life(eng, rng=_RNG(0.0))
        self.assertIn(v.metadata.get("_emote"), anim._FIDGETS)

    def test_hostile_never_fidgets(self):
        mon = _Char("wolf1", role="monster")
        eng = _Engine([mon], _Char("hero"))
        anim.update_idle_life(eng, rng=_RNG(0.0))
        self.assertIsNone(mon.metadata.get("_emote"))

    def test_startle_near_a_hostile(self):
        v = _Char("villager2", pos=(5, 5))
        mon = _Char("brigand1", role="brigand", pos=(6, 5))     # adjacent
        eng = _Engine([v, mon], _Char("hero", pos=(40, 40)))
        anim.update_idle_life(eng, rng=_RNG(0.0))
        self.assertEqual(v.metadata.get("_bubble"), "alert")
        self.assertIn("_face", v.metadata)                      # turned to it
        self.assertIsNone(v.metadata.get("_emote"))             # no calm fidget

    def test_busy_character_is_left_alone(self):
        v = _Char("busy")
        v.metadata["_stance"] = "sit"
        eng = _Engine([v], _Char("hero"))
        anim.update_idle_life(eng, rng=_RNG(0.0))
        self.assertIsNone(v.metadata.get("_emote"))

    def test_low_roll_yields_no_fidget(self):
        v = _Char("still")
        eng = _Engine([v], _Char("hero", pos=(40, 40)))
        anim.update_idle_life(eng, rng=_RNG(0.99))             # roll above chance
        self.assertIsNone(v.metadata.get("_emote"))

    def test_tradesfolk_busy_themselves_with_their_craft(self):
        # a smith hammers, a farmer sweeps, a cleric kneels (P34.22)
        for role, action in (("blacksmith", "hammer"), ("farmer", "sweep"),
                             ("cleric", "kneel")):
            self.assertEqual(anim._role_action(_Char("w", role)), action)
        self.assertIsNone(anim._role_action(_Char("v", "villager")))

    def test_idle_smith_hammers(self):
        smith = _Char("smith1", role="blacksmith")
        eng = _Engine([smith], _Char("hero", pos=(40, 40)))
        anim.update_idle_life(eng, rng=_RNG(0.0))          # always fires
        self.assertEqual(smith.metadata.get("_emote"), "hammer")

    def test_merchant_hawks_wares(self):
        m = _Char("merchant1", role="merchant")
        eng = _Engine([m], _Char("hero", pos=(40, 40)))
        anim.update_idle_life(eng, rng=_RNG(0.0))
        self.assertIn(m.metadata.get("_emote"), ("beckon", "wave"))


if __name__ == "__main__":
    unittest.main()
