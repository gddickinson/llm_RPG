"""T4.2 rival companies compete & die: a renown ledger, a wiped company
that DIES, and a strong company that claims a far hoard before the player."""

import unittest

from engine.game_engine import GameEngine
from engine import companies


class _Adv:
    """A tiny stand-in for AdventurerSystem (companies read .engine +
    .controllers + npc_manager)."""
    def __init__(self, engine, ids):
        self.engine = engine
        self.controllers = {i: object() for i in ids}


def _make_adventurer(engine, aid, name, level, home, leader_id=None):
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace
    c = Character(id=aid, name=name, character_class=CharacterClass.WARRIOR,
                  race=CharacterRace.HUMAN, level=level,
                  strength=12, dexterity=12, constitution=12,
                  intelligence=10, wisdom=10, charisma=10,
                  hp=30, max_hp=30)
    c.metadata["home_settlement"] = home
    c.metadata["adventurer"] = True
    if leader_id is not None:
        c.metadata["company"] = leader_id
        if leader_id == aid:
            c.metadata["company_leader"] = True
            c.metadata["company_name"] = "The Iron Band"
    engine.npc_manager.add_npc(c)
    engine.world.map.place_character(c, 3, 3)
    return c


class TestFortune(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def test_ledger_records_a_company(self):
        lead = _make_adventurer(self.engine, "adv_lead", "Bram", 6,
                                "oakvale", leader_id="adv_lead")
        _make_adventurer(self.engine, "adv_2", "Cael", 4, "oakvale",
                         leader_id="adv_lead")
        adv = _Adv(self.engine, ["adv_lead", "adv_2"])
        companies.run_day(adv, day=1)
        led = self.engine.player.metadata.get("company_ledger", {})
        self.assertIn("adv_lead", led)
        self.assertEqual(led["adv_lead"]["fate"], "active")
        self.assertGreater(led["adv_lead"]["peak"], 0)
        lines = companies.ledger_lines(adv)
        self.assertTrue(any("renown" in l for l in lines))

    def test_wiped_company_dies(self):
        lead = _make_adventurer(self.engine, "adv_lead", "Bram", 6,
                                "oakvale", leader_id="adv_lead")
        adv = _Adv(self.engine, ["adv_lead"])
        companies.run_day(adv, day=1)         # register it (active)
        self.assertEqual(
            self.engine.player.metadata["company_ledger"]["adv_lead"]["fate"],
            "active")
        # the whole company is slain
        self.engine.npc_manager.remove_npc("adv_lead")
        companies.run_day(adv, day=2)
        self.assertEqual(
            self.engine.player.metadata["company_ledger"]["adv_lead"]["fate"],
            "fallen")
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("wiped out", log)

    def test_rival_claims_a_far_lair(self):
        lairs = getattr(self.engine, "lairs", None)
        if lairs is None or not getattr(lairs, "lairs", None):
            self.skipTest("no lairs seeded")
        # move the player far from every lair so one qualifies as 'far'
        self.engine.player.position = (0, 0)
        uncleared_before = [l for l in lairs.lairs if not l.get("cleared")]
        if not uncleared_before:
            self.skipTest("no uncleared lair")
        name = lairs.claim_by_rival("The Iron Band")
        self.assertIsNotNone(name)
        # the named lair is now cleared (the farthest one, not a specific one)
        claimed = next(l for l in lairs.lairs if l["name"] == name)
        self.assertTrue(claimed.get("cleared"))
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history)
        self.assertIn("stormed", log)

    def test_realm_digest_includes_companies(self):
        _make_adventurer(self.engine, "adv_lead", "Bram", 6, "oakvale",
                         leader_id="adv_lead")
        adv = _Adv(self.engine, ["adv_lead"])
        companies.run_day(adv, day=1)
        # the realm digest reads engine.adventurers — point it at our stub
        self.engine.adventurers = adv
        from engine import realm_digest
        text = "\n".join(realm_digest.lines(self.engine))
        self.assertIn("Iron Band", text)


if __name__ == "__main__":
    unittest.main()
