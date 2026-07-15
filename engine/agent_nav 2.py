"""Away-agent navigation safety (2026-07-12) — the movement layer that
keeps a driven hero from EVER freezing: walkability that understands
both the overworld and the grid the hero is standing inside (a building
interior or a dungeon), a flee that sidesteps a walled escape, and a
"step toward a goal, but only onto a tile you can actually reach" move.

Split from `agent_controller` to hold the 500-line line. Pure functions
over (engine, char); no state of their own.
"""

from world.world_map import TerrainType

DIRS8 = ((1, 0), (-1, 0), (0, 1), (0, -1),
         (1, 1), (1, -1), (-1, 1), (-1, -1))

_SOLID = (TerrainType.MOUNTAIN, TerrainType.WATER)


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _toward(frm, to):
    return ((to[0] > frm[0]) - (to[0] < frm[0]),
            (to[1] > frm[1]) - (to[1] < frm[1]))


def active_zone(engine):
    """The interior/dungeon grid the hero is inside, or None on the map."""
    try:
        return engine.active_zone()
    except Exception:
        return None


def walkable(engine, char, pos) -> bool:
    """Could the hero actually step onto `pos` this turn? Checks the grid
    it is ON — the active zone's floor when indoors/underground, else the
    overworld — mirroring the real move gates without mutating."""
    zone = active_zone(engine)
    grid = zone if zone is not None else engine.world.map
    x, y = pos
    try:
        if not (0 <= x < grid.width and 0 <= y < grid.height):
            return False
        t = grid.terrain[y][x]
    except Exception:
        return False
    if zone is not None:
        if t in _SOLID or t == TerrainType.BUILDING:
            return False
        for spot in getattr(zone, "visitors", {}).values():
            if tuple(spot) == (x, y):
                return False
        for npc in engine.npc_manager.npcs.values():
            if npc.is_active() and npc.position == (x, y) \
                    and npc.id.startswith(("enc_", "tut_")):
                return False
        return True
    # overworld: skirt buildings entirely — an away hero has no reason to
    # be indoors, and stepping on a door auto-enters, then it exits, then
    # re-enters... an endless doorway shuffle (2026-07-12b)
    if t in _SOLID or t == TerrainType.BUILDING:
        return False
    guard = getattr(grid, "wall_guard", None)
    old = getattr(char, "position", None)
    if guard is not None and old is not None and guard(char, old, (x, y)):
        return False
    return (x, y) not in grid.characters


def flee_step(engine, char, threat_pos, avoid=()):
    """A WALKABLE step that opens (or at least doesn't lose) distance from
    `threat_pos`. Tries every neighbour and takes the one that gets
    furthest away, breaking ties AGAINST recently-stood tiles (`avoid`) so
    a hero doesn't ping-pong between two spots when the threat shifts. None
    when truly cornered (every escape blocked or closes in): the caller
    then turns and FIGHTS."""
    x, y = char.position
    cur = _dist(char.position, threat_pos)
    best, score = None, None
    for dx, dy in DIRS8:
        nxt = (x + dx, y + dy)
        gain = _dist(nxt, threat_pos)
        if gain <= cur - 1 or not walkable(engine, char, nxt):
            continue
        s = gain - (0.5 if nxt in avoid else 0)     # shun the way we came
        if score is None or s > score:
            best, score = (dx, dy), s
    return best


def safe_step(engine, char, goal, avoid=()):
    """Step toward `goal`, but only onto a tile the hero can actually
    reach. If the straight-toward tile is blocked, take the walkable
    neighbour that gets closest to the goal — so a hero heading for an
    awkward or unreachable goal routes around walls instead of walking
    on the spot. `avoid` (recently-stood tiles) is penalised so the hero
    doesn't oscillate back and forth between two spots at a dead end.
    (0, 0) only when boxed in on every side."""
    x, y = char.position
    want = _toward(char.position, goal)
    fwd = (x + want[0], y + want[1])
    if want != (0, 0) and walkable(engine, char, fwd) and fwd not in avoid:
        return want
    best, bd = (0, 0), None
    for dx, dy in DIRS8:
        nxt = (x + dx, y + dy)
        if not walkable(engine, char, nxt):
            continue
        d = _dist(nxt, goal) + (4 if nxt in avoid else 0)   # break 2-cycles
        if bd is None or d < bd:
            best, bd = (dx, dy), d
    return best


def zone_roam(engine, char, zone, rng):
    """A random WALKABLE tile inside the zone to head for — so the hero
    prowls a dungeon floor's rooms rather than standing still."""
    for _ in range(20):
        gx, gy = rng.randint(0, zone.width - 1), rng.randint(0, zone.height - 1)
        if walkable(engine, char, (gx, gy)):
            return (gx, gy)
    return tuple(char.position)
