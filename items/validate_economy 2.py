"""Cross-reference checks for the P16 economy data files.

Split out of `items/data_validate.py` (which was brushing the 500-line
rule): the supply chain (production.json), the building-type catalogue
(building_types.json), and the resource nodes (resource_nodes.json) all
reference skills, items, professions, terrains and each other, and this
is where those references are checked.
"""

from typing import List


def _known_item(item_id: str) -> bool:
    from items.item_registry import ITEM_REGISTRY
    return item_id in ITEM_REGISTRY


def check_production() -> List[str]:
    """production.json (P16.1): professions map to real skills, and the
    authored raws are real items with a valid skill/profession/source."""
    from engine.skill_progression import SKILLS
    from world.world_map import TerrainType
    from engine.production import PROFESSIONS, WORKSTATIONS
    from items.data_loader import load_data_file
    out = []
    prod = load_data_file("production.json") or {}
    for prof, skill in PROFESSIONS.items():
        if skill not in SKILLS:
            out.append(f"production: profession '{prof}' -> unknown "
                       f"skill '{skill}'")
    for skill in WORKSTATIONS:
        if skill not in SKILLS:
            out.append(f"production: workstation skill '{skill}' undefined")
    extra_sources = {"beast", "farmland"}
    for iid, spec in prod.get("raw", {}).items():
        if not _known_item(iid):
            out.append(f"production raw: unknown item '{iid}'")
        if spec.get("skill") not in SKILLS:
            out.append(f"production raw {iid}: unknown skill "
                       f"'{spec.get('skill')}'")
        if spec.get("profession") not in PROFESSIONS:
            out.append(f"production raw {iid}: unknown profession "
                       f"'{spec.get('profession')}'")
        src = spec.get("source", "")
        ok = src in extra_sources
        if not ok:
            try:
                TerrainType(src)
                ok = True
            except ValueError:
                ok = False
        if not ok:
            out.append(f"production raw {iid}: unknown source '{src}'")
    return out


def check_building_types() -> List[str]:
    """building_types.json (P16.3): every profession is a real producer
    profession, and every specialization lists catalogued kinds."""
    from world.building_types import TYPES, SPECIALIZATIONS
    from engine.production import PROFESSIONS
    out = []
    for kind, spec in TYPES.items():
        prof = spec.get("profession")
        if prof is not None and prof not in PROFESSIONS:
            out.append(f"building_types {kind}: unknown profession '{prof}'")
        if "function" not in spec:
            out.append(f"building_types {kind}: missing function")
    for spec_name, kinds in SPECIALIZATIONS.items():
        for k in kinds:
            if k not in TYPES:
                out.append(f"specialization {spec_name}: unknown kind '{k}'")
    return out


def check_resource_nodes() -> List[str]:
    """resource_nodes.json (P16.4): each node's skill is real and its
    terrain + leaves_tile are valid terrain types."""
    from engine.skill_progression import SKILLS
    from world.world_map import TerrainType
    from world.resource_nodes import SPECS
    out = []
    for kind, spec in SPECS.items():
        if spec.get("skill") not in SKILLS:
            out.append(f"resource_nodes {kind}: unknown skill "
                       f"'{spec.get('skill')}'")
        for field in ("terrain", "leaves_tile"):
            try:
                TerrainType(spec.get(field, ""))
            except ValueError:
                out.append(f"resource_nodes {kind}: unknown {field} "
                           f"'{spec.get(field)}'")
    return out
