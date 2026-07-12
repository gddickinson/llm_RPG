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
