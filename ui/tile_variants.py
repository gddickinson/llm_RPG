"""P33.1 per-tile variety + texture — the fix for the graph-paper grid.

The old `SpriteLoader.tile()` bakes ONE surface per terrain name, so every
grass/tree/water tile on screen is byte-identical and the map reads as a grid
of repeated stamps. Autonomous World's cure (ported here): bake a few VARIANTS
of each terrain — a weighted 3-shade dither plus a little scattered detail —
once, then pick which variant a tile shows from a HASH of its world position.
Deterministic (a tile always looks the same across frames and saves) but
neighbours differ, so the repetition dissolves.

This module is the pure, headless-testable core: `variant_index` (the hash),
`dither_grid` / `scatter_points` (deterministic noise), and the `RECIPES` data.
`build_tile` is the one thin pygame pass that turns a recipe + variant seed into
a Surface (lazy `import pygame`, like `renderer_buildings`). `SpriteLoader.tile_
variant` calls in and caches by (name, variant); the PNG-tileset path is left
untouched (a recipe only fires for procedural terrain).
"""

import random

N_VARIANTS = 4


def type_id(name: str) -> int:
    """A small stable integer per terrain name (varies the position hash)."""
    return sum(ord(c) for c in name) % 97


def variant_index(wx: int, wy: int, name: str, n: int = N_VARIANTS) -> int:
    """Which variant a tile at world (wx, wy) of `name` shows (AW's hash:
    deterministic per tile, neighbours differ)."""
    return (wx * 7 + wy * 13 + type_id(name) * 3) % max(1, n)


def _cum_weights(weights):
    total = float(sum(weights)) or 1.0
    out, acc = [], 0.0
    for w in weights:
        acc += w / total
        out.append(acc)
    return out


def dither_grid(size: int, seed: int, weights):
    """A size×size grid of shade-bucket indices, weighted-random and fully
    deterministic for a seed (identical every run → headless-testable)."""
    r = random.Random(seed)
    cum = _cum_weights(weights)
    grid = []
    for _y in range(size):
        row = []
        for _x in range(size):
            v = r.random()
            idx = len(cum) - 1
            for i, c in enumerate(cum):
                if v <= c:
                    idx = i
                    break
            row.append(idx)
        grid.append(row)
    return grid


def scatter_points(size: int, count: int, seed: int, margin: int = 2):
    """`count` deterministic (x, y) detail positions inside the tile."""
    r = random.Random(seed * 131 + 7)
    lo, hi = margin, max(margin, size - 1 - margin)
    return [(r.randint(lo, hi), r.randint(lo, hi)) for _ in range(max(0, count))]


# Per-terrain texture recipes. `shades`: (rgb, weight) buckets for the dither;
# `detail`: a scattered-feature spec drawn on top. Only these terrains get
# variants — buildings (2.5D blocks), caves and bridges keep the classic stamp.
RECIPES = {
    "grass":    {"shades": [((90, 150, 70), 6), ((70, 130, 60), 3),
                            ((112, 168, 88), 2)],
                 "detail": {"kind": "blades", "count": 11,
                            "color": (120, 178, 92)}},
    "forest":   {"shades": [((70, 120, 60), 5), ((45, 95, 50), 3),
                            ((88, 138, 72), 1)],
                 "detail": {"kind": "canopy", "count": 3,
                            "color": (34, 82, 42), "hi": (74, 122, 62)}},
    "water":    {"shades": [((45, 100, 180), 6), ((40, 90, 165), 3),
                            ((70, 140, 210), 2)],
                 "detail": {"kind": "ripples", "count": 3,
                            "color": (120, 176, 226)}},
    "mountain": {"shades": [((110, 100, 95), 5), ((92, 84, 80), 3),
                            ((140, 130, 125), 2)],
                 "detail": {"kind": "rocks", "count": 3, "color": (74, 68, 64),
                            "hi": (162, 152, 146)}},
    "swamp":    {"shades": [((62, 78, 52), 5), ((44, 62, 48), 3),
                            ((52, 72, 60), 2)],
                 "detail": {"kind": "reeds", "count": 4, "color": (40, 60, 44),
                            "hi": (38, 58, 66)}},
    "road":     {"shades": [((160, 130, 90), 6), ((140, 112, 78), 3),
                            ((178, 148, 108), 1)],
                 "detail": {"kind": "pebbles", "count": 6,
                            "color": (120, 96, 66), "hi": (190, 162, 122)}},
    "farmland": {"shades": [((124, 92, 56), 6), ((104, 76, 46), 3),
                            ((140, 106, 66), 1)],
                 "detail": {"kind": "furrows", "count": 4,
                            "color": (100, 72, 44)}},
    "rubble":   {"shades": [((105, 100, 95), 5), ((80, 76, 72), 3),
                            ((125, 120, 114), 2)],
                 "detail": {"kind": "chunks", "count": 4, "color": (72, 68, 64),
                            "hi": (140, 134, 128)}},
    "scorched": {"shades": [((48, 40, 36), 6), ((38, 32, 28), 3),
                            ((60, 50, 44), 1)],
                 "detail": {"kind": "ash", "count": 7, "color": (92, 84, 78)}},
}


