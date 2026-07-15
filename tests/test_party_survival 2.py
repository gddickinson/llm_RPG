"""M.10b — companion combat survival.

Companions take combat injuries (an enemy's blow drops their HP); a hurt
companion quaffs its OWN healing potion rather than fight on at a sliver,
and one still critical BREAKS OFF even without the /order flee — survival
before orders, so a party member doesn't fight to the death.
"""

import unittest

from engine.game_engine import GameEngine
from items.item_registry import create_item
from world.monsters import build_monster
from world.world_map import TerrainType


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(llm_provider="heuristic",
                                 enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        self.wmap = self.engine.world.map
        self.mel = self.engine.npc_manager.get_npc("minstrel_01")
        self.engine.companion_manager.party.append("minstrel_01")
        # a clear grassy arena around the player
        px, py = self.player.position
        for yy in range(py - 3, py + 4):
            for xx in range(px - 3, px + 4):
                if 0 <= xx < self.wmap.width and 0 <= yy < self.wmap.height:
                    self.wmap.terrain[yy][xx] = TerrainType.GRASS

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _place(self, ch, x, y):
        self.wmap.remove_character(ch)
        ch.position = (x, y)
        self.wmap.place_character(ch, x, y)

    def _foe_next_to(self, ch):
        foe = build_monster("goblin", (ch.position[0] + 1, ch.position[1]))
        self.engine.npc_manager.add_npc(foe)
        self.wmap.remove_character(foe)
        foe.position = (ch.position[0] + 1, ch.position[1])
        self.wmap.place_character(foe, *foe.position)
        return foe


class TestInjuries(_Base):
    def test_a_companion_takes_combat_damage(self):
        # the user's suspicion: do party members suffer injuries? They do.
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        foe = self._foe_next_to(self.mel)
        before = self.mel.hp
        # attacks roll to-hit and can MISS — swing until one lands (a hit is
        # near-certain within a few tries); the point is a companion CAN be hurt
        for _ in range(30):
            self.engine.combat_system.npc_attack(foe, self.mel.name, "attack")
            if self.mel.hp < before:
                break
        self.assertLess(self.mel.hp, before, "a companion should be woundable")


class TestSelfHeal(_Base):
    def test_a_hurt_companion_quaffs_its_potion(self):
        self.mel.inventory.append(create_item("potion"))
        self.mel.hp = int(self.mel.max_hp * 0.3)
        before = self.mel.hp
        self.engine.companion_manager.update()
        self.assertGreater(self.mel.hp, before)

    def test_the_potion_is_consumed(self):
        pot = create_item("potion")
        self.mel.inventory.append(pot)
        self.mel.hp = int(self.mel.max_hp * 0.3)
        self.engine.companion_manager.update()
        self.assertNotIn(pot, self.mel.inventory)

    def test_a_healthy_companion_keeps_its_potion(self):
        pot = create_item("potion")
        self.mel.inventory.append(pot)
        self.mel.hp = self.mel.max_hp
        self.engine.companion_manager.update()
        self.assertIn(pot, self.mel.inventory)

    def test_no_potion_no_heal(self):
        self.mel.inventory = []
        self.mel.hp = int(self.mel.max_hp * 0.3)
        before = self.mel.hp
        self.engine.companion_manager.update()
        # nothing to drink — HP unchanged by self-heal (may still fight/flee)
        self.assertEqual(self.mel.hp, before)


class TestCriticalFlee(_Base):
    def test_a_critical_companion_flees_even_on_follow(self):
        # no potion, critically hurt, a foe adjacent, ordered to FOLLOW
        self.mel.inventory = []
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        self.mel.hp = max(1, int(self.mel.max_hp * 0.2))
        self.mel.metadata["order"] = "follow"
        foe = self._foe_next_to(self.mel)
        pos0 = self.mel.position
        self.engine.companion_manager.update()
        # it broke off (moved) away from the foe rather than trading blows
        moved = self.mel.position != pos0
        self.assertTrue(moved, "a critical companion should break off")
        fx, fy = foe.position
        self.assertGreater(
            max(abs(self.mel.position[0] - fx),
                abs(self.mel.position[1] - fy)), 1,
            "it should have opened distance from the foe")

    def test_a_hale_companion_does_not_flee(self):
        self.mel.inventory = []
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        self.mel.hp = self.mel.max_hp          # hale — stands and fights
        self.mel.metadata["order"] = "follow"
        foe = self._foe_next_to(self.mel)
        pos0 = self.mel.position
        self.engine.companion_manager.update()
        fx, fy = foe.position
        # a hale companion stays in the fight (adjacent), not fleeing
        self.assertLessEqual(
            max(abs(self.mel.position[0] - fx),
                abs(self.mel.position[1] - fy)), 1)


class TestDesertion(_Base):
    """At death's door, a disloyal member bolts; a loyal one stands fast."""

    def _corner(self):
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        self.mel.inventory = []
        self.mel.hp = max(1, int(self.mel.max_hp * 0.12))   # critical
        return self._foe_next_to(self.mel)

    def test_a_disloyal_member_abandons_the_party(self):
        self._corner()
        self.mel.relationships[self.player.id] = -30        # estranged
        self.engine.companion_manager.update()
        self.assertNotIn("minstrel_01", self.engine.companion_manager.party)
        self.assertTrue(self.mel.metadata.get("deserted"))

    def test_a_loyal_member_stays_at_your_side(self):
        self._corner()
        self.mel.relationships[self.player.id] = 40         # fond & loyal
        self.engine.companion_manager.update()
        self.assertIn("minstrel_01", self.engine.companion_manager.party)

    def test_not_critical_enough_holds(self):
        foe = self._foe_next_to(self.mel)   # noqa: F841
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        self.mel.inventory = []
        self.mel.hp = int(self.mel.max_hp * 0.30)           # hurt, not dying
        self.mel.relationships[self.player.id] = -30
        self.engine.companion_manager.update()
        self.assertIn("minstrel_01", self.engine.companion_manager.party)

    def test_a_potion_keeps_it_in_the_fight(self):
        self._corner()
        self.mel.relationships[self.player.id] = -30
        self.mel.inventory.append(create_item("potion"))    # can self-save
        self.engine.companion_manager.update()
        self.assertIn("minstrel_01", self.engine.companion_manager.party)

    def test_no_danger_no_desertion(self):
        # critical & estranged but NO foe adjacent — it doesn't abandon ship
        self._place(self.mel, self.player.position[0],
                    self.player.position[1] + 1)
        self.mel.inventory = []
        self.mel.hp = max(1, int(self.mel.max_hp * 0.12))
        self.mel.relationships[self.player.id] = -30
        self.engine.companion_manager.update()
        self.assertIn("minstrel_01", self.engine.companion_manager.party)


if __name__ == "__main__":
    unittest.main()
