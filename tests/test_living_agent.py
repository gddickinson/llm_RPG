"""The living agent (2026-07-12) — an away-hero with a life.

Beyond survive/fight/loot/wander, the autoplay brain now chats with folk,
takes and pursues quests, recruits a party, and explores toward places its
calling draws it — biased by a disposition the player sets — and writes its
deeds into the record the player can review."""

import os as _os
import tempfile as _tempfile
_os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                       _tempfile.mkdtemp(prefix="llmrpg_liva_"))

import unittest

from engine.game_engine import GameEngine
from engine.agent_controller import AgentController
from engine import agent_nav as nav
from engine.settings import get_setting, set_setting
from world.monsters import build_monster
from world.world_map import TerrainType
from characters.character_types import CharacterClass
from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus


def _recent(engine):
    return " ".join(e.get("text", "") if isinstance(e, dict) else str(e)
                    for e in engine.memory_manager.get_recent_history())


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.p = self.engine.player
        self.ac = AgentController()
        for yy in range(2, 22):
            for xx in range(2, 22):
                self.engine.world.map.terrain[yy][xx] = TerrainType.GRASS
        self._put(self.p, 10, 10)
        # clear the whole pre-existing cast so only this test's NPCs are in
        # play (the world cast could otherwise sit nearer than a test ally)
        for nid in list(self.engine.npc_manager.npcs):
            n = self.engine.npc_manager.npcs[nid]
            self.engine.world.map.remove_character(n)
            self.engine.npc_manager.remove_npc(nid)

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _put(self, ch, x, y):
        self.engine.world.map.remove_character(ch)
        ch.position = (x, y)
        self.engine.world.map.place_character(ch, x, y)

    def _friend(self, cid, x, y, cls="merchant", rel=0):
        n = build_monster("wolf", (x, y))
        n.id = cid
        n.name = cid.title()
        n.character_class = CharacterClass(cls)
        n.metadata = {}
        n.relationships[self.p.id] = rel
        self.engine.npc_manager.add_npc(n)
        self.engine.world.map.place_character(n, x, y)
        return n


class TestSocial(_Base):
    def test_takes_an_offered_quest_from_a_neighbour(self):
        giver = self._friend("brenna", 11, 10)
        q = Quest(id="brenna_q", title="A Small Favour", description="",
                  objectives=[QuestObjective(ObjectiveType.TALK, "x")],
                  status=QuestStatus.AVAILABLE, giver_id="brenna")
        self.engine.quest_manager.quests["brenna_q"] = q
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "accept_quest")

    def test_recruits_a_willing_ally(self):
        self._friend("ksana", 11, 10, cls="ranger", rel=60)  # warm enough
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "recruit")

    def test_chats_with_a_stranger(self):
        self._friend("odd", 11, 10, rel=0)                   # no quest, cold
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "talk")

    def test_a_chat_is_recorded_as_a_deed(self):
        self._friend("odd", 11, 10, rel=0)
        self.ac.take_turn(self.engine, self.p)
        self.assertIn("[Away]", _recent(self.engine))
        self.assertTrue(self.ac.greeted)


class TestMagic(_Base):
    """A caster away-hero fights with magic (M.8c) — the best affordable,
    reaching damage spell before blade or bow; falls back when out of mana."""

    def _wizard(self, mana=12):
        self.p.character_class = CharacterClass.WIZARD
        self.p.metadata["spells_known"] = ["magic_missile", "fireball",
                                           "firebolt"]
        self.p.metadata["mana"] = mana
        self.p.metadata["max_mana"] = 12

    def _foe(self, x=13, y=10):
        foe = build_monster("wolf", (x, y))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, x, y)
        return foe

    def test_a_caster_flings_a_spell(self):
        self._wizard()
        self._foe()
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "cast")

    def test_it_picks_the_mana_efficient_spell(self):
        self._wizard()
        self._foe()
        # magic_missile (6 dmg / 2 mana) beats fireball (12 / 5) on efficiency
        self.assertEqual(self.ac.decide(self.engine, self.p)[1],
                         "magic_missile")

    def test_out_of_mana_falls_back_to_the_blade(self):
        self._wizard(mana=0)
        self._foe(x=11, y=10)                        # adjacent
        self.assertEqual(self.ac.decide(self.engine, self.p)[0], "attack")

    def test_a_warrior_casts_nothing(self):
        self.p.character_class = CharacterClass.WARRIOR
        self.p.metadata.pop("spells_known", None)
        self._foe(x=11, y=10)
        self.assertNotEqual(self.ac.decide(self.engine, self.p)[0], "cast")


