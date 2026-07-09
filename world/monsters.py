"""Monster templates — loaded from `data/monsters.json`.

One registry feeds both spawn systems:
- wilderness encounters use `encounter_table()` (id, weight) pairs,
  entries with `encounter_weight > 0`;
- procedural dungeons use `dungeon_pool()`, entries with `"dungeon": true`.

Adding a monster = adding a JSON entry. Optional per-monster `stats`
override the hostile defaults below.
"""

import logging
import uuid
from typing import Dict, List, Tuple

from items.data_loader import load_data_file

logger = logging.getLogger("llm_rpg.monsters")


DEFAULT_STATS = {
    "strength": 12, "dexterity": 12, "constitution": 11,
    "intelligence": 6, "wisdom": 8, "charisma": 6,
}


def _load() -> Dict[str, dict]:
    return load_data_file("monsters.json")


MONSTER_TEMPLATES: Dict[str, dict] = _load()


def encounter_table() -> List[Tuple[str, int]]:
    """(template_id, weight) pairs for wilderness spawns."""
    return [(tid, t.get("encounter_weight", 0))
            for tid, t in MONSTER_TEMPLATES.items()
            if t.get("encounter_weight", 0) > 0]


def dungeon_pool() -> List[str]:
    """Template ids eligible for dungeon rooms."""
    return [tid for tid, t in MONSTER_TEMPLATES.items()
            if t.get("dungeon", False)]


def build_monster(template_id: str, position: Tuple[int, int]):
    """Create a hostile Character from a template."""
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace

    spec = MONSTER_TEMPLATES.get(template_id)
    if spec is None:
        logger.warning(f"Unknown monster template '{template_id}', "
                       f"falling back to wolf")
        spec = MONSTER_TEMPLATES["wolf"]
        template_id = "wolf"

    stats = dict(DEFAULT_STATS)
    stats.update(spec.get("stats", {}))
    hp = spec.get("hp", 10)
    nid = f"enc_{template_id}_{uuid.uuid4().hex[:6]}"
    return Character(
        id=nid,
        name=spec["name"],
        character_class=CharacterClass(spec.get("class", "monster")),
        race=CharacterRace(spec.get("race", "goblin")),
        level=spec.get("level", 1),
        hp=hp, max_hp=spec.get("max_hp", hp),
        position=position,
        symbol=spec.get("symbol", "m"),
        description=spec.get("description", ""),
        personality={"traits": ["hostile"]},
        goals=["Attack the player"],
        inventory=[],
        **stats,
    )
