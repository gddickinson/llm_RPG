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

# P27.1 danger tiers — a settlement's guarded environs have NO wandering
# spawns; its fringe is quieter; the deep wilderness ramps up with distance;
# roads are travelled and safer. Early play (which hugs the start town) gets
# breathing room, and straying far has stakes.
SAFE_RADIUS = 7          # no wilderness spawns this near a settlement
FRINGE_RADIUS = 14       # a settlement's fringe: encounters are rarer
FRINGE_MULT = 0.4
ROAD_MULT = 0.45         # roads/bridges are travelled — safer
FAR_STEP = 22            # every N tiles past the fringe ramps danger up
FAR_BONUS = 0.2
FAR_CAP = 1.75
_SETTLEMENT_KEYS = ("village", "hamlet", "town")


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
        # P27.1: a settlement's guarded environs are SAFE — no monsters
        # wander in or right around a town (the walled starting town too)
        d = self._nearest_settlement_dist(player.position)
        if d is not None and d <= SAFE_RADIUS:
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
        # The endgame curve (P19.5): a party that out-levels the wild draws
        # an ELITE, and sometimes a whole warband under it.
        from engine import elites
        base_level = monster.level
        promoted = elites.maybe_promote(self.engine, monster, self.rng)
        extra = elites.extra_pack(self.engine, base_level, self.rng)
        # P32.2: a wolf sighting is a PACK, a bandit a GANG — the template's
        # `group` block brings companions from turn one, on top of any elite
        # warband, all under one tag so the P19.3 pack brain coordinates them.
        group, word = self._group_extra(template)
        companions = group + extra
        self.engine.npc_manager.add_npc(monster)
        self.engine.world.map.place_character(monster, *spawn_pos)
        placed_extra = 0
        if companions:
            tag = f"pack:{monster.id}"           # the P19.3 pack brain bands them
            monster.metadata["lair"] = tag
            for epos in self._nearby_spawns(spawn_pos, companions):
                em = _build_monster(template, epos)
                em.metadata["lair"] = tag
                self.engine.npc_manager.add_npc(em)
                self.engine.world.map.place_character(em, *epos)
                placed_extra += 1
        self._cooldown_until = self.engine.turn_counter + ENCOUNTER_COOLDOWN_TURNS
        if placed_extra:
            return (f"A {word} of {monster.name}s "
                    f"appears in the distance!")
        if promoted:
            return f"A fearsome {monster.name} appears in the distance!"
        return f"A {monster.name} appears in the distance!"

    def _group_extra(self, template: str) -> Tuple[int, str]:
        """How many EXTRA companions this template's `group` brings (size − 1)
        and the collective NOUN for the sighting message (P32.2). Solitary
        templates return (0, 'pack')."""
        from world.monsters import group_spec
        g = group_spec(template)
        if not g:
            return 0, "pack"
        lo = int(g.get("min", 1))
        hi = max(lo, int(g.get("max", lo)))
        size = self.rng.randint(lo, hi)
        return max(0, size - 1), g.get("word", "pack")

    def _nearby_spawns(self, pos, n) -> List[Tuple[int, int]]:
        """Up to n free walkable tiles adjacent-ish to a spawn point."""
        wmap = self.engine.world.map
        px, py = pos
        out = []
        for r in (1, 2, 3):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = px + dx, py + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in (TerrainType.WATER,
                                              TerrainType.MOUNTAIN,
                                              TerrainType.BUILDING,
                                              TerrainType.CAVE):
                        continue
                    if (x, y) in wmap.characters:
                        continue
                    out.append((x, y))
                    if len(out) >= n:
                        return out
        return out

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
        return ENCOUNTER_CHANCE * (2.0 - mod) * mult * self.danger_multiplier()

    def _nearest_settlement_dist(self, pos) -> Optional[float]:
        """Distance to the nearest SETTLEMENT (village/hamlet/town), or None
        if the world has none placed."""
        px, py = pos
        best = None
        for loc in getattr(self.engine.world, "locations", []):
            name = getattr(loc, "name", "").lower()
            if not any(k in name for k in _SETTLEMENT_KEYS):
                continue
            try:
                cx, cy = loc.center()
            except Exception:
                cx, cy = getattr(loc, "x", px), getattr(loc, "y", py)
            dd = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if best is None or dd < best:
                best = dd
        return best

    def danger_multiplier(self) -> float:
        """P27.1 tier factor on the spawn chance: quieter near a settlement,
        ramping up the deeper into the wild, softened on a road. Always > 0 —
        the hard no-spawn town zone lives in `maybe_spawn`."""
        px, py = self.engine.player.position
        d = self._nearest_settlement_dist((px, py))
        if d is None:
            mult = 1.0
        elif d <= FRINGE_RADIUS:
            mult = FRINGE_MULT
        else:
            steps = (d - FRINGE_RADIUS) / FAR_STEP
            mult = min(FAR_CAP, 1.0 + FAR_BONUS * steps)
        try:
            if self.engine.world.map.get_terrain_at(px, py) in (
                    TerrainType.ROAD, TerrainType.BRIDGE):
                mult *= ROAD_MULT
        except Exception:
            pass
        return mult

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
