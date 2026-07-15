"""Building-type catalog & room classification (P16.3).

Ports autonomous_world's `SPECIALIZATION_BUILDINGS` + `_classify_room`
as data (`data/building_types.json`): every building KIND names the
FUNCTION it serves, the producer PROFESSION that works there (from the
P16.1 supply chain's set, or None for civic/service buildings), and the
MARKER furniture that identifies the room.

Two questions this answers, both used by the P16.2 economy so a town's
trade follows its BUILDINGS rather than its residents' character
classes:

  * `profession_of_kind(kind)` — a forge is a smith's smithy, a
    farmhouse a farmer's farm, a lodge a hunter's, regardless of who
    happens to live there.
  * `classify_interior(interior)` — when the kind is unknown or generic,
    read the furniture: an anvil-bearing room IS a smithy, an altar room
    a temple. Furniture → room-function → occupation.

Pure data + queries; the catalogue also lists new economic kinds
(mine/bakery/sawmill/dock) ahead of worldgen placing them, and the
settlement SPECIALIZATIONS those kinds compose into.
"""

import logging
from typing import Dict, List, Optional

from items.data_loader import load_data_file

logger = logging.getLogger("llm_rpg.building_types")


def _load() -> dict:
    try:
        return load_data_file("building_types.json") or {}
    except Exception as e:                                # pragma: no cover
        logger.warning(f"building_types.json unreadable: {e}")
        return {}


_DATA = _load()
TYPES: Dict[str, dict] = _DATA.get("types", {})
SPECIALIZATIONS: Dict[str, list] = _DATA.get("specializations", {})

# marker furniture -> the kind it identifies (first kind that claims it)
_MARKER_KIND: Dict[str, str] = {}
for _kind, _spec in TYPES.items():
    for _m in _spec.get("markers", []):
        _MARKER_KIND.setdefault(_m, _kind)


# ---- catalogue queries ----------------------------------------------

def all_kinds() -> List[str]:
    return list(TYPES.keys())


def type_of(kind: str) -> Optional[dict]:
    return TYPES.get(kind)


def profession_of_kind(kind: str) -> Optional[str]:
    """The producer profession that works a building of this kind, or
    None for civic/service buildings (shop/temple/watchtower/…)."""
    spec = TYPES.get(kind)
    return spec.get("profession") if spec else None


def function_of_kind(kind: str) -> Optional[str]:
    spec = TYPES.get(kind)
    return spec.get("function") if spec else None


def is_workshop(kind: str) -> bool:
    """A building that PRODUCES (has a profession), not a civic one."""
    return profession_of_kind(kind) is not None


def all_specializations() -> Dict[str, list]:
    return dict(SPECIALIZATIONS)


# ---- furniture -> room function -------------------------------------

def classify_interior(interior) -> Optional[str]:
    """The building KIND an interior's furniture marks it as — an anvil
    means a smithy, an altar a temple — or None if nothing distinctive."""
    from engine.furniture import _kind as furn_kind
    for piece in getattr(interior, "furniture", []) or []:
        k = furn_kind(piece.get("name", ""))
        kind = _MARKER_KIND.get(k)
        if kind:
            return kind
    return None
