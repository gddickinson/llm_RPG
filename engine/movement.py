"""Wall-aware movement guard (bug-fix, 2026-07-12).

`WorldMap.move_character` is the single chokepoint through which every
NPC and monster steps. Historically it blocked only WATER and MOUNTAIN,
so creatures walked straight through BUILDING footprints — and while the
player stood inside a zone, zone-native monsters were being stepped on
the OVERWORLD grid at their zone-local coordinates, ignoring the zone's
own walls entirely. Two ways to phase through a wall.

This guard is installed on the active map (`map.wall_guard`) and
consulted by `move_character`. It rejects any move that would cross a
solid wall on the grid the mover ACTUALLY occupies:

  * a **zone-native** creature (a dungeon monster, an interior visitor,
    the tutorial cast) is validated against the ACTIVE ZONE's terrain —
    a BUILDING tile is a wall and blocks everyone, fliers included;
  * **everyone else** is on the overworld, where a BUILDING footprint is
    a solid building whose only gap is its south door tile, so nothing
    enters or leaves a building through a wall. A door tile (or a
    breached wall, which is RUBBLE, not BUILDING) still admits passage.

The player is unaffected: it never reaches `move_character` on a building
tile (its own door logic runs first) and moves inside zones through
`_move_in_zone`.
"""

from world.world_map import TerrainType, _is_flier


def _zone_native(engine, character):
    """The active zone IFF this character lives on that zone's grid."""
    try:
        zone = engine.active_zone()
    except Exception:
        zone = None
    if zone is None:
        return None
    cid = getattr(character, "id", "") or ""
    meta = getattr(character, "metadata", {}) or {}
    if meta.get("zone") == getattr(zone, "name", None):
        return zone
    if cid.startswith(("enc_", "tut_")):
        return zone
    if cid in getattr(zone, "visitors", {}):
        return zone
    return None


def _door_tile(engine, x, y):
    """The south-door tile of the enterable building covering (x, y)."""
    loc = engine.world.get_location_at(x, y)
    if loc is None or loc.name not in getattr(engine, "interiors", {}):
        return None
    return (loc.x + loc.width // 2, loc.y + loc.height - 1)


def _is_door(engine, x, y):
    return _door_tile(engine, x, y) == (x, y)


def crosses_building_wall(engine, character, old, new) -> bool:
    """Overworld: True if old->new crosses a building footprint boundary
    anywhere but a door — i.e. a wall the mover would phase through."""
    wmap = engine.world.map
    ox, oy = int(old[0]), int(old[1])
    nx, ny = int(new[0]), int(new[1])

    def _bldg(x, y):
        return (0 <= x < wmap.width and 0 <= y < wmap.height
                and wmap.terrain[y][x] == TerrainType.BUILDING)

    if _bldg(nx, ny) == _bldg(ox, oy):
        return False                       # not crossing a wall boundary
    return not (_is_door(engine, ox, oy) or _is_door(engine, nx, ny))


def move_blocked(engine, character, old, new) -> bool:
    """The map's `wall_guard`: return True to reject the move."""
    zone = _zone_native(engine, character)
    if zone is not None:
        nx, ny = int(new[0]), int(new[1])
        if not (0 <= nx < zone.width and 0 <= ny < zone.height):
            return True
        t = zone.terrain[ny][nx]
        if t == TerrainType.BUILDING:
            return True                    # a wall is a wall — fliers too
        if t in (TerrainType.WATER, TerrainType.MOUNTAIN):
            return not _is_flier(character)
        return False
    # overworld: buildings are solid footprints; the door is the one gap
    return crosses_building_wall(engine, character, old, new)


def ensure_wall_guard(engine) -> None:
    """Install the guard on the current world map if absent. Idempotent
    and cheap: streaming mutates the map in place (guard survives), and a
    freshly-built map re-installs on the next call."""
    import functools
    wmap = getattr(getattr(engine, "world", None), "map", None)
    if wmap is None:
        return
    if getattr(wmap, "wall_guard", None) is None:
        wmap.wall_guard = functools.partial(move_blocked, engine)
