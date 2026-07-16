"""OAKVALE T4 — the TOWN GENERATOR orchestrator.

`plan_town(cx, cy, radius, size, seed)` runs the whole reusable pipeline —
districts (T1) → streets (T2) → defended-core wall (T3) → building lots (T4) —
and returns a `TownPlan`: the districts, the street network, the core wall +
gates + towers, and the building lots (each a future `Location`). Pure and
deterministic in `seed`; the T5 integration `stamp`s a `TownPlan` onto the real
world map (streets→ROAD, wall→WALL, gates→ROAD, lots→BUILDING + `Location`),
then wires interiors/fortify/population. Reusable for Oakvale and any future
town.
"""

from world.town.lots import district_counts, place_lots
from world.town.streets import plan_streets
from world.town.town_wall import build_core_wall
from world.town.wards import plan_districts


class TownPlan:
    def __init__(self, cx, cy, radius, size, districts, streets, wall, lots):
        self.cx, self.cy, self.radius, self.size = cx, cy, radius, size
        self.districts = districts      # DistrictPlan (T1)
        self.streets = streets          # StreetPlan (T2)
        self.wall = wall                # CoreWall (T3)
        self.lots = lots                # [BuildingLot] (T4)

    def building_count(self) -> int:
        return len(self.lots)

    def kind_counts(self):
        return district_counts(self.lots)

    def lots_of_kind(self, kind):
        return [lot for lot in self.lots if lot.kind == kind]

    def core_lots(self):
        """Building lots that fall INSIDE the defended wall (the core)."""
        return [lot for lot in self.lots
                if self.wall.encloses(*lot.center())]

    def gates(self):
        return list(self.wall.gates)


def plan_town(cx: float, cy: float, radius: float, size: str = "town",
              seed: int = 0, wall_frac: float = 0.5) -> TownPlan:
    """Plan a whole town (districts + streets + wall + lots). Deterministic."""
    districts = plan_districts(cx, cy, radius, seed=seed, size=size)
    streets = plan_streets(cx, cy, radius, size=size, seed=seed)
    wall = build_core_wall(cx, cy, radius, streets, frac=wall_frac, seed=seed)
    lots = place_lots(districts, streets, wall, seed=seed)
    return TownPlan(cx, cy, radius, size, districts, streets, wall, lots)
