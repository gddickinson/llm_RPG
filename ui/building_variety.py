"""OAKVALE T8 — per-building STYLE variety (deterministic by world position).

Every building of the same KIND used to render identically. George wants varied
designs — tudor half-timber beams, thatched vs tile vs slate roofs, stone vs
brick vs timber walls, different window shapes. This picks a per-building
variant from a KIND-appropriate palette, seeded by the building's WORLD
position via a pure integer hash (no RNG, no per-frame flicker) — so two houses
side by side differ, but each is stable and in-character (a cathedral stays
stone-and-slate, a cottage might be thatch-and-timber).

Pure; `variant_style` overrides a base style's covering + wall, and
`window_shape` / `door_style` vary the openings. `renderer_buildings` calls in.
"""

# a building's style CLASS → its covering + wall palettes
_COVERINGS = {
    "humble": ["thatch", "thatch", "shingle", "clay"],
    "trade": ["clay", "shingle", "slate", "thatch"],
    "civic": ["slate", "lead", "stone", "clay"],
    "sacred": ["slate", "lead", "stone"],
}
_WALLS = {
    "humble": ["timber", "timber", "wood", "brick"],   # tudor half-timber lean
    "trade": ["timber", "brick", "wood", "stone"],
    "civic": ["stone", "brick", "stone"],
    "sacred": ["stone", "stone", "brick"],
}
_CLASS = {
    "home": "humble", "cottage": "humble", "farmhouse": "humble",
    "stable": "humble", "storage": "humble", "granary": "humble",
    "shop": "trade", "stall": "trade", "tavern": "trade", "inn": "trade",
    "bakery": "trade", "smithy": "trade", "forge": "trade", "armoury": "trade",
    "workshop": "trade", "mill": "trade", "sawmill": "trade",
    "warehouse": "trade",
    "hall": "civic", "bank": "civic", "library": "civic", "guildhall": "civic",
    "tower": "civic", "watchtower": "civic",
    "temple": "sacred", "cathedral": "sacred", "chapel": "sacred",
    "shrine": "sacred",
}
# window shapes that suit each class (keys from ui/openings.window shapes)
_WINDOWS = {
    "humble": ["square", "square", "arched"],
    "trade": ["square", "arched", "round"],
    "civic": ["arched", "lancet", "square"],
    "sacred": ["lancet", "rose", "arched"],
}


def _hash(a: int, b: int, salt: int) -> int:
    h = (int(a) * 73856093) ^ (int(b) * 19349663) ^ (salt * 83492791)
    return h & 0x7FFFFFFF


def style_class(kind: str) -> str:
    return _CLASS.get(kind, "humble")


def variant_style(base: dict, kind: str, wx: int, wy: int) -> dict:
    """A copy of `base` with covering + wall picked per-building from the kind's
    palette (roof SHAPE + the rest kept). Deterministic in (wx, wy)."""
    cls = style_class(kind)
    covs = _COVERINGS.get(cls, _COVERINGS["humble"])
    walls = _WALLS.get(cls, _WALLS["humble"])
    out = dict(base or {})
    out["covering"] = covs[_hash(wx, wy, 1) % len(covs)]
    out["wall"] = walls[_hash(wx, wy, 2) % len(walls)]
    return out


def window_shape(kind: str, default: str, wx: int, wy: int) -> str:
    """A per-building window shape from the kind's class palette."""
    opts = _WINDOWS.get(style_class(kind))
    if not opts:
        return default
    return opts[_hash(wx, wy, 3) % len(opts)]
