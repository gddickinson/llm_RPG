"""Supply-chain origins (P16.1) — every item has a producer.

Ported from `autonomous_world`'s supply-chain shape, adapted to our
data: this module answers, for any economic item, WHERE it comes from —
a RAW material (gathered / farmed / hunted from a source tile by a
profession, with a tool) or a CRAFTED good (made from inputs at a
workstation by a profession + skill). Every profession gains a purpose
and every object a maker, which is the foundation the P16.2 NPC
production loop stands on (gatherers fill stores from tiles, crafters
consume inputs, merchants arbitrage surplus).

It is DRY by construction: the mining/woodcutting/fishing raws come
from `data/gathering.json` and the crafted goods from
`data/recipes.json`, so those single sources never drift; this module
merges them with `data/production.json`, which adds only what those
files lack — the profession layer, the workstations, and the farmed /
foraged / hunted raws that live outside the gathering nodes. The result
is one unified `origin_of(item)` view. Pure data + queries, no state.
"""

import logging
from typing import Dict, List, Optional

from items.data_loader import load_data_file

logger = logging.getLogger("llm_rpg.production")

RAW = "raw"
CRAFTED = "crafted"


def _load(name: str, default):
    try:
        return load_data_file(name) or default
    except Exception as e:                               # pragma: no cover
        logger.warning(f"{name} unreadable: {e}")
        return default


_PROD = _load("production.json", {})
PROFESSIONS: Dict[str, str] = _PROD.get("professions", {})   # prof -> skill
WORKSTATIONS: Dict[str, str] = _PROD.get("workstations", {})  # skill -> station
# skill -> canonical producer profession (invert; last wins, but the
# only doubled skill — foraging — is used only via explicit `raw` specs)
_SKILL_PROF: Dict[str, str] = {sk: pr for pr, sk in PROFESSIONS.items()}


def _build_index() -> Dict[str, dict]:
    idx: Dict[str, dict] = {}

    # 1. gathered raws — mining / woodcutting / fishing (gathering.json)
    for skill, node in _load("gathering.json", {}).items():
        prof = _SKILL_PROF.get(skill, skill)
        terrains = node.get("terrain", [])
        src = terrains[0] if terrains else ""
        for tier in node.get("tiers", []):
            iid = tier.get("item")
            if not iid:
                continue
            idx[iid] = {"kind": RAW, "item": iid, "skill": skill,
                        "profession": prof, "source": src,
                        "tool": node.get("tool"),
                        "level": tier.get("level", 1), "yield": 1}

    # 2. authored raws — farmed / foraged / hunted (production.json)
    for iid, spec in _PROD.get("raw", {}).items():
        idx[iid] = {"kind": RAW, "item": iid,
                    "skill": spec.get("skill", ""),
                    "profession": spec.get("profession", ""),
                    "source": spec.get("source", ""),
                    "tool": spec.get("tool"),
                    "level": spec.get("level", 1),
                    "yield": spec.get("yield", 1)}

    # 3. crafted goods (recipes.json) — a recipe IS a production step
    for out, rec in _load("recipes.json", {}).items():
        skill = rec.get("skill", "")
        idx[out] = {"kind": CRAFTED, "item": out, "skill": skill,
                    "profession": _SKILL_PROF.get(skill, skill),
                    "workstation": rec.get("required_property")
                    or WORKSTATIONS.get(skill),
                    "level": rec.get("level", 1),
                    "inputs": dict(rec.get("ingredients", {}))}
    return idx


_INDEX: Dict[str, dict] = _build_index()


# ---- queries --------------------------------------------------------

def origin_of(item_id: str) -> Optional[dict]:
    """The production origin of an item, or None (bought/looted only)."""
    return _INDEX.get(item_id)


def is_raw(item_id: str) -> bool:
    o = _INDEX.get(item_id)
    return bool(o and o["kind"] == RAW)


def is_crafted(item_id: str) -> bool:
    o = _INDEX.get(item_id)
    return bool(o and o["kind"] == CRAFTED)


def raw_materials() -> List[str]:
    return [i for i, o in _INDEX.items() if o["kind"] == RAW]


def crafted_goods() -> List[str]:
    return [i for i, o in _INDEX.items() if o["kind"] == CRAFTED]


def profession_of(item_id: str) -> Optional[str]:
    o = _INDEX.get(item_id)
    return o.get("profession") if o else None


def producers(profession: str) -> List[str]:
    """Every item a profession makes (raw or crafted)."""
    return [i for i, o in _INDEX.items()
            if o.get("profession") == profession]


def all_professions() -> List[str]:
    return sorted(PROFESSIONS.keys())


def skill_for_profession(profession: str) -> Optional[str]:
    return PROFESSIONS.get(profession)


def profession_for_skill(skill: str) -> Optional[str]:
    """The canonical producer profession for a skill (P16.2 uses this to
    turn an NPC's taught skill into what they make)."""
    return _SKILL_PROF.get(skill)


def primary_raw(profession: str) -> Optional[str]:
    """The main raw a gathering profession pulls (its first raw)."""
    for item in producers(profession):
        if is_raw(item):
            return item
    return None


def inputs_of(item_id: str) -> Dict[str, int]:
    """The crafted inputs of an item (empty for raws / unknowns)."""
    o = _INDEX.get(item_id)
    return dict(o.get("inputs", {})) if o else {}


def source_of(item_id: str) -> Optional[str]:
    """The source tile / origin of a raw material (None for crafted)."""
    o = _INDEX.get(item_id)
    return o.get("source") if o and o["kind"] == RAW else None


def all_origins() -> Dict[str, dict]:
    return dict(_INDEX)
