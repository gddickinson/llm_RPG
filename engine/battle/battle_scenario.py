"""Battle scenarios (P17.4) — staged fields as data.

The Battle Testbed's pickable set-pieces live in
`data/battles/scenarios.json`: each names a field size, optional
wall segments, and the armies (team → squads with an archetype,
size, anchor and starting order). `build_field(id)` expands one
into a ready-to-tick `BattleField`; the screen and the headless
tests share the same builder, so what you watch is exactly what
the suite asserts.

Content-as-data: no squad numbers live in code. New set-piece =
a JSON edit + a validator pass.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from engine.battle.battle_field import BattleField
from engine.battle.battle_unit import Squad

logger = logging.getLogger("llm_rpg.battle.scenario")

_PATH = Path(__file__).resolve().parent.parent.parent / "data" / \
    "battles" / "scenarios.json"


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text())
    except Exception as e:            # pragma: no cover - data always present
        logger.warning(f"scenarios.json unreadable: {e}")
        return {}


SCENARIOS = _load()


def list_scenarios() -> List[Tuple[str, str, str]]:
    """(id, name, desc) for every scenario, in a stable order."""
    out = []
    for sid in sorted(SCENARIOS):
        sc = SCENARIOS[sid]
        out.append((sid, sc.get("name", sid), sc.get("desc", "")))
    return out


def _block(ax: int, ay: int, size: int, cols: int
           ) -> List[Tuple[int, int]]:
    """Lay `size` soldiers into `cols`-wide columns from an anchor."""
    cols = max(1, cols)
    return [(ax + (i % cols), ay + (i // cols)) for i in range(size)]


def wall_cells(entry: dict) -> List[Tuple[int, int]]:
    """The tiles a wall entry raises (explicit cells only)."""
    return [(int(x), int(y)) for x, y in entry.get("cells", [])]


def build_field(scenario_id: str) -> BattleField:
    """Expand a scenario id into a ready-to-tick BattleField."""
    sc = SCENARIOS.get(scenario_id)
    if sc is None:
        raise KeyError(f"unknown battle scenario: {scenario_id}")
    bf = BattleField(int(sc["width"]), int(sc["height"]))
    for patch in sc.get("terrain", []):     # cover/ground first
        kind = patch["kind"]
        x, y, w, h = patch["rect"]
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                bf.set_terrain(xx, yy, kind)
    for wall in sc.get("walls", []):
        kind = wall.get("type", "stone_wall")
        for (x, y) in wall_cells(wall):
            bf.add_wall(x, y, kind)
    for army in sc.get("armies", []):
        team = army["team"]
        for sq in army.get("squads", []):
            cells = _block(sq["anchor"][0], sq["anchor"][1],
                           int(sq["size"]), int(sq.get("cols", 3)))
            squad = Squad.raise_squad(sq["id"], team, sq["type"], cells)
            squad.set_order(sq.get("order", "charge"), sq.get("target"))
            bf.add_squad(squad)
    return bf


def team_strengths(field: BattleField) -> Dict[str, int]:
    return {t: sum(s.strength for s in field.squads.values()
                   if s.team == t)
            for t in field.teams()}
