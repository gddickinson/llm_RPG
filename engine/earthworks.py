"""Earthworks (P10.6) — the player reshapes the ground.

The E key's ground fallback lives here: with nothing to pick up,
E first clears rubble (P10.4 — debris is moved, never deleted),
then, pickaxe in hand, DIGS at an adjacent mountain face. Rock is
just another material (see tile_damage): a few swings cut the
mountain down to open ground — a tunnel through the ridge — and
every swing trains Mining.

Also home to the breach mapping shared by entry-sync and the
night masons: one function decides which interior perimeter tile
an exterior footprint tile corresponds to, so holes open AND close
through the same arithmetic.
"""

import logging
from typing import Optional

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.earthworks")

DIG_DAMAGE = 20            # per swing; stone is 80 HP → 4 swings
DIG_XP = 3                 # Mining XP per swing
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def has_pickaxe(player) -> bool:
    return any(getattr(it, "id", "") == "pickaxe"
               for it in player.inventory)


def e_fallback(engine, x: int, y: int) -> Optional[str]:
    """E with nothing underfoot: clear rubble, else dig. Returns a
    message when work was done, else None."""
    if engine.active_zone() is not None:
        return None
    td = engine.tile_damage
    for dx, dy in ((0, 0),) + NEIGHBORS:
        if td.depth_at(x + dx, y + dy) > 0:
            msg = td.clear_rubble(x + dx, y + dy)
            if msg:
                return msg
    if has_pickaxe(engine.player):
        return _dig(engine, x, y)
    return None


def _dig(engine, x: int, y: int) -> Optional[str]:
    wmap = engine.world.map
    for dx, dy in NEIGHBORS:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            continue
        if wmap.terrain[ny][nx] != TerrainType.MOUNTAIN:
            continue
        try:
            from engine.skill_progression import add_skill_xp
            add_skill_xp(engine.player, "mining", DIG_XP)
        except Exception:
            pass
        msg = engine.tile_damage.damage_tile(
            nx, ny, DIG_DAMAGE, "physical")
        if msg is None:
            msg = "Your pick bites into the rock — chips fly."
            engine.memory_manager.add_event(msg)
        return msg
    return None


# ----------------------------------------------------- breach mapping

def footprint_to_perimeter(loc, inter, ex: int, ey: int):
    """Map an exterior footprint tile to the interior perimeter tile
    that shares its wall — the arithmetic behind breach sync."""
    rx = (ex - loc.x) / max(1, loc.width - 1)
    ry = (ey - loc.y) / max(1, loc.height - 1)
    ix = 1 + round(rx * (inter.width - 3))
    iy = 1 + round(ry * (inter.height - 3))
    if min(ix, inter.width - 1 - ix) < \
            min(iy, inter.height - 1 - iy):
        ix = 0 if ix < inter.width // 2 else inter.width - 1
    else:
        iy = 0 if iy < inter.height // 2 else inter.height - 1
    return ix, iy


def sync_breaches(engine, loc, inter) -> None:
    """Every rubbled footprint tile opens the matching interior
    perimeter tile — the hole goes all the way through (P10.4)."""
    wmap = engine.world.map
    for ey in range(loc.y, loc.y + loc.height):
        for ex in range(loc.x, loc.x + loc.width):
            if not (0 <= ex < wmap.width and 0 <= ey < wmap.height):
                continue
            if wmap.terrain[ey][ex] != TerrainType.RUBBLE:
                continue
            ix, iy = footprint_to_perimeter(loc, inter, ex, ey)
            if inter.terrain[iy][ix] == TerrainType.BUILDING:
                inter.terrain[iy][ix] = TerrainType.RUBBLE


def close_breach(loc, inter, ex: int, ey: int) -> None:
    """A rebuilt exterior wall closes its interior hole too."""
    ix, iy = footprint_to_perimeter(loc, inter, ex, ey)
    if inter.terrain[iy][ix] == TerrainType.RUBBLE:
        inter.terrain[iy][ix] = TerrainType.BUILDING