class TestEconomy(_Base):
    """The away-hero SPENDS (M.8b): clears junk for coin and buys the
    potion/ammo it's short of when it deals with a merchant."""

    def _junk(self):
        from items.item import Item, ItemType, ItemRarity
        return Item(id="trinket", name="Bent Trinket", description="",
                    item_type=ItemType.MISC, rarity=ItemRarity.COMMON,
                    value=3)

    def _merchant(self):
        m = self._friend("shopkeep", 11, 10, cls="merchant", rel=0)
        m.gold = 200
        return m

    def test_trades_with_an_adjacent_merchant(self):
        self._merchant()
        self.p.inventory = [self._junk()]
        self.p.gold = 100
        self.assertEqual(self.ac.decide(self.engine, self.p)[0], "trade")

    def test_trade_clears_junk_and_buys_a_potion(self):
        from engine import agent_trade
        from engine.trade_info import junk_items
        from engine.agent_sense import _healing_item
        m = self._merchant()
        self.p.inventory = [self._junk(), self._junk()]
        self.p.gold = 100
        agent_trade.do_trade(self.engine, self.p, m)
        self.assertFalse(junk_items(self.p))            # junk sold off
        self.assertIsNotNone(_healing_item(self.p))     # a potion bought

    def test_no_trade_with_a_plain_warrior(self):
        self._friend("brawn", 11, 10, cls="warrior", rel=0)
        self.p.inventory = [self._junk()]
        self.assertNotEqual(self.ac.decide(self.engine, self.p)[0], "trade")

    def test_shop_buy_and_sell_helpers(self):
        m = self._merchant()
        j = self._junk()
        self.p.inventory = [j]
        self.p.gold = 50
        self.assertTrue(self.engine.shop_manager.sell_for(self.p, j, m))
        self.assertGreater(self.p.gold, 50)            # got paid
        self.assertNotIn(j, self.p.inventory)


class TestRecovery(_Base):
    """A safe, wounded hero recovers (M.8a) instead of soldiering on at a
    sliver of health — a potion, a Heal, or making camp."""

    def test_safe_wounded_hero_drinks_a_potion(self):
        from items.item_registry import create_item
        self.p.hp = int(self.p.max_hp * 0.5)      # below REST, above LOW
        self.p.inventory = [create_item("potion")]
        self.assertEqual(self.ac.decide(self.engine, self.p)[0],
                         "heal_potion")

    def _rations(self, heal=10):
        class _Food:
            use_effect = {"food": True}
            heal_amount = heal
            quantity = 1
        return _Food()

    def test_badly_hurt_provisioned_hero_makes_camp(self):
        self.p.hp = int(self.p.max_hp * 0.3)      # below LOW, out of heals
        self.p.inventory = [self._rations()]      # but has trail rations
        self.p.metadata.pop("spells_known", None)
        self.assertEqual(self.ac.decide(self.engine, self.p)[0], "rest")

    def test_no_camp_without_provisions(self):
        # a fruitless doze would just loop — so with no food, no camp
        self.p.hp = int(self.p.max_hp * 0.3)
        self.p.inventory = []
        self.p.metadata.pop("spells_known", None)
        self.assertNotEqual(self.ac.decide(self.engine, self.p)[0], "rest")

    def test_no_rest_with_a_foe_near(self):
        self.p.hp = int(self.p.max_hp * 0.3)
        self.p.inventory = []
        foe = build_monster("wolf", (13, 10))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, 13, 10)
        self.assertNotEqual(self.ac.decide(self.engine, self.p)[0], "rest")

    def test_an_adventurer_never_sleeps_the_world_away(self):
        self.ac.social = False                     # a driven adventurer NPC
        self.p.hp = int(self.p.max_hp * 0.3)
        self.p.inventory = [self._rations()]       # even provisioned
        self.assertNotEqual(self.ac.decide(self.engine, self.p)[0], "rest")


