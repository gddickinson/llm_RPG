"""BLD.3 — feature-composition furnishing (ported from autonomous_world's
`blueprint_gen.ROOM_FURNISHINGS` / `_furnish_room`).

Where BLD.2 fills a room with SCATTERED single props, a *feature* stamps a named
ARRANGEMENT: a bar gets an L-shaped counter, a nave gets pew rows facing an altar
down a carpet aisle, a great hall a colonnade. `data/room_templates.json` lists a
room_type's `features`; `world/room_plan.py` applies them before the fill pass.

Also here: the DOOR-APRON exclusion — a doorway tile and the floor directly in
front of it must stay clear so furniture never blocks a passage. Both room_plan
(typed kits + features) and furnishings (the decorative pass) exclude it.

Pure over the Interior grid; each feature returns [(x, y, name)] placed.
"""

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _wall(inter, x, y) -> bool:
    from world.world_map import TerrainType
    if not (0 <= x < inter.width and 0 <= y < inter.height):
        return True
    return inter.terrain[y][x] == TerrainType.BUILDING


def _free(inter, x, y, taken) -> bool:
    return (0 < x < inter.width - 1 and 0 < y < inter.height - 1
            and not _wall(inter, x, y) and (x, y) not in taken)


# ---- door-apron exclusion ------------------------------------------------

def doorways(inter) -> set:
    """Doorway tiles: a floor tile that gaps a wall (walls on opposite sides),
    plus the building entrance."""
    doors = set()
    for y in range(1, inter.height - 1):
        for x in range(1, inter.width - 1):
            if _wall(inter, x, y):
                continue
            if (_wall(inter, x - 1, y) and _wall(inter, x + 1, y)) or \
               (_wall(inter, x, y - 1) and _wall(inter, x, y + 1)):
                doors.add((x, y))
    if getattr(inter, "door", None):
        dx, dy = inter.door
        doors.add((dx, dy))
        doors.add((dx, dy - 1))                 # the tile just inside the door
    return doors


def apron(inter) -> set:
    """Doorway tiles + the floor directly around them — keep-clear zone."""
    out = set()
    for (x, y) in doorways(inter):
        out.add((x, y))
        for dx, dy in _DIRS:
            out.add((x + dx, y + dy))
    return out


# ---- composition stampers ------------------------------------------------

def bar_counter(inter, rect, taken, rng):
    """An L-shaped run of counter (Table) along a corner of the room."""
    rx, ry, rw, rh = rect
    placed = []
    for x in range(rx, rx + rw):                # horizontal arm along the top
        if _free(inter, x, ry, taken):
            placed.append((x, ry, "Table"))
            taken.add((x, ry))
        if len([p for p in placed if p[1] == ry]) >= max(2, rw - 1):
            break
    for y in range(ry + 1, ry + rh):            # vertical arm down the side
        if _free(inter, rx, y, taken):
            placed.append((rx, y, "Table"))
            taken.add((rx, y))
        if sum(1 for p in placed if p[0] == rx) >= max(2, rh - 1):
            break
    return placed


def pew_rows(inter, rect, taken, rng):
    """Rows of Pews every other tile, leaving a central aisle."""
    rx, ry, rw, rh = rect
    aisle = rx + rw // 2
    placed = []
    for y in range(ry, ry + rh, 2):
        for x in range(rx, rx + rw):
            if x == aisle:
                continue
            if _free(inter, x, y, taken):
                placed.append((x, y, "Pew"))
                taken.add((x, y))
    return placed


def pillar_row(inter, rect, taken, rng):
    """Two columns of Pillars down the room's long axis."""
    rx, ry, rw, rh = rect
    placed = []
    for y in range(ry, ry + rh, 2):
        for x in (rx, rx + rw - 1):
            if _free(inter, x, y, taken):
                placed.append((x, y, "Pillar"))
                taken.add((x, y))
    return placed


def carpet_runner(inter, rect, taken, rng):
    """A runner of Rug down the room's centre column (the aisle)."""
    rx, ry, rw, rh = rect
    cx = rx + rw // 2
    placed = []
    for y in range(ry, ry + rh):
        if _free(inter, cx, y, taken):
            placed.append((cx, y, "Rug"))
            taken.add((cx, y))
    return placed


def altar_end(inter, rect, taken, rng):
    """An Altar centred on the far (top) wall, opposite the entrance."""
    rx, ry, rw, rh = rect
    x = rx + rw // 2
    for y in range(ry, ry + rh):                # first free cell from the top
        if _free(inter, x, y, taken):
            taken.add((x, y))
            return [(x, y, "Altar")]
    return []


_FEATURES = {
    "bar_counter": bar_counter, "pew_rows": pew_rows,
    "pillar_row": pillar_row, "carpet_runner": carpet_runner,
    "altar_end": altar_end,
}


def apply_feature(name, inter, rect, taken, rng):
    fn = _FEATURES.get(name)
    return fn(inter, rect, taken, rng) if fn else []


# ---- BLD.6 decoration pass -----------------------------------------------

def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _front_of(inter, hx, hy, taken):
    """The floor tile in front of a hearth/forge (into the room, not the wall
    it backs onto) — prefer south, then the other free orthogonal neighbours."""
    for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
        x, y = hx + dx, hy + dy
        if _free(inter, x, y, taken):
            return (x, y)
    return None


def _wall_tiles(inter, taken):
    """Free floor tiles that back onto a wall — where a wall torch sits."""
    out = []
    for y in range(1, inter.height - 1):
        for x in range(1, inter.width - 1):
            if not _free(inter, x, y, taken):
                continue
            if any(_wall(inter, x + dx, y + dy) for dx, dy in _DIRS):
                out.append((x, y))
    return out


def decorate_pass(inter, seed: int = 0) -> int:
    """After furnishing, add ATMOSPHERE (ported from autonomous_world's Stage 5):
    a hearthRUG in front of each hearth/forge, and wall TORCHES spaced ~5 tiles
    apart. Torches are in `prop_sprites.LIT_PROPS`, so they immediately cast the
    P39.4 warm light pools that make a room legible. Returns props added."""
    import random
    rng = random.Random((seed ^ 0x9e37) & 0xffffffff)
    taken = {(f.get("x"), f.get("y")) for f in getattr(inter, "furniture", [])}
    taken |= apron(inter)
    if getattr(inter, "door", None):
        taken.add(tuple(inter.door))
    added = []
    # 1) a rug in front of every hearth / forge
    for f in list(getattr(inter, "furniture", [])):
        nm = (f.get("name") or "").lower()
        if "hearth" in nm or "forge" in nm or "fireplace" in nm:
            spot = _front_of(inter, f.get("x"), f.get("y"), taken)
            if spot:
                taken.add(spot)
                added.append({"name": "Rug", "x": spot[0], "y": spot[1]})
    # 2) wall torches, evenly spaced so the room is lit but not a bonfire
    walls = _wall_tiles(inter, taken)
    rng.shuffle(walls)
    lit = []
    for (x, y) in walls:
        if all(_cheb((x, y), p) >= 5 for p in lit):
            lit.append((x, y))
            taken.add((x, y))
            added.append({"name": "Torch", "x": x, "y": y})
    inter.furniture.extend(added)
    return len(added)
