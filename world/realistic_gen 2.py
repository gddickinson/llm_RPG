"""P36.1 realistic terrain — a heightmap + moisture → Whittaker-lite biomes.

The classic worldgen paints flat grass + one river; this builds a real LANDSCAPE:
a multi-octave value-noise ELEVATION field (mountain ranges, valleys, coastlines,
lakes) and a MOISTURE field, mapped to the terrain palette so forests grow where
it's wet, marsh in wet lowlands, peaks on the heights, seas/lakes in the basins.
Adapted (not ported) from `autonomous_world/game/world/terrain_gen.py`. Pure +
numpy-vectorised + seed-reproducible; `WorldGenerator(mode="realistic")` calls in.
"""

import numpy as np

from world.world_map import TerrainType as T

SEA_LEVEL = 0.30
COAST = 0.345
HIGHLAND = 0.66
PEAK = 0.80


def _upsample(grid, w, h):
    """Bilinear + smoothstep upsample of a coarse grid to (h, w)."""
    gh, gw = grid.shape
    ys = np.linspace(0.0, gh - 1, h)
    xs = np.linspace(0.0, gw - 1, w)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    y1 = np.minimum(y0 + 1, gh - 1)
    x1 = np.minimum(x0 + 1, gw - 1)
    fy = (ys - y0)
    fx = (xs - x0)
    fy = (fy * fy * (3 - 2 * fy))[:, None]
    fx = (fx * fx * (3 - 2 * fx))[None, :]
    top = grid[np.ix_(y0, x0)] * (1 - fx) + grid[np.ix_(y0, x1)] * fx
    bot = grid[np.ix_(y1, x0)] * (1 - fx) + grid[np.ix_(y1, x1)] * fx
    return top * (1 - fy) + bot * fy


def fbm(w, h, seed, octaves=5, base_cells=4.0, gain=0.5):
    """A normalised [0,1] multi-octave value-noise field, seed-reproducible."""
    field = np.zeros((h, w), dtype=np.float32)
    amp, total, cells = 1.0, 0.0, base_cells
    for o in range(octaves):
        rng = np.random.default_rng(seed + o * 1013904223)
        gw = max(2, int(round(cells)) + 1)
        gh = max(2, int(round(cells * h / max(1, w))) + 1)
        field += _upsample(rng.random((gh, gw)).astype(np.float32), w, h) * amp
        total += amp
        amp *= gain
        cells *= 2.0
    field /= total
    lo, hi = float(field.min()), float(field.max())
    return (field - lo) / (hi - lo + 1e-9)


def _island_mask(w, h):
    """A soft radial falloff so the map edges tend to sea (a continent, not a
    tiled plane) — gentle, so inland terrain stays varied."""
    ys = np.linspace(-1.0, 1.0, h)[:, None]
    xs = np.linspace(-1.0, 1.0, w)[None, :]
    d = np.sqrt(xs * xs + ys * ys) / 1.4142
    return np.clip(1.0 - d ** 3 * 0.85, 0.0, 1.0).astype(np.float32)


def terrain_for(elev, moist):
    if elev < SEA_LEVEL:
        return T.WATER
    if elev < COAST:
        return T.GRASS                     # a beach/coast (no sand terrain)
    if elev >= PEAK:
        return T.MOUNTAIN
    if elev >= HIGHLAND:
        return T.MOUNTAIN if moist < 0.45 else T.FOREST
    if elev < 0.40 and moist > 0.70:
        return T.SWAMP                     # wet lowland → marsh
    if moist > 0.58:
        return T.FOREST
    return T.GRASS


def assign_terrain(wmap, seed):
    """Fill `wmap.terrain` from a heightmap + moisture. Returns the elevation
    array (for river/settlement placement in later phases)."""
    w, h = wmap.width, wmap.height
    elev = fbm(w, h, seed, octaves=5, base_cells=3.0)
    elev = elev * 0.78 + _island_mask(w, h) * 0.22      # bias edges toward sea
    lo, hi = float(elev.min()), float(elev.max())
    elev = (elev - lo) / (hi - lo + 1e-9)
    moist = fbm(w, h, seed + 71993, octaves=4, base_cells=2.5)
    for y in range(h):
        row = wmap.terrain[y]
        ey, my = elev[y], moist[y]
        for x in range(w):
            row[x] = terrain_for(float(ey[x]), float(my[x]))
    return elev


_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def flow_accumulation(elev):
    """P36.2 D8 flow accumulation: every land cell drains to its steepest-downhill
    neighbour; return the accumulated upstream drainage per cell. Processing cells
    from HIGH to LOW means each cell's total is known before its outlet's."""
    h, w = elev.shape
    acc = np.ones((h, w), dtype=np.float32)
    order = np.argsort(elev, axis=None)[::-1]           # high → low
    ef = elev
    for flat in order:
        y, x = divmod(int(flat), w)
        e = ef[y, x]
        by, bx, be = -1, -1, e
        for dy, dx in _D8:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and ef[ny, nx] < be:
                be, by, bx = ef[ny, nx], ny, nx
        if by >= 0:
            acc[by, bx] += acc[y, x]
    return acc


def carve_rivers(wmap, elev, percentile=98.5):
    """Carve WATER where drainage concentrates on LAND — rivers running downhill
    from the highlands to the sea/lakes. Returns the number of river tiles."""
    acc = flow_accumulation(elev)
    h, w = elev.shape
    land = elev >= SEA_LEVEL
    if not land.any():
        return 0
    thresh = float(np.percentile(acc[land], percentile))
    carved = 0
    for y in range(h):
        row = wmap.terrain[y]
        for x in range(w):
            if land[y, x] and acc[y, x] >= thresh and row[x] != T.WATER:
                row[x] = T.WATER
                carved += 1
    return carved
