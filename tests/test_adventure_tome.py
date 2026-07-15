"""P38 — "The Sunken Tome of Vael'Zhur" adventure content.

P38.1 content-integrity: the adventure's monsters (incl. the lich boss), the
Reedmarsh tribe, and the artifacts all exist, build, and cross-reference cleanly.
Later phases add the areas, quest chain, and a scripted playthrough.
"""

import json
import os as _os
import tempfile as _tempfile
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_tome_"))

import unittest


def _load(path):
    with open(path) as fp:
        return json.load(fp)


from world.monsters import build_monster
from engine.bosses import boss_spec
from items.item_registry import create_item


ADVENTURE_MONSTERS = {
    "grave_touched": 3, "drowned_guardian": 4, "cinder_cultist": 3,
    "cinder_captain": 5, "bog_goblin": 2, "bog_goblin_champion": 4,
    "vaelzhur_lich": 9,
}
ARTIFACTS = [
    "sunken_tome", "warding_key_i", "warding_key_ii", "warding_key_iii",
    "warding_key", "drowned_lantern", "tidecaller_signet",
    "guardian_halberd", "scroll_frost_ray", "scroll_frost_armor",
]


class TestMonsters(unittest.TestCase):
    def test_all_build_at_the_designed_level(self):
        for mid, lvl in ADVENTURE_MONSTERS.items():
            m = build_monster(mid, (4, 4))
            self.assertIsNotNone(m, f"{mid} failed to build")
            self.assertEqual(m.level, lvl, f"{mid} level")
            self.assertGreater(m.max_hp, 0)

    def test_the_adventure_foes_do_not_wild_spawn(self):
        # encounter_weight 0 → they appear only via the adventure, like bosses
        data = _load("data/monsters.json")
        for mid in ADVENTURE_MONSTERS:
            self.assertEqual(data[mid].get("encounter_weight", 0), 0, mid)

    def test_the_lich_is_a_phased_boss(self):
        lich = build_monster("vaelzhur_lich", (4, 4))
        spec = boss_spec(lich)
        self.assertTrue(spec, "the lich carries a boss block")
        actions = [p["action"] for p in spec.get("phases", [])]
        for want in ("summon", "terror", "enrage"):
            self.assertIn(want, actions, f"lich should have a {want} phase")
        self.assertEqual(spec.get("telegraph", {}).get("kind"), "necrotic")

    def test_undead_take_extra_holy_damage(self):
        # holy sears the wicked (class monster) — a wired combat consequence
        from engine.combat_math import damage_type_modifier

        class _W:
            id = "mace_holy"
            name = "Holy Mace"
            damage_kind = "holy"
        guardian = build_monster("drowned_guardian", (4, 4))

        class _A:
            equipped_weapon = _W()
        bonus = damage_type_modifier(_A(), guardian, 10)
        self.assertGreater(bonus, 0, "holy should bite the undead guardian")


class TestTribe(unittest.TestCase):
    def test_reedmarsh_warren_registered_with_real_units(self):
        tribes = _load("data/tribes.json")
        self.assertIn("reedmarsh_warren", tribes)
        warren = tribes["reedmarsh_warren"]
        monsters = _load("data/monsters.json")
        self.assertIn(warren["raider"], monsters)
        self.assertIn(warren["champion"], monsters)
        self.assertEqual(warren["terrain"], "swamp")


class TestArtifacts(unittest.TestCase):
    def test_all_create(self):
        for iid in ARTIFACTS:
            self.assertIsNotNone(create_item(iid), f"{iid} missing")

    def test_the_tome_teaches_dark_magic(self):
        tome = create_item("sunken_tome")
        self.assertEqual(tome.rarity.value if hasattr(tome.rarity, "value")
                         else tome.rarity, "legendary")
        self.assertEqual((tome.use_effect or {}).get("teach_spell"), "drain")
        self.assertTrue((tome.metadata or {}).get("tome_of_vaelzhur"))

    def test_three_distinct_warding_fragments(self):
        frags = [create_item(f"warding_key_{n}") for n in ("i", "ii", "iii")]
        nums = sorted((f.metadata or {}).get("warding_fragment") for f in frags)
        self.assertEqual(nums, [1, 2, 3])

    def test_signet_aids_swimming(self):
        sig = create_item("tidecaller_signet")
        self.assertGreater((sig.equip_bonuses or {}).get("swim", 0), 0)


if __name__ == "__main__":
    unittest.main()
