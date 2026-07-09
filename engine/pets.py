"""Skilling pets — rare cosmetic followers (P2.6, the OSRS pattern).

Every skilling action (gather, craft, forage) rolls a small chance of a
themed pet: `1 in (BASE - level * LEVEL_BONUS)`, so higher skill = better
odds (level 1: ~1/394, level 50: ~1/100). Pets are pure cosmetics: the
newest one follows a step behind the player. Owned pets live in
`player.metadata["pets"]`; the follower is drawn by the renderer.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.pets")

BASE_ODDS = 400
LEVEL_BONUS = 6          # each skill level shaves this off the odds
MIN_ODDS = 60


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

    # ---- persistence ---------------------------------------------------

    # Ownership lives in player.metadata; only the (ephemeral) trail
    # position is held here, so no to_dict/from_dict is needed.
