"""Building interiors.

Each building location can have an Interior (mini-map) with its own
terrain grid, furniture, and NPC placements. The player "enters" by
stepping onto a building tile and pressing the interact key.

Interiors are owned by the World and keyed by location name. When the
player is inside an interior, `engine.current_interior` is set; the
renderer can switch to drawing the interior tile grid instead of the
outdoor map.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.interiors")


@dataclass
class Interior:
    """A small indoor map for a building."""
    name: str
    width: int = 8
    height: int = 6
    terrain: List[List[TerrainType]] = field(default_factory=list)
    door: Tuple[int, int] = (4, 5)        # exit tile
    npc_spots: List[Tuple[int, int]] = field(default_factory=list)
    furniture: List[Dict] = field(default_factory=list)
    description: str = ""
    # Multi-level buildings (P9A.5): linked level stack
    ground: bool = True
    stairs_up: Optional[Tuple[int, int]] = None
    stairs_down: Optional[Tuple[int, int]] = None
    level_above: Optional["Interior"] = None
    level_below: Optional["Interior"] = None

    def init_grid(self) -> None:
        """Build the wall/floor grid and cut the current door."""
        if not self.terrain:
            self.terrain = [
                [TerrainType.GRASS for _ in range(self.width)]
                for _ in range(self.height)
            ]
            for x in range(self.width):
                self.terrain[0][x] = TerrainType.BUILDING
                self.terrain[self.height - 1][x] = TerrainType.BUILDING
            for y in range(self.height):
                self.terrain[y][0] = TerrainType.BUILDING
                self.terrain[y][self.width - 1] = TerrainType.BUILDING
        self._cut_door()

    def _cut_door(self) -> None:
        dx, dy = self.door
        if 0 <= dx < self.width and 0 <= dy < self.height:
            self.terrain[dy][dx] = TerrainType.ROAD


def _make(name: str, width: int, height: int, description: str,
          door: Tuple[int, int],
          furniture: List[Dict],
          npc_spots: List[Tuple[int, int]]) -> Interior:
    inter = Interior(name=name, width=width, height=height,
                     description=description, door=door)
    inter.furniture = list(furniture)
    inter.npc_spots = list(npc_spots)
    inter.init_grid()
    return inter


def make_tavern_interior() -> Interior:
    return _make(
        name="Oakvale Tavern (interior)",
        width=10, height=7,
        description="Warm light, the smell of ale, a bard tuning a lute.",
        door=(5, 6),
        furniture=[
            {"name": "Bar", "x": 2, "y": 1},
            {"name": "Hearth", "x": 8, "y": 1},
            {"name": "Table", "x": 4, "y": 3},
            {"name": "Table", "x": 6, "y": 3},
            {"name": "Bed", "x": 8, "y": 5},
            {"name": "Barrel", "x": 1, "y": 1},
            {"name": "Stairs up", "x": 1, "y": 5},
        ],
        npc_spots=[(2, 2), (5, 3), (6, 3)],
    )


def make_forge_interior() -> Interior:
    return _make(
        name="Durgan's Forge (interior)",
        width=9, height=6,
        description="Heat from the anvil. Sparks fly with every hammer blow.",
        door=(4, 5),
        furniture=[
            {"name": "Anvil", "x": 4, "y": 2},
            {"name": "Forge", "x": 6, "y": 1},
            {"name": "Workbench", "x": 2, "y": 3},
            {"name": "Wall rack", "x": 7, "y": 3},
        ],
        npc_spots=[(4, 3)],
    )


def make_shop_interior() -> Interior:
    return _make(
        name="General Store (interior)",
        width=8, height=6,
        description="Shelves stacked with goods and curiosities.",
        door=(4, 5),
        furniture=[
            {"name": "Counter", "x": 4, "y": 1},
            {"name": "Shelves", "x": 1, "y": 1},
            {"name": "Shelves", "x": 6, "y": 1},
            {"name": "Crates", "x": 3, "y": 3},
        ],
        npc_spots=[(4, 2)],
    )


def make_temple_interior() -> Interior:
    return _make(
        name="Temple of Light (interior)",
        width=8, height=7,
        description="Sunlight streams through stained glass.",
        door=(4, 6),
        furniture=[
            {"name": "Altar", "x": 4, "y": 1},
            {"name": "Pew", "x": 2, "y": 3},
            {"name": "Pew", "x": 5, "y": 3},
            {"name": "Statue", "x": 1, "y": 2},
            {"name": "Statue", "x": 6, "y": 2},
        ],
        npc_spots=[(4, 2)],
    )


def make_default_interior(name: str) -> Interior:
    return _make(
        name=f"{name} (interior)",
        width=8, height=6,
        description="A simple interior.",
        door=(4, 5),
        furniture=[
            {"name": "Bed", "x": 1, "y": 1},
            {"name": "Hearth", "x": 6, "y": 1},
            {"name": "Chest", "x": 1, "y": 3},
            {"name": "Chair", "x": 5, "y": 3},
        ],
        npc_spots=[],
    )


def make_from_blueprint(loc_name: str, bp) -> Interior:
    """Build an Interior from a Blueprint grid.

    Maps blueprint cells (W/F/D/T/B/A/C/P/R/S) to terrain + furniture.
    """
    name = f"{loc_name} (interior)"
    w, h = bp.width, bp.height
    inter = Interior(name=name, width=w, height=h,
                     description=bp.description)
    # Pre-fill terrain
    inter.terrain = [[TerrainType.GRASS for _ in range(w)] for _ in range(h)]
    door_pos = None
    for y in range(h):
        for x in range(w):
            cell = bp.cell(x, y)
            if cell == "W":
                inter.terrain[y][x] = TerrainType.BUILDING
            elif cell == "D":
                inter.terrain[y][x] = TerrainType.ROAD
                door_pos = (x, y)
            elif cell in ("F", "."):
                pass  # grass / floor
            else:
                # Furniture: keep cell walkable (interior floor) but record
                # the furniture object.
                inter.terrain[y][x] = TerrainType.GRASS
                cell_name_map = {
                    "T": "Table", "B": "Bed", "A": "Anvil",
                    "C": "Chest", "P": "Hearth", "R": "Barrel",
                    "S": "Altar",
                }
                if getattr(bp, "kind", "") == "library":
                    cell_name_map["R"] = "Shelves"
                inter.furniture.append({
                    "name": cell_name_map.get(cell, "Furniture"),
                    "x": x, "y": y,
                })
    if door_pos is None:
        door_pos = (w // 2, h - 1)
        if 0 <= door_pos[1] < h:
            inter.terrain[door_pos[1]][door_pos[0]] = TerrainType.ROAD
    inter.door = door_pos
    # NPC spot near the center (off-furniture)
    spot = (w // 2, h // 2)
    inter.npc_spots = [spot]
    return inter


def _free_tiles(inter: Interior) -> List[Tuple[int, int]]:
    """Inner floor tiles with no wall, door, or furniture on them."""
    taken = {(f.get("x"), f.get("y")) for f in inter.furniture}
    taken.add(inter.door)
    out = []
    for y in range(1, inter.height - 1):
        for x in range(1, inter.width - 1):
            if inter.terrain[y][x] == TerrainType.BUILDING:
                continue
            if (x, y) in taken:
                continue
            out.append((x, y))
    return out


def add_upper_floor(inter: Interior) -> Optional[Interior]:
    """Bedrooms above the taproom (P9A.5). Clean transitions: the
    stair tile on each level carries you to its twin on the other."""
    free = _free_tiles(inter)
    if not free:
        return None
    spot = free[-1]                      # a corner, away from the door
    loft = Interior(name=f"{inter.name} — upstairs",
                    width=inter.width, height=inter.height,
                    door=spot, ground=False,
                    description="Creaking boards, low beams, and the "
                                "quiet of the bedrooms.")
    loft.init_grid()
    loft.stairs_down = spot
    loft.furniture.append({"name": "Stairs down",
                           "x": spot[0], "y": spot[1]})
    beds = [t for t in _free_tiles(loft) if t != spot][:3]
    for i, (bx, by) in enumerate(beds):
        loft.furniture.append(
            {"name": "Bed" if i < 2 else "Chest", "x": bx, "y": by})
    inter.stairs_up = spot
    inter.furniture.append({"name": "Stairs up",
                            "x": spot[0], "y": spot[1]})
    inter.level_above = loft
    loft.level_below = inter
    return loft


def add_cellar(inter: Interior) -> Optional[Interior]:
    """Storage below the shop floor (P9A.5)."""
    free = _free_tiles(inter)
    if not free:
        return None
    spot = free[0]
    cellar = Interior(name=f"{inter.name} — cellar",
                      width=inter.width, height=inter.height,
                      door=spot, ground=False,
                      description="Cool dark air, dust, and stacked "
                                  "stores.")
    cellar.init_grid()
    cellar.stairs_up = spot
    cellar.furniture.append({"name": "Stairs up",
                             "x": spot[0], "y": spot[1]})
    stock = [t for t in _free_tiles(cellar) if t != spot][:3]
    for i, (bx, by) in enumerate(stock):
        cellar.furniture.append(
            {"name": "Barrel" if i < 2 else "Chest",
             "x": bx, "y": by})
    inter.stairs_down = spot
    inter.furniture.append({"name": "Stairs down",
                            "x": spot[0], "y": spot[1]})
    inter.level_below = cellar
    cellar.level_above = inter
    return cellar


def build_interiors_for_world(world) -> Dict[str, Interior]:
    """Create matching interiors for each building in the world.

    Tries the blueprint library first; falls back to the old factory set.
    """
    try:
        from world.blueprints import blueprint_for_location
    except Exception:
        blueprint_for_location = None

    interiors: Dict[str, Interior] = {}
    for loc in world.locations:
        ltype = loc.get_property("type", "")
        name_l = loc.name.lower()
        inter = None

        # Try blueprint first
        if blueprint_for_location is not None:
            bp = blueprint_for_location(loc.name)
            if bp is not None:
                inter = make_from_blueprint(loc.name, bp)

        # Fallback to hand-built interior factories
        if inter is None:
            if "tavern" in name_l:
                inter = make_tavern_interior()
            elif "forge" in name_l or "smith" in name_l:
                inter = make_forge_interior()
            elif "store" in name_l or "shop" in name_l:
                inter = make_shop_interior()
            elif "temple" in name_l or "shrine" in name_l:
                inter = make_temple_interior()
            elif ltype in ("tavern", "shop", "temple", "forge"):
                inter = make_default_interior(loc.name)
            else:
                continue

        interiors[loc.name] = inter

    # Multi-level pass (P9A.5): bedrooms above taverns and inns,
    # storage cellars below shops and forges
    for name, inter in interiors.items():
        low = name.lower()
        try:
            if "tavern" in low or "inn" in low:
                add_upper_floor(inter)
            elif any(k in low for k in ("store", "goods", "shop",
                                        "smithy", "forge")):
                add_cellar(inter)
        except Exception as e:
            logger.debug(f"level stack for {name}: {e}")
    return interiors
