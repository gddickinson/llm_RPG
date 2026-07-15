"""P39.3 — themed furnishing: decorate an interior with theme-appropriate props.

Where P39.1 (the prop sprites) and P39.2 (interior themes) meet: a tomb gets
sarcophagi + braziers + urns + cobwebs + bones; a temple gets an altar + pillars
+ braziers + pews; a smithy gets a forge + anvil + weapon racks. `furnish(inter,
name, seed)` reads the theme from the interior's NAME (the same keywords the
renderer themes on, from `data/interior_themes.json`), looks up its prop list in
`data/furnishings.json`, and lays each prop out by a WALL-PREFERENCE pass
(adapted from building-gen's fixtures.py) — pillars/tapestries against walls,
braziers/urns/cobwebs in corners, an altar/dais/throne mid-room — skipping tiles
that already hold walls, doors, stairs, or furniture, and any functional piece
already present so nothing doubles. Pure over the Interior; deterministic.
"""

import logging
import random
import zlib

logger = logging.getLogger("llm_rpg.furnishings")

_THEMES = None
_FURN = None


def _load(fname: str) -> dict:
    try:
        from items.data_loader import load_data_file
        return load_data_file(fname) or {}
    except Exception as e:
        logger.debug(f"{fname}: {e}")
        return {}


def _theme_keywords() -> dict:
    global _THEMES
    if _THEMES is None:
        _THEMES = _load("interior_themes.json").get("themes", {})
    return _THEMES


def _furnishings() -> dict:
    global _FURN
    if _FURN is None:
        _FURN = _load("furnishings.json").get("themes", {})
    return _FURN


# BLD.1: building FUNCTION → interior theme, so a building whose name doesn't
# happen to carry a theme keyword still furnishes by what it IS (a market shop
# no longer falls through to a bedroom-and-hearthrug "home").
_FUNCTION_THEME = {
    "smithy": "smithy", "tavern": "tavern", "temple": "temple",
    "shrine": "temple", "library": "library", "market": "shop",
    "farm": "farmhouse", "lodge": "lodge", "tower": "tower",
    "bakery": "bakery", "watch": "watchtower", "hall": "hall",
    "stable": "stable", "well": "well", "storage": "storage",
    "mine": "cave", "sawmill": "storage", "mill": "storage", "dock": "storage",
}


def theme_of(name: str, kind: str = None) -> str:
    """The theme id for an interior — a keyword match on its NAME first (the
    same match the renderer uses), then, failing that, the building KIND's
    FUNCTION (BLD.1), and finally 'home'."""
    hay = (name or "").lower()
    for tid, spec in _theme_keywords().items():
        if any(k in hay for k in spec.get("keywords", [])):
            return tid
    if kind:
        try:
            from world.building_types import function_of_kind
            t = _FUNCTION_THEME.get(function_of_kind(kind))
            if t:
                return t
        except Exception:
            pass
    return "home"


def _buckets(inter) -> dict:
    """Classify free inner floor tiles: wall-adjacent / corner / centre / any."""
    from world.world_map import TerrainType
    wall = TerrainType.BUILDING
    taken = {(f.get("x"), f.get("y")) for f in inter.furniture}
    if getattr(inter, "door", None):
        taken.add(tuple(inter.door))
    for attr in ("stairs_up", "stairs_down"):
        s = getattr(inter, attr, None)
        if s:
            taken.add(tuple(s))
    for sp in getattr(inter, "spawns", None) or []:      # structure monsters
        at = sp.get("at") if isinstance(sp, dict) else None
        if at:
            taken.add(tuple(at))
    walls, corners, centres, scatter = [], [], [], []
    for y in range(1, inter.height - 1):
        for x in range(1, inter.width - 1):
            if inter.terrain[y][x] == wall or (x, y) in taken:
                continue
            n = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if inter.terrain[y + dy][x + dx] == wall)
            scatter.append((x, y))
            if n >= 2:
                corners.append((x, y))
            elif n == 1:
                walls.append((x, y))
            else:
                centres.append((x, y))
    return {"wall": walls, "corner": corners, "center": centres,
            "scatter": scatter}


def furnish(inter, name: str, seed: int = 0, kind: str = None) -> int:
    """Add themed decorative props to `inter`. Returns how many were placed.
    `kind` (the building kind) lets an oddly-named building still furnish by
    function (BLD.1)."""
    specs = _furnishings().get(theme_of(name, kind), {}).get("props", [])
    if not specs or inter.width < 3 or inter.height < 3:
        return 0
    rng = random.Random(zlib.crc32((name or "").encode("utf-8")) ^ (seed & 0xffffffff))
    buckets = _buckets(inter)
    for b in buckets.values():
        rng.shuffle(b)
    existing = {f.get("name", "").lower() for f in inter.furniture}
    used = set()
    added = 0
    # don't overcrowd — at most a third of the inner floor becomes props
    cap = max(2, (inter.width - 2) * (inter.height - 2) // 3)
    for spec in specs:
        pname = spec.get("name", "")
        if not pname or pname.lower() in existing:
            continue                                  # keep functional pieces
        pool = buckets.get(spec.get("where", "scatter")) or buckets["scatter"]
        placed = 0
        want = spec.get("n", 1)
        for (x, y) in pool:
            if added >= cap or placed >= want:
                break
            if (x, y) in used:
                continue
            used.add((x, y))
            inter.furniture.append({"name": pname, "x": x, "y": y})
            placed += 1
            added += 1
    return added
