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

# P40.2 supersample factor for terrain (built once, cached). The renderer sets
# this from the "Smooth sprites" setting (3 on / 1 off); `LLM_RPG_SS` overrides.
SSAA = None                     # None → gfx.ss_factor() decides at build time


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


def build_tile(name: str, variant: int, size: int, base_seed: int = 1, ss=None):
    """Bake one variant Surface for a recipe terrain, or None if the terrain
    has no recipe. P40.2: the tile is a LAYER STACK — gradient base + multi-tone
    mottle + dense scattered detail + a directional light — built at `size·ss`
    and smoothscaled down (via `gfx.supersample`) so it reads high-res. Cached
    by the caller. `ss` defaults to the module `SSAA` (renderer setting)."""
    recipe = RECIPES.get(name)
    if recipe is None:
        return None
    from ui import gfx
    seed = base_seed * 1009 + variant * 37 + type_id(name)
    factor = gfx.ss_factor(3) if (ss is None and SSAA is None) else \
        (SSAA if ss is None else ss)
    return gfx.supersample(lambda S: _paint_tile(recipe, S, seed), size, factor)


def _paint_tile(recipe, S: int, seed: int):
    """Compose one terrain tile at working size S (the supersampled canvas)."""
    from ui import gfx
    shades = [c for c, _ in recipe["shades"]]
    dominant = shades[0]
    by_bright = sorted(shades, key=sum)
    dark, light = by_bright[0], by_bright[-1]
    ramp = gfx.shade_ramp(dominant, 6)
    # 1) gradient base — a subtle top-light → bottom-dark, not a flat fill
    surf = gfx.vgradient(S, gfx.scale_rgb(light, 1.05), gfx.scale_rgb(dark, 0.95))
    # 2) mottle — multi-tone soft patches (the texture the flat dither lacked)
    tones = shades + [ramp[1], ramp[2], ramp[4]]
    gfx.mottle(surf, tones, seed, density=recipe.get("density", 0.55),
               blob=max(2, S // 7))
    # 3) dense scattered detail (blades / ripples / canopy …), S-proportional
    _draw_detail(surf, S, recipe.get("detail"), seed + 555)
    # 4) directional light — consistent top-left highlight, bottom-right shadow
    surf.blit(gfx.directional_light(S, recipe.get("light", 28)), (0, 0))
    return surf


def _draw_detail(surf, S, spec, seed):
    """Scatter the recipe's detail features across the tile, sized relative to
    the working canvas S (so detail scales with the oversample) and ~3× denser
    than the flat original."""
    if not spec:
        return
    import pygame
    kind = spec["kind"]
    unit = max(1, S // 24)
    factor = max(1, S // 40)                  # ~3 at ss=3 → denser detail
    count = spec.get("count", 4) * factor
    pts = scatter_points(S, count, seed)
    col = spec.get("color")
    hi = spec.get("hi") or col
    rr = random.Random(seed * 3 + 1)
    lw = max(1, unit // 2)
    if kind == "blades":
        for (x, y) in pts:
            h = rr.randint(unit, unit * 3)
            shade = col if rr.random() < 0.7 else hi
            pygame.draw.line(surf, shade, (x, y), (x, max(0, y - h)), lw)
    elif kind == "canopy":
        r = max(2, S // 6)
        for (x, y) in pts:
            pygame.draw.circle(surf, col, (x, y), r)
            pygame.draw.circle(surf, hi, (x - unit, y - unit), max(1, r // 2))
    elif kind == "ripples":
        for (x, y) in pts:
            w = max(3, S // 4)
            rect = pygame.Rect(x - w // 2, y - unit, w, unit * 2)
            pygame.draw.arc(surf, col, rect, 3.6, 5.8, lw)
    elif kind == "rocks":
        for (x, y) in pts:
            pygame.draw.line(surf, col, (x, y), (x + unit, y + unit), lw)
            pygame.draw.circle(surf, hi, (x, y), max(1, lw))
    elif kind == "reeds":
        for i, (x, y) in enumerate(pts):
            if i % 5 == 0:
                pygame.draw.circle(surf, hi, (x, y), max(2, S // 8))
            else:
                pygame.draw.line(surf, col, (x, y), (x, max(0, y - unit * 2)), lw)
    elif kind == "pebbles":
        for i, (x, y) in enumerate(pts):
            pygame.draw.circle(surf, col if i % 2 else hi, (x, y), max(1, lw))
    elif kind == "furrows":
        n = spec.get("count", 4) + 1
        for i in range(1, n):
            fy = S * i // n
            pygame.draw.line(surf, col, (0, fy), (S - 1, fy), lw)
    elif kind == "chunks":
        for i, (x, y) in enumerate(pts):
            c = hi if i % 2 else col
            pygame.draw.rect(surf, c, (x, y, unit + 1, unit + 1))
    elif kind == "ash":
        for (x, y) in pts:
            pygame.draw.circle(surf, col, (x, y), max(1, lw))