class TestExplore(_Base):
    def test_a_named_goal_is_class_flavoured(self):
        from engine import agent_goals as agoals
        self.p.character_class = CharacterClass.WIZARD
        goal = agoals.named_goal(self.ac, self.engine, self.p)
        self.assertIsNotNone(goal)
        self.assertIsNotNone(self.ac.goal_name)

    def test_visited_places_are_not_re_sought(self):
        from engine import agent_goals as agoals
        goal1 = agoals.named_goal(self.ac, self.engine, self.p)
        self.ac.visited.add(self.ac.goal_name)
        goal2 = agoals.named_goal(self.ac, self.engine, self.p)
        self.assertNotEqual(goal1, goal2)


class TestDisposition(_Base):
    def test_setting_round_trips(self):
        set_setting(self.p, "disposition", "explorer")
        self.assertEqual(get_setting(self.p, "disposition"), "explorer")

    def test_cautious_keeps_its_distance(self):
        set_setting(self.p, "disposition", "cautious")
        foe = build_monster("wolf", (14, 10))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, 14, 10)
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "flee")

    def test_explorer_wanders_over_a_quest(self):
        # an explorer roams rather than chasing a quest target
        set_setting(self.p, "disposition", "explorer")
        q = Quest(id="far", title="Far Errand", description="",
                  objectives=[QuestObjective(ObjectiveType.TALK,
                                             "guard_01")],
                  status=QuestStatus.ACTIVE)
        self.engine.quest_manager.quests["far"] = q
        # no friend nearby, no loot -> falls to explore, not quest-pursuit
        plan = self.ac.decide(self.engine, self.p)
        self.assertIn(plan[0], ("move", "wait"))


class TestFleeSafety(_Base):
    """The away-hero must never freeze fleeing into a wall (2026-07-12):
    a blocked escape is sidestepped; a true corner is fought."""

    def _wall(self, x, y):
        self.engine.world.map.terrain[y][x] = TerrainType.MOUNTAIN

    def test_flee_sidesteps_a_blocked_escape(self):
        from engine.agent_controller import _dist
        # threat east; the straight-away (west) tiles are walled off
        for yy in (9, 10, 11):
            self._wall(9, yy)
        step = nav.flee_step(self.engine, self.p, (12, 10))
        self.assertIsNotNone(step)               # it does NOT freeze
        nx, ny = self.p.position[0] + step[0], self.p.position[1] + step[1]
        self.assertTrue(nav.walkable(self.engine, self.p, (nx, ny)))
        # and the sidestep never moves toward the threat
        self.assertGreaterEqual(_dist((nx, ny), (12, 10)),
                                _dist(self.p.position, (12, 10)))

    def test_a_cornered_hero_turns_and_fights(self):
        # boxed in on every side, low HP, no heals: rather than 'flee'
        # uselessly into stone forever, the hero attacks the adjacent foe
        self.p.hp = 2
        self.p.inventory = []                    # no healing draught
        foe = build_monster("wolf", (11, 10))
        self.engine.npc_manager.add_npc(foe)
        self.engine.world.map.place_character(foe, 11, 10)
        for (x, y) in [(9, 9), (10, 9), (11, 9), (9, 10),
                       (9, 11), (10, 11), (11, 11)]:
            self._wall(x, y)
        self.assertIsNone(nav.flee_step(self.engine, self.p, (11, 10)))
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "attack")


class TestDeedTrail(_Base):
    def test_the_goal_is_visible_to_the_player(self):
        self.ac.take_turn(self.engine, self.p)
        self.assertIn("agent_goal", self.p.metadata)

    def test_recruiting_is_recorded(self):
        self._friend("ksana", 11, 10, cls="ranger", rel=60)
        self.ac.take_turn(self.engine, self.p)
        if "ksana" in self.engine.companion_manager.party:
            self.assertIn("recruited", _recent(self.engine))


