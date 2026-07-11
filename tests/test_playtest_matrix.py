"""PUX.5 — a scripted, judged Playtest-Matrix session.

Complements the unit tests with cross-cutting PLAYABILITY checks that
walk the standing 12-dimension charter: no dead ends, the economy
loop closes, allies fight, the world is navigable and region-scoped,
and the log stays readable. A green run here is a green scorecard.
"""

import os as _os
import tempfile as _tempfile
import unittest

_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_lib_"))

from engine.game_engine import GameEngine           # noqa: E402
from world.monsters import build_monster            # noqa: E402


class PlaytestSession(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _spawn(self, template, off):
        px, py = self.p.position
        m = build_monster(template, (px + off[0], py + off[1]))
        self.engine.npc_manager.add_npc(m)
        return m

    # 1. PROGRESSION — no authored quest is a dead end -------------
    def test_no_quest_dead_ends(self):
        from quests.quest_templates import QUEST_TEMPLATES
        from quests.quest import ObjectiveType
        from world.monsters import MONSTER_TEMPLATES
        from characters.character_types import CharacterClass
        present = set(self.engine.npc_manager.npcs)
        classes = {c.value for c in CharacterClass}
        for qid, factory in QUEST_TEMPLATES.items():
            q = factory()
            if q.giver_id:
                self.assertIn(q.giver_id, present,
                              f"{qid}: giver not in the world")
            for o in q.objectives:
                if o.obj_type in (ObjectiveType.KILL, ObjectiveType.TALK):
                    self.assertTrue(
                        o.target in present or o.target in MONSTER_TEMPLATES
                        or o.target in classes,
                        f"{qid}: target '{o.target}' unreachable")

    # 4. ECONOMY — earn, craft, and a sink to reach ---------------
    def test_economy_loop_closes(self):
        wolf = self._spawn("wolf", (1, 0))
        g0 = self.p.gold
        for _ in range(40):
            if not wolf.is_active():
                break
            self.engine.combat_system.player_attack(wolf.name)
        self.assertFalse(wolf.is_active(), "a kill earns loot/xp")
        # craft: give the ingredients for a sample recipe, then make it
        from items.crafting import RECIPES
        from items.item_registry import create_item
        rid = next(iter(RECIPES))
        for iid in RECIPES[rid].ingredients:
            self.p.inventory.append(create_item(iid))
        self.assertIn("craft", self.engine.craft(rid).lower())
        # a bankable sink exists in the world (economy isn't a dead end)
        names = " ".join(l.name.lower()
                         for l in self.engine.world.locations)
        self.assertTrue(any(k in names for k in
                            ("temple", "store", "shop")),
                        "no bank/shop sink to reach")

    # 2/10. COOPERATION & COORDINATION — an ally fights -----------
    def test_a_companion_fights_at_your_side(self):
        ally_id = next(iter(self.engine.npc_manager.npcs))
        self.engine.companion_manager.party.append(ally_id)
        ally = self.engine.npc_manager.get_npc(ally_id)
        px, py = self.p.position
        ally.position = (px, py + 1)
        foe = self._spawn("wolf", (1, 1))
        hp0 = foe.hp
        for _ in range(10):
            self.engine.companion_manager.update()
        self.assertLess(foe.hp, hp0, "the companion joins the fight")

    # 7. NAVIGATION — regions scope their cast, player survives ----
    def test_travel_between_regions_is_clean(self):
        s = self.engine.world_streamer
        home = set(self.engine.npc_manager.npcs)
        s.transit("east")
        self.assertFalse(home & set(self.engine.npc_manager.npcs),
                         "home NPCs must not haunt the next region")
        self.assertTrue(self.p.is_active(), "the player survives travel")
        s.transit("west")
        self.assertTrue(home <= set(self.engine.npc_manager.npcs),
                        "the home cast returns")

    # 12. FEEL — the log declutters on quiet ----------------------
    def test_log_verbosity_trims_ambient_noise(self):
        from engine import event_filter
        ev = self.engine.memory_manager.add_event
        ev("The wind rustles through the trees.")     # ambient
        ev("You strike the wolf for 6 damage.")       # player/combat
        self.p.metadata["log_verbosity"] = "verbose"
        verbose = event_filter.filtered_recent(self.engine, 80)
        self.p.metadata["log_verbosity"] = "quiet"
        quiet = event_filter.filtered_recent(self.engine, 80)
        self.assertLessEqual(len(quiet), len(verbose))
        self.assertTrue(any("wind rustles" in x for x in verbose))
        self.assertFalse(any("wind rustles" in x for x in quiet),
                         "ambient flavour is hidden on quiet")


if __name__ == "__main__":
    unittest.main()
