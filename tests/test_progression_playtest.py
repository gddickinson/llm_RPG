"""P37.5c — the gear & party progression playtest (before/after balance check).

George's rebalance goal: the hero should NOT rocket up levels, and power should
come from better GEAR and PARTY members, not from XP farming. This test pins the
three levers with the real combat resolver (`combat_system._resolve` — real
to-hit / weapon-damage / armour-AC math), driving fights between constructed
Fighter characters so no player-death machinery fires and every trial is
deterministic (the combat RNG is seeded per fight).

Contract proven here:
  * Leveling is a SLOW climb (many same-level kills per level).
  * GEAR matters — a geared hero takes far less damage and survives packs that
    kill a bare hero.
  * PARTY matters — a second sword turns a deadly pack into a clean win.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_playtest_"))

import random
import unittest

from engine.game_engine import GameEngine
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item
from characters.equipment import equip
from world.monsters import build_monster

GEAR = ("sword", "chainmail", "iron_shield")   # a common-tier kit
TRIALS = 24


class TestProgressionPlaytest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    # ---- fight harness ---------------------------------------------------

    def _fighter(self, fid, x, y, gear=()):
        h = Character(
            id=fid, name="Hero", character_class=CharacterClass.WARRIOR,
            race=CharacterRace.HUMAN, level=1, strength=14, dexterity=12,
            constitution=13, intelligence=10, wisdom=10, charisma=10,
            hp=24, max_hp=24, position=(x, y))
        for g in gear:
            it = create_item(g)
            h.inventory.append(it)
            equip(h, it)
        self.engine.npc_manager.add_npc(h)
        self.engine.world.map.place_character(h, x, y)
        return h

    def _foe(self, fid, mid, x, y):
        m = build_monster(mid, (x, y))
        m.id = fid
        self.engine.npc_manager.add_npc(m)
        self.engine.world.map.place_character(m, x, y)
        return m

    def _cleanup(self, chars):
        for c in chars:
            try:
                self.engine.world.map.remove_character(c)
            except Exception:
                pass
            self.engine.npc_manager.npcs.pop(c.id, None)

    def _fight(self, gear, foe_ids, n_allies=1, seed=0):
        """One deterministic fight; returns (win, allied HP remaining)."""
        cs = self.engine.combat_system
        cs.rng = random.Random(seed)
        allies = [self._fighter(f"pt_a{i}_{seed}", 10 + i, 10, gear)
                  for i in range(n_allies)]
        foes = [self._foe(f"pt_f{i}_{seed}", fid, 20 + i, 20)
                for i, fid in enumerate(foe_ids)]

        def live(group):
            return [c for c in group if c.hp > 0 and c.is_active()]

        r = 0
        while live(allies) and live(foes) and r < 60:
            r += 1
            for a in live(allies):
                tgt = live(foes)
                if tgt:
                    cs._resolve(a, tgt[0], "attack")
            for f in live(foes):
                tgt = live(allies)
                if tgt:
                    cs._resolve(f, random.Random(seed * 7 + r).choice(tgt),
                                "attack")
        win = bool(live(allies)) and not live(foes)
        hp = sum(max(0, a.hp) for a in allies)
        self._cleanup(allies + foes)
        return win, hp

    def _survey(self, gear, foe_ids, n_allies=1):
        wins = hp = 0
        for s in range(TRIALS):
            w, h = self._fight(gear, foe_ids, n_allies, seed=s)
            wins += 1 if w else 0
            hp += h
        return wins / TRIALS, hp / TRIALS

    # ---- the levers ------------------------------------------------------

    def test_leveling_is_a_slow_climb(self):
        # P37.6 (George: 10x XP/level) — reaching L2 takes many same-level kills.
        from engine.leveling import xp_threshold
        need = xp_threshold(2)                 # XP for level 2 (3000)
        award = 25 + 15 * 1                     # kill award vs a level-1 foe (40)
        kills = -(-need // award)               # ceil → ~75
        self.assertGreaterEqual(
            kills, 40,
            "reaching level 2 should be a long, deliberate climb")

    def test_gear_reduces_damage_taken(self):
        _, bare_hp = self._survey((), ["wolf"])
        _, geared_hp = self._survey(GEAR, ["wolf"])
        # Both win a lone wolf, but the geared hero walks away far healthier.
        self.assertGreater(
            geared_hp, bare_hp + 3.0,
            f"gear should cut damage taken (bare {bare_hp:.1f} vs "
            f"geared {geared_hp:.1f} HP left)")

    def test_a_pack_kills_a_bare_hero(self):
        win, _ = self._survey((), ["wolf", "wolf", "wolf"])
        self.assertLess(
            win, 0.2, "a 3-wolf pack should overwhelm an ungeared hero")

    def test_gear_then_party_carry_the_pack_fight(self):
        bare, _ = self._survey((), ["wolf", "wolf", "wolf"])
        solo, _ = self._survey(GEAR, ["wolf", "wolf", "wolf"])
        party, party_hp = self._survey(GEAR, ["wolf", "wolf", "wolf"],
                                       n_allies=2)
        # Gear lifts a hopeless fight; a second sword turns it into a win.
        self.assertGreater(solo, bare, "gear should help against a pack")
        self.assertGreater(party, solo, "a party should beat a lone hero")
        self.assertGreaterEqual(
            party, 0.8, "a geared two-hero party should clear a wolf pack")


if __name__ == "__main__":
    unittest.main()