class TestNoLoops(_Base):
    """The away-hero must never lock into a loop (2026-07-12b): looting an
    unpickable corpse, looting with a full pack, shuffling in a doorway, or
    wading into a lair to die over and over."""

    def test_a_body_marker_is_not_loot(self):
        # a plain-string ground entry (a KO'd body) is NOT pickable — the
        # hero must not fixate on it forever
        self.engine.world.add_item_to_ground("Fallen Guard", 10, 10)
        self.assertIsNone(self.ac._nearest_loot(self.engine, self.p, r=0))

    def test_a_full_pack_stops_looting(self):
        from items.item_registry import create_item
        self.engine.world.add_item_to_ground(create_item("arrow"), 10, 10)
        self.assertEqual(self.ac._nearest_loot(self.engine, self.p, r=0),
                         (10, 10))
        from engine.carry import can_carry
        while can_carry(self.p):           # stuff the pack until it's full
            self.p.inventory.append(create_item("arrow"))
        self.assertIsNone(self.ac._nearest_loot(self.engine, self.p, r=0))

    def test_the_agent_skirts_buildings(self):
        self.engine.world.map.terrain[10][11] = TerrainType.BUILDING
        self.assertFalse(nav.walkable(self.engine, self.p, (11, 10)))

    def test_a_closing_pack_is_a_retreat(self):
        # three foes within four tiles = a lair; withdraw, don't wade in
        for i, pos in enumerate([(13, 10), (12, 12), (13, 12)]):
            f = build_monster("goblin", pos)
            f.id = f"pack_{i}"
            self.engine.npc_manager.add_npc(f)
            self.engine.world.map.place_character(f, *pos)
        plan = self.ac.decide(self.engine, self.p)
        self.assertEqual(plan[0], "flee")


class TestColocation(unittest.TestCase):
    """A hero only perceives what shares its grid (2026-07-12b) — the
    fix for shooting a phantom overworld foe through a tavern wall."""

    def _npc(self, zone):
        n = build_monster("wolf", (0, 0))
        n.metadata = {"zone": zone} if zone else {}
        return n

    def test_overworld_ignores_the_underground(self):
        from engine.agent_controller import _colocated
        self.assertTrue(_colocated(None, self._npc(None)))
        self.assertFalse(_colocated(None, self._npc("Deep Crypt")))

    def test_a_zone_sees_only_its_own_natives(self):
        from engine.agent_controller import _colocated
        self.assertTrue(_colocated("Deep Crypt", self._npc("Deep Crypt")))
        self.assertFalse(_colocated("Deep Crypt", self._npc(None)))
        self.assertFalse(_colocated("Deep Crypt", self._npc("Tavern")))


class TestInteriorNoFreeze(unittest.TestCase):
    """Entering a building must not freeze the away-hero (2026-07-12b):
    inside, it heads for the door and steps back out to its life."""

    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.engine.world.time = 12 * 60
        self.p = self.engine.player
        self.ac = AgentController()

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _enter_a_building(self):
        loc = next((l for l in self.engine.world.locations
                    if l.name in self.engine.interiors), None)
        self.assertIsNotNone(loc, "demo world needs an enterable building")
        wmap = self.engine.world.map
        wmap.remove_character(self.p)
        self.p.position = (loc.x + loc.width // 2, loc.y + loc.height - 1)
        wmap.place_character(self.p, *self.p.position)
        self.engine.enter_building(loc, via_breach=True)
        return loc

    def test_away_hero_does_not_freeze_indoors(self):
        self._enter_a_building()
        self.assertIsNotNone(self.engine.active_zone(),
                             "should be inside the building")
        self.engine.roster.set_away(self.p, True)
        seen = set()
        exited = False
        for _ in range(25):
            self.ac.take_turn(self.engine, self.p)
            seen.add(tuple(self.p.position))
            if self.engine.active_zone() is None:
                exited = True
                break
        # walked its rooms or stepped back outside — never frozen in place
        self.assertTrue(exited or len(seen) > 1, "away-hero froze indoors")


if __name__ == "__main__":
    unittest.main()
