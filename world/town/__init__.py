"""world.town — the large-town generator (OAKVALE project).

A reusable procedural TOWN builder adapted from `autonomous_world`'s settlement
pipeline onto llm_RPG's tile-grid + `Location`/`Character` model. See
`docs/OAKVALE.md` for the design + phased plan.

Contents (built incrementally):
- `wards`     — T1 Voronoi DISTRICTS: sunflower seeds → nearest-seed wards →
                Lloyd relaxation → ring classification (inner civic/market,
                middle residential/craft, outer suburbs). `plan_districts`.
- `streets`   — T2 STREET network: size-scaled templates (boulevards + ring +
                radial lanes + core grid + central market square). `plan_streets`.
- `town_wall` — T3 DEFENDED CORE: a wall polygon round the inner districts with
                gates where the boulevards cross it + towers. `build_core_wall`.
- `lots`      — T4 BUILDING LOTS: landmarks → street frontage → interior fill,
                each a `BuildingLot` keyed to its district. `place_lots`.
- `town_gen`  — T4 orchestrator: `plan_town` → a `TownPlan` (districts + streets
                + wall + lots). The T5 integration stamps it onto the world.
- `population`— T6 role NPCs (planned).
"""

from world.town.wards import DistrictPlan, plan_districts
from world.town.streets import StreetPlan, plan_streets
from world.town.town_wall import CoreWall, build_core_wall
from world.town.lots import BuildingLot, place_lots
from world.town.town_gen import TownPlan, plan_town
from world.town.stamp import stamp_town

__all__ = ["DistrictPlan", "plan_districts", "StreetPlan", "plan_streets",
           "CoreWall", "build_core_wall", "BuildingLot", "place_lots",
           "TownPlan", "plan_town", "stamp_town"]
