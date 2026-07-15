"""BLD.2 — functional room typing (the interior "unlock").

The BSP subdivision (`world/room_gen.py`) makes ANONYMOUS rooms, and the old
`_furnish_rooms` filled them with a generic kit by SIZE RANK — a tavern's second
room and a temple's second room both got "bed + chest". Here each leaf room is
tagged a ROOM TYPE drawn from the building's room-set (`data/building_room_sets
.json`) — the public room touches the entrance, the rest fill by descending area
— and furnished with that type's kit (`data/room_templates.json`). So a tavern
becomes a common room + bar + kitchen + guest rooms, a smithy a forge + workshop,
a temple a nave + sanctuary + vestry.

Ported from autonomous_world's ROOM_TEMPLATES / BUILDING_ROOM_SETS. Pure over the
Interior grid, seed-reproducible; `interiors._furnish_rooms` delegates here.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.room_plan")

_TEMPLATES = None
_ROOM_SETS = None

# furniture that belongs in the middle of a room (everything else hugs a wall)
_CENTER = {"table", "rug", "well", "fountain", "altar", "throne", "dais",
           "mosaic", "anvil", "pew"}


def _load(fname: str, key: str) -> dict:
    try:
        from items.data_loader import load_data_file
        return load_data_file(fname).get(key, {})
    except Exception as e:                                # pragma: no cover
        logger.debug(f"{fname}: {e}")
        return {}


def _templates() -> dict:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _load("room_templates.json", "room_types")
    return _TEMPLATES


def _room_sets() -> dict:
    global _ROOM_SETS
    if _ROOM_SETS is None:
        try:
            from items.data_loader import load_data_file
            _ROOM_SETS = load_data_file("building_room_sets.json") or {}
        except Exception as e:                            # pragma: no cover
            logger.debug(f"building_room_sets.json: {e}")
            _ROOM_SETS = {}
    return _ROOM_SETS


def room_set_for(kind: str) -> list:
    """The ordered room-type list for a building — by raw KIND first, then its
    FUNCTION, then the default."""
    sets = _room_sets()
    k = (kind or "").lower()
    by_kind = sets.get("by_kind", {})
    if k in by_kind:
        return list(by_kind[k])
    by_fn = sets.get("by_function", {})
    if k in by_fn:
        return list(by_fn[k])
    try:
        from world.building_types import function_of_kind
        fn = function_of_kind(k)
        if fn in by_fn:
            return list(by_fn[fn])
    except Exception:
        pass
    return list(sets.get("default", ["hearth_room", "bedroom", "storeroom"]))


def _room_at(rooms, x, y):
    for r in rooms:
        rx, ry, rw, rh = r
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return r
    return None


def assign_types(rooms, door, room_set):
    """[(rect, room_type)] — the leaf touching the entrance is the public room
    (room_set[0]); the rest take the remaining types by descending area."""
    if not rooms:
        return []
    ent = _room_at(rooms, door[0], door[1] - 1) or \
        max(rooms, key=lambda r: r[2] * r[3])
    others = sorted((r for r in rooms if r != ent),
                    key=lambda r: -(r[2] * r[3]))
    out = [(ent, room_set[0] if room_set else "hearth_room")]
    rest = room_set[1:] if len(room_set) > 1 else room_set
    for i, r in enumerate(others):
        t = rest[i] if i < len(rest) else (rest[-1] if rest else "storeroom")
        out.append((r, t))
    return out


def _cells(inter, rect, taken):
    """Free floor cells of a room, split into wall-adjacent + central."""
    from world.world_map import TerrainType
    wall = TerrainType.BUILDING
    rx, ry, rw, rh = rect
    walls, centres = [], []
    for y in range(max(1, ry), min(inter.height - 1, ry + rh)):
        for x in range(max(1, rx), min(inter.width - 1, rx + rw)):
            if inter.terrain[y][x] == wall or (x, y) in taken:
                continue
            n = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if inter.terrain[y + dy][x + dx] == wall)
            (walls if n >= 1 else centres).append((x, y))
    return walls, centres


def furnish_typed(inter, rooms, kind, seed) -> None:
    """Assign each leaf a room_type and lay its furniture kit. Mutates
    `inter.furniture` (+ `npc_spots`); keeps prior furniture that is on floor."""
    from world.world_map import TerrainType
    rng = random.Random((seed ^ 0x2f3d) & 0xffffffff)
    room_set = room_set_for(kind)
    templates = _templates()

    # the BSP rebuilt the room layout, so the blueprint furniture's positions
    # are meaningless — discard it (the room kits re-furnish each room by its
    # function) and keep only structural stairs, so rooms don't double up
    kept = [f for f in inter.furniture
            if "stair" in f.get("name", "").lower()]
    taken = {(f["x"], f["y"]) for f in kept} | {tuple(inter.door)}
    added, npc_spots = [], []
    for idx, (rect, rtype) in enumerate(assign_types(rooms, inter.door, room_set)):
        kit = templates.get(rtype, {}).get("furniture", [])
        walls, centres = _cells(inter, rect, taken)
        rng.shuffle(walls)
        rng.shuffle(centres)
        cap = max(1, (len(walls) + len(centres)) // 3)   # keep the room roomy
        placed = 0
        for (name, lo, hi) in kit:
            if placed >= cap:
                break
            central = name.lower() in _CENTER
            primary = centres if central else walls
            backup = walls if central else centres
            for _ in range(rng.randint(lo, hi)):
                if placed >= cap:
                    break
                spot = primary.pop() if primary else (backup.pop() if backup
                                                      else None)
                if spot is None:
                    break
                taken.add(spot)
                added.append({"name": name, "x": spot[0], "y": spot[1]})
                placed += 1
        if idx == 0:                                     # public room → NPC spot
            rx, ry, rw, rh = rect
            npc_spots.append((rx + rw // 2, ry + rh // 2))
    inter.furniture = kept + added
    if npc_spots:
        inter.npc_spots = npc_spots
