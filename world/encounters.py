"""Random encounters in the wilderness.

When the player moves into a wilderness tile (FOREST / GRASS away from
the village), there is a small chance to spawn a wandering monster
within FOV. Encounter tables can be expanded later.
"""

import logging
import random
import uuid
from typing import List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.encounters")


# Encounter table: (monster_template_id, weight)
ENCOUNTER_TABLE = [
    ("wolf", 4),
    ("bandit", 2),
    ("goblin", 2),
    ("wandering_troll", 1),
]


# Distance from player at which a new spawn appears
SPAWN_DISTANCE = 4

# Cooldown turns between encounters
ENCOUNTER_COOLDOWN_TURNS = 25

# Per-tick chance to roll an encounter
ENCOUNTER_CHANCE = 0.18


def _weighted_pick(table, rng):
    total = sum(w for _, w in table)
    r = rng.uniform(0, total)
    upto = 0.0
    for k, w in table:
        upto += w
        if r <= upto:
            return k
    return table[-1][0]


def _build_monster(template_id: str, position: Tuple[int, int]):
    """Create a Character instance for the spawned monster."""
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace

    base = {
        "wolf": dict(name="Wolf", klass=CharacterClass.MONSTER,
                     race=CharacterRace.GOBLIN,  # use existing race; flavor only
                     hp=10, max_hp=10, level=1, symbol="w",
                     description="A snarling wolf with hungry eyes."),
        "bandit": dict(name="Bandit", klass=CharacterClass.BRIGAND,
                       race=CharacterRace.HUMAN,
                       hp=14, max_hp=14, level=2, symbol="b",
                       description="A scarred outlaw clutching a rusty blade."),
        "goblin": dict(name="Goblin", klass=CharacterClass.MONSTER,
                       race=CharacterRace.GOBLIN,
                       hp=8, max_hp=8, level=1, symbol="g",
                       description="A green-skinned scavenger."),
        "wandering_troll": dict(name="Wandering Troll",
                                klass=CharacterClass.TROLL,
                                race=CharacterRace.TROLL,
                                hp=30, max_hp=30, level=4, symbol="X",
                                description="A solitary troll, lost from its kin."),
    }
    spec = base.get(template_id, base["wolf"])
    nid = f"enc_{template_id}_{uuid.uuid4().hex[:6]}"
    npc = Character(
        id=nid, name=spec["name"],
        character_class=spec["klass"], race=spec["race"],
        level=spec["level"],
        strength=12, dexterity=12, constitution=11,
        intelligence=6, wisdom=8, charisma=6,
        hp=spec["hp"], max_hp=spec["max_hp"],
        position=position, symbol=spec["symbol"],
        description=spec["description"],
        personality={"traits": ["hostile"]},
        goals=["Attack the player"],
        inventory=[],
    )
    return npc


class EncounterManager:
    """Spawn wilderness encounters around the player."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self._cooldown_until = 0

    def maybe_spawn(self) -> Optional[str]:
        """Possibly spawn a monster nearby. Return event string or None."""
        if self.engine.turn_counter < self._cooldown_until:
            return None
        player = self.engine.player
        if not player:
            return None
        # Only spawn in wilderness terrain
        terrain = self.engine.world.map.get_terrain_at(*player.position)
        if terrain not in (TerrainType.FOREST, TerrainType.GRASS):
            return None
        if self.rng.random() > self.spawn_chance():
            return None

        spawn_pos = self._find_spawn_position()
        if spawn_pos is None:
            return None

        template = _weighted_pick(ENCOUNTER_TABLE, self.rng)
        monster = _build_monster(template, spawn_pos)
        self.engine.npc_manager.add_npc(monster)
        self.engine.world.map.place_character(monster, *spawn_pos)
        self._cooldown_until = self.engine.turn_counter + ENCOUNTER_COOLDOWN_TURNS
        msg = f"A {monster.name} appears in the distance!"
        return msg

    def spawn_chance(self) -> float:
        """Base chance, raised in poor visibility — monsters ambush in
        fog/storm (clear: x1.0, fog: x1.45, storm: x1.5)."""
        try:
            mod = self.engine.weather_system.visibility_modifier()
        except Exception:
            mod = 1.0
        return ENCOUNTER_CHANCE * (2.0 - mod)

    def _find_spawn_position(self) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        candidates = []
        for dy in range(-SPAWN_DISTANCE, SPAWN_DISTANCE + 1):
            for dx in range(-SPAWN_DISTANCE, SPAWN_DISTANCE + 1):
                d = (dx * dx + dy * dy) ** 0.5
                if not (SPAWN_DISTANCE - 1 <= d <= SPAWN_DISTANCE + 0.5):
                    continue
                x, y = px + dx, py + dy
                if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                    continue
                terrain = wmap.terrain[y][x]
                if terrain in (TerrainType.WATER, TerrainType.MOUNTAIN,
                               TerrainType.BUILDING, TerrainType.CAVE):
                    continue
                if (x, y) in wmap.characters:
                    continue
                candidates.append((x, y))
        if not candidates:
            return None
        return self.rng.choice(candidates)
