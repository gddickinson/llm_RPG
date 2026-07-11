"""Skilling pets — rare followers (P2.6) with LOYALTY (P12.14).

Every skilling action (gather, craft, forage) rolls a small chance of a
themed pet: `1 in (BASE - level * LEVEL_BONUS)`, so higher skill = better
odds (level 1: ~1/394, level 50: ~1/100). The newest pet follows a step
behind the player. Owned pets live in `player.metadata["pets"]`.

P12.14 (NetHack tameness): the ACTIVE pet has a loyalty of 1-20.
Tossing it a treat (SHIFT+Z, burns one food item) adds 1; every day
you don't feed it costs 1; at 0 it WALKS AWAY (gone from the
collection — win it back at the skilling grind). At tameness
FETCH_AT (12) or better it learns APPORT: each turn it may dart off
and fetch a ground item from near its heels into your pack.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.pets")

BASE_ODDS = 400
LEVEL_BONUS = 6          # each skill level shaves this off the odds
MIN_ODDS = 60
TAME_START = 10          # NetHack: fresh pets are moderately tame
TAME_MAX = 20
FETCH_AT = 12            # apport unlocks here
FETCH_CHANCE = 0.05
FETCH_RANGE = 3


def _load_pets() -> Dict[str, dict]:
    from items.data_loader import load_data_file
    return load_data_file("pets.json")


PETS: Dict[str, dict] = _load_pets()


class PetSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        # Trail position for the follower (lags one step behind)
        self.follow_pos: Optional[Tuple[int, int]] = None
        self._last_player_pos: Optional[Tuple[int, int]] = None

    # ---- ownership -----------------------------------------------------

    def owned(self) -> List[str]:
        return list(self.engine.player.metadata.get("pets", []))

    def active_pet(self) -> Optional[dict]:
        skill_id = self.engine.player.metadata.get("active_pet")
        if skill_id and skill_id in PETS:
            return {**PETS[skill_id], "skill": skill_id}
        return None

    # ---- the roll --------------------------------------------------------

    def odds_for(self, skill_id: str) -> int:
        from engine.skill_progression import get_skill_level
        level = get_skill_level(self.engine.player, skill_id)
        return max(MIN_ODDS, BASE_ODDS - level * LEVEL_BONUS)

    def maybe_award(self, skill_id: str) -> Optional[str]:
        """Roll for a pet after a skilling action; returns announce msg."""
        if skill_id not in PETS:
            return None
        meta = self.engine.player.metadata
        pets = meta.setdefault("pets", [])
        if skill_id in pets:
            return None
        if self.rng.randint(1, self.odds_for(skill_id)) != 1:
            return None
        pets.append(skill_id)
        meta["active_pet"] = skill_id
        meta.setdefault("pet_tameness", {})[skill_id] = TAME_START
        pet = PETS[skill_id]
        msg = (f"*** {pet['name']} the {pet['kind']} scrambles out to "
               f"join you! ({pet['description']}) ***")
        self.engine.memory_manager.add_event(msg)
        return msg

    # ---- follower movement -------------------------------------------------

    def on_player_moved(self, old_pos: Tuple[int, int]) -> None:
        """Called by PlayerActions.move with the pre-move position."""
        self.follow_pos = old_pos

    def update(self) -> None:
        """Fallback for non-move position changes (teleports, load)."""
        pos = self.engine.player.position
        if self._last_player_pos is not None and \
                pos != self._last_player_pos and \
                self.follow_pos != self._last_player_pos:
            self.follow_pos = self._last_player_pos
        self._last_player_pos = pos

    # ---- loyalty (P12.14) ------------------------------------------

    def tameness(self, skill_id: str = None) -> int:
        meta = self.engine.player.metadata
        skill_id = skill_id or meta.get("active_pet")
        if not skill_id:
            return 0
        return int(meta.get("pet_tameness", {})
                   .get(skill_id, TAME_START))

    def feed_pet(self) -> str:
        """SHIFT+Z: toss the active pet a treat (+1 tameness)."""
        meta = self.engine.player.metadata
        pet = self.active_pet()
        if pet is None:
            return "No pet trots at your heels."
        food = next((it for it in self.engine.player.inventory
                     if (getattr(it, "use_effect", None) or {})
                     .get("food")), None)
        if food is None:
            return f"{pet['name']} sniffs your empty hands. Carry food."
        from engine.item_use import _remove_one
        _remove_one(self.engine.player, food)
        tame = meta.setdefault("pet_tameness", {})
        sid = pet["skill"]
        tame[sid] = min(TAME_MAX, tame.get(sid, TAME_START) + 1)
        meta["pet_fed_day"] = self.engine.world.time // (24 * 60)
        learned = " They watch your hands now — ready to fetch." \
            if tame[sid] == FETCH_AT else ""
        msg = (f"{pet['name']} wolfs down the {food.name} "
               f"(loyalty {tame[sid]}/{TAME_MAX}).{learned}")
        self.engine.memory_manager.add_event(msg)
        return msg

    def run_night(self) -> None:
        """A day without a treat is neglect; at 0 they walk away."""
        meta = self.engine.player.metadata
        sid = meta.get("active_pet")
        if not sid:
            return
        day = self.engine.world.time // (24 * 60)
        if meta.get("pet_fed_day") == day - 1:
            return
        tame = meta.setdefault("pet_tameness", {})
        tame[sid] = tame.get(sid, TAME_START) - 1
        if tame[sid] > 0:
            if tame[sid] <= 3:
                pet = PETS[sid]
                self.engine.memory_manager.add_event(
                    f"{pet['name']} trails further behind, thin "
                    f"and doubtful. (loyalty {tame[sid]})")
            return
        pet = PETS[sid]
        meta["pets"] = [p for p in meta.get("pets", []) if p != sid]
        tame.pop(sid, None)
        meta["active_pet"] = meta["pets"][-1] if meta["pets"] \
            else None
        self.engine.memory_manager.add_event(
            f"[!] {pet['name']} the {pet['kind']} is gone come "
            f"morning — neglect wore the bond through.")

    def maybe_fetch(self) -> Optional[str]:
        """Apport: a loyal pet darts off and brings something back."""
        pet = self.active_pet()
        if pet is None or self.follow_pos is None:
            return None
        try:
            if self.engine.active_zone() is not None:
                return None
        except Exception:
            pass
        if self.tameness() < FETCH_AT:
            return None
        if self.rng.random() >= FETCH_CHANCE:
            return None
        fx, fy = self.follow_pos
        world = self.engine.world
        for r in range(1, FETCH_RANGE + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    items = [it for it in
                             world.get_items_at(fx + dx, fy + dy)
                             if hasattr(it, "id")]
                    if not items:
                        continue
                    from engine.carry import can_carry
                    if not can_carry(self.engine.player):
                        return None
                    item = items[0]
                    world.remove_item_from_ground(
                        item, fx + dx, fy + dy)
                    self.engine.player.inventory.append(item)
                    msg = (f"{pet['name']} darts off and drops "
                           f"{item.name} at your feet!")
                    self.engine.memory_manager.add_event(msg)
                    return msg
        return None

    # ---- persistence ---------------------------------------------------

    # Ownership + tameness live in player.metadata; only the
    # (ephemeral) trail position is held here.
