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


# Encounter table: (monster_template_id, weight) — from data/monsters.json
from world.monsters import encounter_table, build_monster

ENCOUNTER_TABLE = encounter_table()


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


_build_monster = build_monster  # local alias used by maybe_spawn


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
        # No ambushes inside dungeons/interiors/the tutorial isle
        try:
            if self.engine.active_zone() is not None:
                return None
        except Exception:
            pass
        # Only spawn in wilderness terrain
        terrain = self.engine.world.map.get_terrain_at(*player.position)
        if terrain not in (TerrainType.FOREST, TerrainType.GRASS,
                           TerrainType.SWAMP):
            return None
        if self.rng.random() > self.spawn_chance():
            return None

        spawn_pos = self._find_spawn_position()
        if spawn_pos is None:
            return None

        from world.monsters import encounter_table_for
        table = encounter_table_for(terrain.value) or ENCOUNTER_TABLE
        try:
            mult = self.engine.faction_ticker.bandit_weight_multiplier()
            if mult != 1.0:
                table = [(tid, max(1, int(w * mult))
                          if tid == "bandit" else w)
                         for tid, w in table]
        except Exception:
            pass
        template = _weighted_pick(table, self.rng)
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
        mult = 1.0
        try:
            from world.astronomy import is_conjunction
            if is_conjunction(self.engine.world.time // (24 * 60)):
                mult = 1.5           # omen nights are dangerous
        except Exception:
            pass
        return ENCOUNTER_CHANCE * (2.0 - mod) * mult

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
