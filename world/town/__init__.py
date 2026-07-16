"""world.town — the large-town generator (OAKVALE project).

A reusable procedural TOWN builder adapted from `autonomous_world`'s settlement
pipeline onto llm_RPG's tile-grid + `Location`/`Character` model. See
`docs/OAKVALE.md` for the design + phased plan.

Contents (built incrementally):
- `wards`     — T1 Voronoi DISTRICTS: sunflower seeds → nearest-seed wards →
                Lloyd relaxation → ring classification (inner civic/market,
                middle residential/craft, outer suburbs). `plan_districts`.
- `streets`   — T2 street network templates (planned).
- `town_wall` — T3 defended-core wall + gates (planned).
- `lots`      — T4 building-lot placement (planned).
- `town_gen`  — orchestrator (planned).
- `population`— T6 role NPCs (planned).
"""

from world.town.wards import DistrictPlan, plan_districts

__all__ = ["DistrictPlan", "plan_districts"]
