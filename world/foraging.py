"""Foraging — pick herbs/berries from forest tiles.

A grid `forageable_at` maps (x, y) → list of items available. The player
can `forage()` at their current tile to harvest. Each tile regenerates
after a cooldown.
"""

import logging
import random
from typing import Dict, List, Tuple

from items.item import Item
from items.item_registry import create_item
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.foraging")


# Drops by terrain type
TERRAIN_FORAGE_TABLE = {
    TerrainType.FOREST: [("herb_bundle", 3), ("bread", 1)],
    TerrainType.GRASS: [("herb_bundle", 1)],
    TerrainType.SWAMP: [("herb_bundle", 3), ("bogcap", 3)],
}

# Regen cooldown (game minutes)
REGEN_MINUTES = 60 * 24 * 2     # 2 in-game days


def _weighted_pick(table, rng):
    total = sum(w for _, w in table)
    pick = rng.uniform(0, total)
    upto = 0.0
    for k, w in table:
        upto += w
        if pick <= upto:
            return k
    return table[-1][0]


class ForageManager:
    """Tracks which tiles have been harvested and when they regenerate."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.harvested_at: Dict[Tuple[int, int], int] = {}

    def can_forage(self, x: int, y: int) -> bool:
        terrain = self.engine.world.map.get_terrain_at(x, y)
        if terrain not in TERRAIN_FORAGE_TABLE:
            return False
        last = self.harvested_at.get((x, y))
        if last is None:
            return True
        return (self.engine.world.time - last) >= REGEN_MINUTES

    def forage(self, x: int = None, y: int = None) -> str:
        if x is None or y is None:
            x, y = self.engine.player.position
        if not self.can_forage(x, y):
            terrain = self.engine.world.map.get_terrain_at(x, y)
            if terrain not in TERRAIN_FORAGE_TABLE:
                return "Nothing to forage here."
            return "You've recently picked clean this spot."

        from engine.carry import can_carry, full_message
        if not can_carry(self.engine.player):
            return full_message(self.engine.player)

        # Tired eyes find less (PT3.1 balance: hopping fresh tiles
        # yielded ~290 herb bundles in one sweep — an economy breaker).
        # Yield thins with each forage today, floor 20%.
        meta = self.engine.player.metadata
        day = self.engine.world.time // (24 * 60)
        if meta.get("forage_day") != day:
            meta["forage_day"] = day
            meta["forage_count"] = 0
        meta["forage_count"] = meta.get("forage_count", 0) + 1
        fatigue = max(0.2, 1.0 - meta["forage_count"] / 25.0)
        if meta["forage_count"] > 5 and self.rng.random() > fatigue:
            self.harvested_at[(x, y)] = self.engine.world.time
            return ("You search, but your eyes are tired and the "
                    "good herbs elude you. (Rest until tomorrow.)")

        terrain = self.engine.world.map.get_terrain_at(x, y)
        table = TERRAIN_FORAGE_TABLE[terrain]
        item_id = _weighted_pick(table, self.rng)
        item = create_item(item_id)
        if not item:
            return "You find nothing of value."
        self.engine.player.inventory.append(item)
        self.harvested_at[(x, y)] = self.engine.world.time
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            iid = getattr(item, "id", "")
            if iid:
                self.engine.quest_manager.on_item_acquired(iid)
        msg = f"You forage and find {item.name}."
        self.engine.memory_manager.add_event(msg)
        try:
            from engine.skill_progression import add_skill_xp
            for note in add_skill_xp(self.engine.player, "foraging", 15):
                self.engine.memory_manager.add_event(note)
            self.engine.pet_system.maybe_award("foraging")
        except Exception:
            pass
        return msg

    def to_dict(self):
        return {f"{x},{y}": t for (x, y), t in self.harvested_at.items()}

    def from_dict(self, d):
        self.harvested_at = {}
        for key, t in d.items():
            try:
                x, y = map(int, key.split(","))
                self.harvested_at[(x, y)] = int(t)
            except Exception:
                continue
