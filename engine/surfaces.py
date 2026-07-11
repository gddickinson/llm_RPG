"""Surfaces (P10.3 — fire spread, upgraded to DOS2-style surfaces
per the Phase 12 research synthesis).

A sparse per-tile surface layer over the overworld: FIRE burns
(damaging whoever stands in it, gnawing the tile itself through
P10.2 materials, spreading to adjacent combustibles), OIL waits
(and a whole connected pool ignites the instant flame touches any
part of it), WATER pools douse fire and slowly dry. Burnt-out fires
leave the tile to tile_damage's verdict — groves become SCORCHED
earth, stone endures.

One tick per game turn, touching only active surfaces (sparse).
The DM can pre-paint arenas: pour oil, then let the players decide
who brings the torch. Persists via save_load.
"""

import logging
import random
from typing import Dict, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.surfaces")

FIRE_BASE_DURATION = 6
FIRE_DAMAGE = 4              # per turn standing in flames
FIRE_TILE_DAMAGE = 6         # per turn against the tile itself
SPREAD_CHANCE = 0.30         # per adjacent combustible per tick
COMBUSTIBLE_TERRAIN = (TerrainType.FOREST, TerrainType.FARMLAND)
WATER_DRY_TURNS = 30
OIL_TURNS = 60


class SurfaceLayer:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        # (x, y) -> {"kind", "turns", "intensity"}
        self.surfaces: Dict[Tuple[int, int], dict] = {}

    # ----------------------------------------------------------- paint

    def pour(self, x: int, y: int, kind: str,
             radius: float = 0.0) -> int:
        """Lay a surface (oil/water) on tiles around (x, y)."""
        placed = 0
        r = int(radius)
        for yy in range(y - r, y + r + 1):
            for xx in range(x - r, x + r + 1):
                if ((xx - x) ** 2 + (yy - y) ** 2) ** 0.5 > radius:
                    continue
                if self._paintable(xx, yy):
                    self.surfaces[(xx, yy)] = {
                        "kind": kind,
                        "turns": OIL_TURNS if kind == "oil"
                        else WATER_DRY_TURNS,
                        "intensity": 1}
                    placed += 1
        return placed

    def ignite(self, x: int, y: int, intensity: int = 2,
               duration: int = FIRE_BASE_DURATION) -> int:
        """Set (x, y) alight. A connected oil pool all goes up."""
        lit = 0
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return 0
        here = self.surfaces.get((x, y))
        if here and here["kind"] == "water":
            return 0                       # hiss, nothing more
        if here and here["kind"] == "oil":
            # flood-fill the whole pool
            stack, seen = [(x, y)], set()
            while stack:
                pos = stack.pop()
                if pos in seen:
                    continue
                seen.add(pos)
                s = self.surfaces.get(pos)
                if s is None or s["kind"] != "oil":
                    continue
                self.surfaces[pos] = {"kind": "fire",
                                      "turns": duration + 2,
                                      "intensity": intensity + 1}
                lit += 1
                px, py = pos
                stack += [(px + 1, py), (px - 1, py),
                          (px, py + 1), (px, py - 1)]
            if lit:
                self.engine.memory_manager.add_event(
                    "The oil catches — flame races across the pool!")
            return lit
        if self._paintable(x, y) or here is not None:
            self.surfaces[(x, y)] = {"kind": "fire",
                                     "turns": duration,
                                     "intensity": intensity}
            return 1
        return 0

    def _paintable(self, x: int, y: int) -> bool:
        wmap = self.engine.world.map
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            return False
        return wmap.terrain[y][x] not in (TerrainType.WATER,
                                          TerrainType.MOUNTAIN)

    # ------------------------------------------------------------ tick

    def tick(self) -> None:
        if not self.surfaces:
            return
        wmap = self.engine.world.map
        for pos, s in list(self.surfaces.items()):
            if s["kind"] == "fire":
                self._burn(pos, s)
            s["turns"] -= 1
            if s["turns"] <= 0:
                self.surfaces.pop(pos, None)

    def _burn(self, pos: Tuple[int, int], s: dict) -> None:
        engine = self.engine
        x, y = pos
        # scorch whoever stands in it (overworld space only)
        for victim in self._standing_at(x, y):
            victim.take_damage(FIRE_DAMAGE)
            if victim.id == engine.player.id:
                engine.memory_manager.add_event(
                    f"You are BURNING! (-{FIRE_DAMAGE} HP — move!)")
                if engine.player.hp <= 0:
                    engine.player.hp = 1     # fire maims, story kills
            elif not victim.is_alive():
                victim.defeat()
                engine.world.map.remove_character(victim)
                engine.memory_manager.add_event(
                    f"{victim.name} is consumed by the flames!")
                try:
                    kls = getattr(victim.character_class, "value", "")
                    engine.quest_manager.on_npc_defeated(victim.id,
                                                         kls)
                except Exception:
                    pass
            else:
                engine.memory_manager.add_event(
                    f"{victim.name} burns in the flames!")
        # gnaw the tile itself (P10.2 materials decide)
        try:
            engine.tile_damage.damage_tile(x, y, FIRE_TILE_DAMAGE,
                                           "fire")
        except Exception:
            pass
        # spread
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in self.surfaces and \
                    self.surfaces[(nx, ny)]["kind"] == "oil":
                self.ignite(nx, ny, s["intensity"])
                continue
            if (nx, ny) in self.surfaces:
                continue
            wmap = engine.world.map
            if 0 <= nx < wmap.width and 0 <= ny < wmap.height and \
                    wmap.terrain[ny][nx] in COMBUSTIBLE_TERRAIN and \
                    self.rng.random() < SPREAD_CHANCE:
                self.surfaces[(nx, ny)] = {
                    "kind": "fire",
                    "turns": FIRE_BASE_DURATION,
                    "intensity": max(1, s["intensity"] - 1)}

    def _standing_at(self, x: int, y: int):
        engine = self.engine
        out = []
        try:
            from engine.presence import is_indoors
        except Exception:
            is_indoors = None
        if engine.active_zone() is None and \
                tuple(engine.player.position) == (x, y):
            out.append(engine.player)
        for npc in engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            if npc.metadata.get("zone") is not None:
                continue
            if is_indoors is not None and is_indoors(engine, npc):
                continue
            if tuple(npc.position) == (x, y):
                out.append(npc)
        return out

    def douse(self, x: int, y: int) -> bool:
        s = self.surfaces.get((x, y))
        if s and s["kind"] == "fire":
            self.surfaces[(x, y)] = {"kind": "water",
                                     "turns": WATER_DRY_TURNS,
                                     "intensity": 1}
            return True
        return False

    def kind_at(self, x: int, y: int) -> Optional[str]:
        s = self.surfaces.get((x, y))
        return s["kind"] if s else None

    # ---------------------------------------------------- persistence

    def to_dict(self) -> dict:
        return {"s": [[x, y, s["kind"], s["turns"], s["intensity"]]
                      for (x, y), s in self.surfaces.items()]}

    def from_dict(self, data: dict) -> None:
        self.surfaces = {}
        for x, y, kind, turns, intensity in data.get("s", []):
            self.surfaces[(int(x), int(y))] = {
                "kind": kind, "turns": int(turns),
                "intensity": int(intensity)}
