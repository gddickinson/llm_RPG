"""Content validators for the living-world data files (M.6/M.7b) —
adventurers and guild halls. Split from `data_validate` to hold the
500-line line; each returns a list of problem strings (empty = clean).
"""

import json
from pathlib import Path
from typing import List

_DATA = Path(__file__).resolve().parent.parent / "data"


def check_adventurers() -> List[str]:
    """adventurers.json: valid class/race and resolvable kit (P-M.6)."""
    path = _DATA / "adventurers.json"
    if not path.exists():
        return []
    try:
        band = json.loads(path.read_text()).get("adventurers", [])
    except Exception as e:
        return [f"adventurers.json unparseable: {e}"]
    from characters.character_types import CharacterClass, CharacterRace
    from items.item_registry import create_item
    classes = {c.value for c in CharacterClass}
    races = {r.value for r in CharacterRace}
    recruitable = {"warrior", "ranger", "wizard", "cleric", "bard", "paladin"}
    problems: List[str] = []
    for a in band:
        aid = a.get("id", "?")
        if a.get("class") not in classes:
            problems.append(f"adventurer {aid}: bad class '{a.get('class')}'")
        elif a.get("class") not in recruitable:
            problems.append(f"adventurer {aid}: class '{a.get('class')}' "
                            f"is not recruitable — cannot join a party")
        if a.get("race") not in races:
            problems.append(f"adventurer {aid}: bad race '{a.get('race')}'")
        for iid in a.get("inventory", []):
            if create_item(iid) is None:
                problems.append(f"adventurer {aid}: unknown item '{iid}'")
    return problems


def check_guildhalls() -> List[str]:
    """guildhalls.json: unique ids, a name, and a known kind (M.7b)."""
    path = _DATA / "guildhalls.json"
    if not path.exists():
        return []
    try:
        halls = json.loads(path.read_text()).get("guildhalls", [])
    except Exception as e:
        return [f"guildhalls.json unparseable: {e}"]
    kinds = {"adventurers", "mercenaries", "mages"}
    seen = set()
    problems: List[str] = []
    for h in halls:
        hid = h.get("id", "?")
        if not h.get("id") or hid in seen:
            problems.append(f"guildhall {hid}: missing or duplicate id")
        seen.add(hid)
        if not h.get("name"):
            problems.append(f"guildhall {hid}: needs a name")
        if h.get("kind") not in kinds:
            problems.append(f"guildhall {hid}: bad kind '{h.get('kind')}'")
    return problems


def check_wildlife() -> List[str]:
    """wildlife.json: a name, terrain, and resolvable loot drops (P32.3)."""
    path = _DATA / "wildlife.json"
    if not path.exists():
        return []
    try:
        roster = json.loads(path.read_text())
    except Exception as e:
        return [f"wildlife.json unparseable: {e}"]
    from items.item_registry import create_item
    valid_terrain = {"grass", "forest", "swamp", "desert", "snow"}
    problems: List[str] = []
    for sid, spec in roster.items():
        if not spec.get("name"):
            problems.append(f"wildlife {sid}: needs a name")
        for t in spec.get("terrain", []):
            if t not in valid_terrain:
                problems.append(f"wildlife {sid}: bad terrain '{t}'")
        if not spec.get("terrain"):
            problems.append(f"wildlife {sid}: needs at least one terrain")
        for entry in spec.get("loot_table", []):
            iid = entry[0] if isinstance(entry, (list, tuple)) else entry
            if create_item(iid) is None:
                problems.append(f"wildlife {sid}: unknown drop '{iid}'")
        for prey in spec.get("preys_on", []):
            if prey not in roster:
                problems.append(f"wildlife {sid}: preys_on unknown '{prey}'")
    return problems


def check_building_styles() -> List[str]:
    """building_styles.json: a known roof shape + covering + wall (P33.3)."""
    path = _DATA / "building_styles.json"
    if not path.exists():
        return []
    try:
        styles = json.loads(path.read_text())
    except Exception as e:
        return [f"building_styles.json unparseable: {e}"]
    try:                       # material tables live with the pure renderer
        from ui.roof_shapes import COVERINGS, WALLS
    except Exception:          # headless env without pygame — skip material check
        COVERINGS, WALLS = None, None
    problems: List[str] = []
    for kind, s in styles.items():
        if s.get("roof") not in ("gable", "hip", "flat"):
            problems.append(f"building {kind}: bad roof '{s.get('roof')}'")
        if COVERINGS is not None and s.get("covering") not in COVERINGS:
            problems.append(f"building {kind}: bad covering '{s.get('covering')}'")
        if WALLS is not None and s.get("wall") not in WALLS:
            problems.append(f"building {kind}: bad wall '{s.get('wall')}'")
    return problems