def build_tile(name: str, variant: int, size: int, base_seed: int = 1):
    """Bake one variant Surface for a recipe terrain, or None if the terrain
    has no recipe. The single thin pygame pass (lazy import)."""
    recipe = RECIPES.get(name)
    if recipe is None:
        return None
    import pygame
    seed = base_seed * 1009 + variant * 37 + type_id(name)
    shades = [c for c, _ in recipe["shades"]]
    weights = [w for _, w in recipe["shades"]]
    grid = dither_grid(size, seed, weights)
    surf = pygame.Surface((size, size))
    for y in range(size):
        row = grid[y]
        for x in range(size):
            surf.set_at((x, y), shades[row[x]])
    _draw_detail(surf, size, recipe.get("detail"), seed + 555)
    return surf


def _draw_detail(surf, size, spec, seed):
    if not spec:
        return
    import pygame
    kind = spec["kind"]
    pts = scatter_points(size, spec.get("count", 4), seed)
    col = spec.get("color")
    hi = spec.get("hi")
    if kind == "blades":
        for (x, y) in pts:
            pygame.draw.line(surf, col, (x, y), (x, max(0, y - 2)))
    elif kind == "canopy":
        r = max(2, size // 5)
        for (x, y) in pts:
            pygame.draw.circle(surf, col, (x, y), r)
            pygame.draw.circle(surf, hi, (x - 1, y - 1), max(1, r // 2))
    elif kind == "ripples":
        for (x, y) in pts:
            w = max(3, size // 4)
            pygame.draw.line(surf, col, (x - w // 2, y), (x + w // 2, y))
    elif kind == "rocks":
        for (x, y) in pts:
            pygame.draw.line(surf, col, (x, y), (x + 2, y + 3))
            surf.set_at((min(size - 1, x + 1), y), hi)
    elif kind == "reeds":
        for i, (x, y) in enumerate(pts):
            if i == 0:
                pygame.draw.circle(surf, hi, (x, y), max(2, size // 6))
            else:
                pygame.draw.line(surf, col, (x, y), (x, max(0, y - 3)))
    elif kind == "pebbles":
        for i, (x, y) in enumerate(pts):
            surf.set_at((x, y), col if i % 2 else hi)
    elif kind == "furrows":
        n = spec.get("count", 4)
        for i in range(1, n):
            fy = size * i // n
            pygame.draw.line(surf, col, (0, fy), (size - 1, fy))
    elif kind == "chunks":
        for i, (x, y) in enumerate(pts):
            c = hi if i % 2 else col
            pygame.draw.rect(surf, c, (x, y, 2, 2))
    elif kind == "ash":
        for (x, y) in pts:
            surf.set_at((x, y), col)
