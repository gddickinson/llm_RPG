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
from typing import Dict, List, Optional, Tuple

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


DEFAULT_SPAWN_TERRAIN = ("grass", "forest")


def encounter_table_for(terrain_value: str) -> List[Tuple[str, int]]:
    """Encounter table filtered to a terrain (regional monsters)."""
    out = []
    for tid, t in MONSTER_TEMPLATES.items():
        if t.get("encounter_weight", 0) <= 0:
            continue
        allowed = t.get("spawn_terrain", DEFAULT_SPAWN_TERRAIN)
        if terrain_value in allowed:
            out.append((tid, t["encounter_weight"]))
    return out


def dungeon_pool() -> List[str]:
    """Template ids eligible for dungeon rooms."""
    return [tid for tid, t in MONSTER_TEMPLATES.items()
            if t.get("dungeon", False)]


def group_spec(template_id: str) -> Optional[dict]:
    """The pack/gang size a wilderness sighting of this template brings
    (P32.2): a `{"min": n, "max": m, "word": "pack"}` block, or None for a
    solitary creature. Wolves run in packs, brigands ride in gangs; a troll
    or a dragon comes alone."""
    spec = MONSTER_TEMPLATES.get(template_id)
    if not spec:
        return None
    g = spec.get("group")
    return g if isinstance(g, dict) else None


def apex_pool(depth: int) -> List[str]:
    """Boss-tier templates a dungeon of this DEPTH may crown its deepest
    floor with (P19.1). A template opts in with a `boss_depth`: the
    warlord, the wisp queen and the tyrant become reachable instead of
    dead test-only content, and a young dragon waits below depth 3, an
    elder wyrm below depth 5."""
    return [tid for tid, t in MONSTER_TEMPLATES.items()
            if t.get("boss_depth") is not None
            and t["boss_depth"] <= depth]


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
    behavior = dict(spec.get("behavior", {}))
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
        metadata={"behavior": behavior,
                  "home_pos": list(position),
                  "speed": spec.get("speed", 1.0),
                  "natural_damage": spec.get("natural_damage", 0)},
        **stats,
    )
