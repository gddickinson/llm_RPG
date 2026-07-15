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


class TestVaultStructure(unittest.TestCase):
    """P38.2 — the Drowned Vault structure parses into three linked levels."""

    def test_three_levels_with_wards_and_the_lich(self):
        from world.structures import StructureBuilder, STRUCTURES
        from engine.game_engine import GameEngine
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        try:
            spec = STRUCTURES["drowned_vault"]
            self.assertEqual(len(spec["levels"]), 3)
            sb = StructureBuilder(eng)
            levels = [sb._build_level(lv, "drowned_vault")
                      for lv in spec["levels"]]
            # levels 1 & 2 have a sigil ward; level 3 holds the lich
            self.assertTrue(any(f["name"] == "Sigil"
                                for f in levels[0].furniture))
            self.assertTrue(levels[1].dark, "the stacks are dark")
            sanctum = levels[2]
            self.assertIn("vaelzhur_lich",
                          [s.get("template") for s in sanctum.spawns])
        finally:
            eng.end_game()


class _AdvBase(unittest.TestCase):
    def setUp(self):
        self._flag = _os.environ.pop("LLM_RPG_NO_ADVENTURERS", None)
        self.addCleanup(_os.environ.__setitem__,
                        "LLM_RPG_NO_ADVENTURERS", self._flag or "1")
        from engine.game_engine import GameEngine
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.at = self.engine.adventure_tome

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass


class TestSeeder(_AdvBase):
    def test_all_areas_are_planted(self):
        names = {a["name"] for a in self.at.areas}
        for want in ("Mirefen", "Thornwatch Ruins", "The Ashen Camp",
                     "Ysolde's Hollow", "The Drowned Vault"):
            self.assertIn(want, names)

    def test_the_vault_is_an_enterable_dungeon(self):
        self.assertIn("The Drowned Vault", self.engine.interiors)
        inter = self.engine.interiors["The Drowned Vault"]
        self.assertEqual(getattr(inter, "structure_id", None), "drowned_vault")

    def test_the_cast_is_seated(self):
        for nid in ("sage_ondrel", "warden_halric", "witch_ysolde"):
            self.assertIn(nid, self.at.npc_ids)
            npc = self.engine.npc_manager.npcs.get(nid)
            self.assertIsNotNone(npc, f"{nid} not in the world")
            self.assertEqual((npc.metadata or {}).get("adventure"),
                             "sunken_tome")

    def test_the_adventure_npcs_do_not_leak_into_the_general_roster(self):
        from characters.npc_presets import all_presets
        ids = {n.id for n in all_presets()}
        self.assertNotIn("sage_ondrel", ids)
        self.assertNotIn("witch_ysolde", ids)

    def test_state_round_trips(self):
        d = self.at.to_dict()
        from engine.adventure_tome import AdventureTome
        fresh = AdventureTome(self.engine)
        fresh.from_dict(d)
        self.assertEqual([a["id"] for a in fresh.areas],
                         [a["id"] for a in self.at.areas])
        self.assertEqual(fresh.npc_ids, self.at.npc_ids)


