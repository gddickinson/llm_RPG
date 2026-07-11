"""Battle-content validators (split from data_validate.py, P17.4).

Cross-reference checks for the Phase 17 battle layer: the unit /
formation / fortification / matchup tables (P17.1) and the staged
testbed scenarios (P17.4). Kept in their own module so the main
validator stays under the file-size line.
"""

from typing import List


def check_battles() -> List[str]:
    """battle tables: units have a category + core stats; formations
    and fortifications well-formed; matchup keys reference known
    categories. Then the staged scenarios."""
    from engine.battle.battle_data import (FORMATIONS, FORTIFICATIONS,
                                           MATCHUP, TERRAIN, UNITS)
    out = []
    for uid, st in UNITS.items():
        if "category" not in st:
            out.append(f"battle unit {uid}: missing category")
        for field in ("melee", "ranged", "defense", "hp"):
            if field not in st:
                out.append(f"battle unit {uid}: missing {field}")
    for key in MATCHUP:
        if "|" not in key:
            out.append(f"battle matchup '{key}': need 'atk|def'")
    for fid, st in FORTIFICATIONS.items():
        if "hp" not in st:
            out.append(f"fortification {fid}: missing hp")
    for fname, spec in FORMATIONS.items():
        if "defense_mult" not in spec or "attack_mult" not in spec:
            out.append(f"formation {fname}: needs def/atk mults")
    if not TERRAIN:
        out.append("battle terrain modifiers missing")
    from engine.battle.battle_data import TERRAIN_COVER
    for kind, cov in TERRAIN_COVER.items():
        if not (0.0 <= cov <= 1.0):
            out.append(f"battle terrain {kind}: cover {cov} not in 0..1")
    out += _check_scenarios(set(UNITS), set(TERRAIN_COVER))
    return out


def _check_scenarios(unit_types: set, terrain_kinds: set) -> List[str]:
    """scenarios.json: fields sized, squads use known archetypes, ids
    unique, orders target real squads, all pieces inside the field."""
    from engine.battle.battle_scenario import SCENARIOS, wall_cells
    out = []
    for sid, sc in SCENARIOS.items():
        w, h = sc.get("width"), sc.get("height")
        if not (isinstance(w, int) and isinstance(h, int)
                and w > 0 and h > 0):
            out.append(f"battle scenario {sid}: bad width/height")
            continue

        def _oob(x, y):
            return not (0 <= x < w and 0 <= y < h)
        for patch in sc.get("terrain", []):
            if patch.get("kind") not in terrain_kinds:
                out.append(f"scenario {sid}: terrain kind "
                           f"'{patch.get('kind')}' unknown")
            rect = patch.get("rect")
            if not (isinstance(rect, list) and len(rect) == 4):
                out.append(f"scenario {sid}: terrain rect malformed")
            elif _oob(rect[0], rect[1]) or \
                    _oob(rect[0] + rect[2] - 1, rect[1] + rect[3] - 1):
                out.append(f"scenario {sid}: terrain rect off-field")
        for wall in sc.get("walls", []):
            for (x, y) in wall_cells(wall):
                if _oob(x, y):
                    out.append(f"scenario {sid}: wall cell "
                               f"({x},{y}) out of bounds")
        ids = set()
        for army in sc.get("armies", []):
            if not army.get("team"):
                out.append(f"scenario {sid}: army missing team")
            for sq in army.get("squads", []):
                qid = sq.get("id")
                if not qid or qid in ids:
                    out.append(f"scenario {sid}: squad id "
                               f"'{qid}' missing or duplicate")
                ids.add(qid)
                if sq.get("type") not in unit_types:
                    out.append(f"scenario {sid}: squad {qid} unknown "
                               f"unit '{sq.get('type')}'")
                if not (isinstance(sq.get("size"), int)
                        and sq["size"] > 0):
                    out.append(f"scenario {sid}: squad {qid} bad size")
                ax, ay = sq.get("anchor", [None, None])
                if not (isinstance(ax, int) and isinstance(ay, int)) \
                        or _oob(ax, ay):
                    out.append(f"scenario {sid}: squad {qid} anchor "
                               f"off-field")
        # second pass: order targets must name a squad in the scenario
        for army in sc.get("armies", []):
            for sq in army.get("squads", []):
                tgt = sq.get("target")
                if tgt and tgt not in ids:
                    out.append(f"scenario {sid}: squad {sq.get('id')} "
                               f"targets unknown squad '{tgt}'")
    return out
