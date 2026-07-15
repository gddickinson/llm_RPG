"""P39.6b — deterministic overworld decorative scatter placement (pure).

Decides WHICH overworld tiles carry a decorative prop (a boulder, deadwood,
mushroom cluster, ferns, reeds, flowers, a stump — or bones/gravestones on the
rubble that ruins leave) and WHICH prop, from a stable per-world-position hash,
so the scatter never flickers frame-to-frame and is IDENTICAL in the top-down
and isometric renderers. Recipes (terrain -> weighted props + density) live in
`data/overworld_scatter.json`. No state; a pure query the renderers call per
visible tile.
"""

import json
import os

_DATA = None


def _data():
    global _DATA
    if _DATA is None:
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "overworld_scatter.json")
        try:
            with open(p) as f:
                _DATA = json.load(f)
        except Exception:
            _DATA = {"density": 0.0, "terrain": {}}
    return _DATA


def _hash(wx, wy):
    h = (int(wx) * 73856093) ^ (int(wy) * 19349663)
    return h & 0x7fffffff


def prop_at(wx, wy, terrain_name):
    """The scatter prop name for this world tile, or None. Deterministic per
    (wx, wy, terrain) — same input always yields the same prop (or nothing)."""
    recipe = _data().get("terrain", {}).get(terrain_name)
    if not recipe:
        return None
    density = _data().get("density", 0.0)
    h = _hash(wx, wy)
    if (h % 1000) >= density * 1000:            # sparse density gate
        return None
    h2 = (h * 2654435761) & 0x7fffffff          # a second, decorrelated hash
    total = sum(max(1, e.get("w", 1)) for e in recipe)
    r = h2 % total
    acc = 0
    for e in recipe:
        acc += max(1, e.get("w", 1))
        if r < acc:
            return e.get("prop")
    return recipe[-1].get("prop")