class TestQuestChain(_AdvBase):
    """P38.3 — the 5-act quest chain is offered, gated, and completable end to
    end, with the Seal/Destroy/Claim finale firing a [Legend]."""

    def _qm(self):
        return self.engine.quest_manager

    def _status(self, qid):
        q = self._qm().quests[qid]
        q.update_status()
        return q.status.value

    def test_ondrel_offers_the_opener_others_gated(self):
        qm = self._qm()
        self.assertIn("q_tome_whisper",
                      [q.id for q in qm.offered_by("sage_ondrel")])
        self.assertFalse(qm.is_unlocked(qm.quests["q_tome_keys"]))
        self.assertFalse(qm.is_unlocked(qm.quests["q_tome_reckoning"]))

    def test_a_starting_rumor_points_to_mirefen(self):
        log = " ".join(str(x) for x in self.engine.memory_manager.game_history)
        self.assertIn("Mirefen", log)

    def test_the_three_fragments_are_findable(self):
        found = {i.id for items in self.engine.world.ground_items.values()
                 for i in items if "warding_key_" in getattr(i, "id", "")}
        self.assertEqual(found,
                         {"warding_key_i", "warding_key_ii", "warding_key_iii"})

    def test_full_chain_seal_to_destroy_finale(self):
        qm, player = self._qm(), self.engine.player
        # Act 1 — find the Vault
        self.assertTrue(qm.accept_quest("q_tome_whisper"))
        qm.on_location_entered("The Drowned Vault")
        self.assertEqual(self._status("q_tome_whisper"), "completed")
        self.assertTrue(qm.turn_in("q_tome_whisper", player))
        # Act 2 — the keys now unlock
        self.assertTrue(qm.is_unlocked(qm.quests["q_tome_keys"]))
        self.assertTrue(qm.accept_quest("q_tome_keys"))
        for frag in ("warding_key_i", "warding_key_ii", "warding_key_iii"):
            qm.on_item_acquired(frag)
        self.assertEqual(self._status("q_tome_keys"), "completed")
        self.assertTrue(qm.turn_in("q_tome_keys", player))
        self.assertTrue(any(getattr(i, "id", "") == "warding_key"
                            for i in player.inventory), "got the Warding Key")
        # Act 5 — the reckoning; kill the lich (template match on an enc_ id)
        self.assertTrue(qm.is_unlocked(qm.quests["q_tome_reckoning"]))
        self.assertTrue(qm.accept_quest("q_tome_reckoning"))
        qm.on_npc_defeated("enc_vaelzhur_lich_ab12cd", "warlock")
        self.assertEqual(self._status("q_tome_reckoning"), "completed")
        # choose the Destroy ending → a [Legend] finale + the won flag
        choices = qm.quests["q_tome_reckoning"].metadata["reward_choices"]
        self.assertEqual(len(choices), 3, "Seal / Destroy / Claim")
        qm.choose_reward("q_tome_reckoning", 1)
        qm.turn_in("q_tome_reckoning", player)
        log = " ".join(str(x) for x in qm.event_log)
        self.assertTrue(any("[Legend]" in str(m) and "shattered" in str(m)
                            for m in qm.event_log), f"finale legend: {log}")
        self.assertTrue(player.metadata.get("quest_flags", {}).get("tome_won"))


class TestPlaythrough(_AdvBase):
    """P38.4 — a scripted playthrough through the REAL engine: the quest is
    offered in dialog, the Vault is entered, the fragments are picked up, the
    lich is defeated, and BOTH endings complete + fire a [Legend]. (Long travel
    is teleported; every quest step uses the real gameplay hook.)"""

    def _tp(self, pos):
        e = self.engine
        e.world.map.remove_character(e.player)
        e.player.position = tuple(pos)
        e.world.map.place_character(e.player, *pos)

    def _run_to_reckoning(self):
        e, qm, p = self.engine, self.engine.quest_manager, self.engine.player
        at = e.adventure_tome
        # Act 1 — Ondrel offers it in the world; accept + reach the Vault
        self.assertIn("q_tome_whisper",
                      [q.id for q in e.quests_offered_by("sage_ondrel")])
        self.assertTrue(qm.accept_quest("q_tome_whisper"))
        self._tp(at.area_pos("drowned_vault"))
        e.enter_building()                                # real: fires EXPLORE
        self.assertTrue(qm.turn_in("q_tome_whisper", p))
        if e.current_interior:
            e.exit_building()
        # Act 2 — pick up all three fragments through the real pickup path
        self.assertTrue(qm.accept_quest("q_tome_keys"))
        frag_pos = [pos for pos, items in e.world.ground_items.items()
                    for i in items if "warding_key_" in getattr(i, "id", "")]
        for pos in frag_pos:
            self._tp(pos)
            e.pickup_item()
        self.assertTrue(qm.turn_in("q_tome_keys", p))
        self.assertTrue(any(getattr(i, "id", "") == "warding_key"
                            for i in p.inventory))
        # Act 5 — the lich falls (the real combat→quest hook, template match)
        self.assertTrue(qm.accept_quest("q_tome_reckoning"))
        qm.on_npc_defeated("enc_vaelzhur_lich_ab99cd", "warlock")
        qm.quests["q_tome_reckoning"].update_status()
        self.assertEqual(qm.quests["q_tome_reckoning"].status.value,
                         "completed")
        return e, qm, p

    def test_seal_ending(self):
        e, qm, p = self._run_to_reckoning()
        qm.choose_reward("q_tome_reckoning", 0)           # Seal
        qm.turn_in("q_tome_reckoning", p)
        self.assertTrue(any("[Legend]" in str(m) and "sealed" in str(m)
                            for m in qm.event_log))
        self.assertTrue(p.metadata.get("quest_flags", {}).get("tome_won"))

    def test_destroy_ending(self):
        e, qm, p = self._run_to_reckoning()
        qm.choose_reward("q_tome_reckoning", 1)           # Destroy
        qm.turn_in("q_tome_reckoning", p)
        self.assertTrue(any("[Legend]" in str(m) and "shattered" in str(m)
                            for m in qm.event_log))
        self.assertTrue(p.metadata.get("quest_flags", {}).get("tome_won"))


if __name__ == "__main__":
    unittest.main()
