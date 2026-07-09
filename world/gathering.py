"""Gathering nodes — mining, woodcutting, fishing (P2.2).

Data-driven from `data/gathering.json`. The Z key routes here first:
standing on (or beside, where `adjacent_ok`) matching terrain with the
right tool gathers the best resource tier your skill level unlocks,
weighted toward common tiers. Tiles regenerate on a per-skill cooldown
(the ForageManager pattern). Falls back to herb foraging.
"""

import logging
import random
from typing import Dict, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.gathering")


def _load_nodes() -> Dict[str, dict]:
    from items.data_loader import load_data_file
    return load_data_file("gathering.json")


GATHER_NODES: Dict[str, dict] = _load_nodes()


def has_tool(player, tool: str) -> bool:
    """Tool check across inventory + equipped weapon."""
    from characters.equipment import equipped_items
    candidates = list(player.inventory) + equipped_items(player)
    for it in candidates:
        iid = getattr(it, "id", "")
        if tool == "axe":
            if "axe" in iid and iid != "pickaxe":
                return True
        elif iid == tool:
            return True
    return False


class GatheringManager:
    """Tracks node cooldowns and resolves gather actions."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        # (skill, x, y) -> world.time of harvest
        self.harvested_at: Dict[Tuple[str, int, int], int] = {}

    # ---- resolution ---------------------------------------------------

    def node_at(self, x: int, y: int) -> Optional[Tuple[str, dict, Tuple[int, int]]]:
        """Return (skill_id, spec, node_pos) for the player's position."""
        wmap = self.engine.world.map
        for skill_id, spec in GATHER_NODES.items():
            terrains = {TerrainType(t) for t in spec["terrain"]}
            if wmap.get_terrain_at(x, y) in terrains:
                return (skill_id, spec, (x, y))
            if spec.get("adjacent_ok"):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < wmap.width and 0 <= ny < wmap.height and \
                            wmap.get_terrain_at(nx, ny) in terrains:
                        return (skill_id, spec, (nx, ny))
        return None

    def _cooldown_ok(self, skill_id: str, spec: dict,
                     pos: Tuple[int, int]) -> bool:
        key = (skill_id, pos[0], pos[1])
        last = self.harvested_at.get(key)
        if last is None:
            return True
        return (self.engine.world.time - last) >= spec.get(
            "regen_minutes", 180)

    def _unlocked_tiers(self, skill_id: str, spec: dict):
        from engine.skill_progression import get_skill_level
        level = get_skill_level(self.engine.player, skill_id)
        return [t for t in spec["tiers"] if t["level"] <= level]

    # ---- action --------------------------------------------------------

    def tool_message(self, node) -> str:
        _, spec, _ = node
        return f"You need {spec['tool_name']} to {spec['verb']} here."

    def has_tool_for(self, node) -> bool:
        _, spec, _ = node
        return has_tool(self.engine.player, spec["tool"])

    def gather(self) -> Optional[str]:
        """Gather at the player's tile (assumes tool checked by caller).
        None = no node here."""
        player = self.engine.player
        x, y = player.position
        found = self.node_at(x, y)
        if found is None:
            return None
        skill_id, spec, pos = found

        if not has_tool(player, spec["tool"]):
            return self.tool_message(found)
        if not self._cooldown_ok(skill_id, spec, pos):
            return f"This spot is picked clean. Come back later."

        tiers = self._unlocked_tiers(skill_id, spec)
        if not tiers:
            return f"You lack the skill to {spec['verb']} anything here."

        tier = self._weighted_pick(tiers)
        from items.item_registry import create_item
        item = create_item(tier["item"])
        if item is None:
            logger.warning(f"gathering: unknown item {tier['item']}")
            return "You come up empty-handed."

        player.inventory.append(item)
        self.harvested_at[(skill_id, pos[0], pos[1])] = \
            self.engine.world.time

        from engine.skill_progression import add_skill_xp, skill_name
        notes = add_skill_xp(player, skill_id, tier["xp"])
        msg = (f"You {spec['verb']} and get {item.name}. "
               f"(+{tier['xp']} {skill_name(skill_id)} XP)")
        self.engine.memory_manager.add_event(msg)
        for note in notes:
            self.engine.memory_manager.add_event(note)

        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            self.engine.quest_manager.on_item_acquired(item.id)
        return msg

    def _weighted_pick(self, tiers):
        total = sum(t.get("weight", 1) for t in tiers)
        r = self.rng.uniform(0, total)
        upto = 0.0
        for t in tiers:
            upto += t.get("weight", 1)
            if r <= upto:
                return t
        return tiers[-1]

    # ---- persistence ----------------------------------------------------

    def to_dict(self):
        return {f"{s}|{x}|{y}": t
                for (s, x, y), t in self.harvested_at.items()}

    def from_dict(self, d):
        self.harvested_at = {}
        for key, t in d.items():
            try:
                s, x, y = key.split("|")
                self.harvested_at[(s, int(x), int(y))] = int(t)
            except Exception:
                continue
