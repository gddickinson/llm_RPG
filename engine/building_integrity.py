"""Building STRUCTURAL integrity (George): knocking a hole in a wall shows up
INSIDE too, and once enough of a building's walls are gone the whole thing
COLLAPSES into rubble. Repairs propagate back. Built on the existing
`tile_damage` (walls → rubble, material-typed) + `earthworks` (the outside↔inside
breach map). `on_wall_destroyed` is called by `tile_damage` the moment a BUILDING
tile falls; `sync_interior` re-mirrors the footprint into the interior.
"""

import logging

logger = logging.getLogger("llm_rpg.building")

COLLAPSE_FRACTION = 0.5      # half a building's walls gone → it comes down


def building_at(engine, x, y):
    """The ENTERABLE building (a Location with an interior) whose footprint holds
    (x, y), or None (a lone wall / town rampart isn't a building)."""
    interiors = getattr(engine, "interiors", None) or {}
    for loc in engine.world.locations:
        if getattr(loc, "name", None) not in interiors:
            continue
        if loc.x <= x < loc.x + loc.width and loc.y <= y < loc.y + loc.height:
            return loc
    return None


def _footprint_wall_count(engine, loc):
    """(standing_walls, rubble) over the building's footprint."""
    from world.world_map import TerrainType
    wmap = engine.world.map
    walls = rubble = 0
    for yy in range(loc.y, min(loc.y + loc.height, wmap.height)):
        for xx in range(loc.x, min(loc.x + loc.width, wmap.width)):
            t = wmap.terrain[yy][xx]
            if t == TerrainType.BUILDING:
                walls += 1
            elif t == TerrainType.RUBBLE:
                rubble += 1
    return walls, rubble


def sync_interior(engine, loc) -> None:
    """Re-mirror the building's exterior breaches into its interior (real-time,
    not just on entry) so a hole outside is a hole inside."""
    inter = (getattr(engine, "interiors", None) or {}).get(loc.name)
    if inter is None:
        return
    try:
        from engine.earthworks import sync_breaches
        sync_breaches(engine, loc, inter)
    except Exception as e:
        logger.debug(f"interior sync failed: {e}")


def on_wall_destroyed(engine, x, y) -> None:
    """Called by `tile_damage` when a BUILDING tile becomes rubble: mirror the
    breach inside and collapse the building if too much is gone."""
    loc = building_at(engine, x, y)
    if loc is None:
        return
    sync_interior(engine, loc)
    _maybe_collapse(engine, loc)


def _maybe_collapse(engine, loc) -> None:
    if (loc.properties or {}).get("collapsed"):
        return
    walls, rubble = _footprint_wall_count(engine, loc)
    total = walls + rubble
    if total < 2 or walls == 0:
        return
    if rubble / total < COLLAPSE_FRACTION:
        return
    # the structure fails — every standing wall comes down at once
    from world.world_map import TerrainType
    wmap = engine.world.map
    td = getattr(engine, "tile_damage", None)
    for yy in range(loc.y, min(loc.y + loc.height, wmap.height)):
        for xx in range(loc.x, min(loc.x + loc.width, wmap.width)):
            if wmap.terrain[yy][xx] == TerrainType.BUILDING:
                wmap.set_terrain(xx, yy, TerrainType.RUBBLE)
                if td is not None:
                    td.rubble_depth[(xx, yy)] = td.rubble_depth.get((xx, yy), 0) + 1
                    td.tile_hp.pop((xx, yy), None)
    loc.properties["collapsed"] = True
    sync_interior(engine, loc)
    try:
        engine.memory_manager.add_event(
            f"[!] {loc.name} groans and CAVES IN — reduced to a heap of rubble!")
    except Exception:
        pass
