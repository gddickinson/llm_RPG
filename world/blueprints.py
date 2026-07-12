"""Building blueprints.

Adapted from autonomous_world/game/world/buildings.py + blueprint_library.py,
condensed for our smaller buildings.

A Blueprint is a 2D grid of cell types (str codes) plus metadata. Cell
codes:
    'W' = wall
    'F' = floor (walkable)
    'D' = door (walkable, marks entrance)
    'T' = table
    'B' = bed
    'A' = anvil / workbench
    'C' = chest
    'P' = fireplace / hearth
    'R' = barrel / shelves
    'S' = altar / shrine
    '.' = exterior (skip / grass)

Each preset blueprint is a small fixed layout (typically 6×6 to 10×8).
The interior system can use these to furnish building interiors.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.blueprints")


@dataclass
class Blueprint:
    """A building floor plan."""
    name: str
    kind: str                    # tavern / forge / shop / temple / inn / camp / chapel
    grid: List[List[str]] = field(default_factory=list)
    description: str = ""
    npc_class: str = ""
    npc_count: int = 1

    @property
    def width(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    @property
    def height(self) -> int:
        return len(self.grid)

    def cell(self, x: int, y: int) -> str:
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.grid[y][x]
        return "."

    def door_positions(self) -> List[Tuple[int, int]]:
        return [(x, y) for y, row in enumerate(self.grid)
                for x, c in enumerate(row) if c == "D"]

    def floor_positions(self) -> List[Tuple[int, int]]:
        return [(x, y) for y, row in enumerate(self.grid)
                for x, c in enumerate(row) if c == "F"]

    def furniture(self) -> List[Tuple[str, int, int]]:
        """All non-wall, non-floor cells (i.e. the furnishings)."""
        return [(c, x, y) for y, row in enumerate(self.grid)
                for x, c in enumerate(row)
                if c not in ("W", "F", "D", ".")]

    def rotated(self) -> "Blueprint":
        """Return a 90° clockwise rotated blueprint."""
        if not self.grid:
            return Blueprint(name=self.name, kind=self.kind, grid=[])
        w, h = self.width, self.height
        new = [["." for _ in range(h)] for _ in range(w)]
        for y in range(h):
            for x in range(w):
                new[x][h - 1 - y] = self.grid[y][x]
        return Blueprint(
            name=self.name, kind=self.kind, grid=new,
            description=self.description,
            npc_class=self.npc_class, npc_count=self.npc_count,
        )


# ---------------------------------------------------------------------- presets

# Shorthand: each row is a string of cell codes.
def _g(*rows: str) -> List[List[str]]:
    return [list(r) for r in rows]


SMALL_TAVERN = Blueprint(
    name="Tavern",
    kind="tavern",
    description="A cozy tavern with a hearth and benches.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WPFFFFTW",
        "WFFFFFFW",
        "WFFTFFRW",
        "WRFFFFTW",
        "WFFFFFFW",
        "WFFFFFFW",
        "WWWDWWWW",
    ),
)


SMALL_FORGE = Blueprint(
    name="Forge",
    kind="forge",
    description="Heat from the anvil. Sparks fly with every hammer blow.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WPRFFFFW",
        "WFFFAFFW",
        "WFFFFFFW",
        "WFFFFFFW",
        "WFFFRRRW",
        "WWWDWWWW",
    ),
)


GENERAL_STORE = Blueprint(
    name="Shop",
    kind="shop",
    description="Shelves stacked with goods and curiosities.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WRFFFFRW",
        "WFFFTFFW",
        "WFFFFFFW",
        "WFFCFFFW",
        "WRFFFFRW",
        "WWWDWWWW",
    ),
)


TEMPLE_OF_LIGHT = Blueprint(
    name="Temple",
    kind="temple",
    description="Sunlight streams through stained glass.",
    npc_class="cleric", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WFFSFFFW",
        "WFFFFFFW",
        "WFTFFTFW",
        "WFFFFFFW",
        "WFTFFTFW",
        "WFFFFFFW",
        "WWWDWWWW",
    ),
)


RIVERSIDE_INN = Blueprint(
    name="Inn",
    kind="inn",
    description="Warm light, the smell of fresh bread.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WBFFFFTW",
        "WFFFFFFW",
        "WFFFRFFW",
        "WFFTFFBW",
        "WFFFFFFW",
        "WWWDWWWW",
    ),
)


HAMLET_CHAPEL = Blueprint(
    name="Chapel",
    kind="temple",
    description="A modest chapel of the Light.",
    npc_class="cleric", npc_count=1,
    grid=_g(
        "WWWWWW",
        "WFSFFW",
        "WFFFFW",
        "WFTFFW",
        "WFFFFW",
        "WWDWWW",
    ),
)


WHEELWRIGHT_SHOP = Blueprint(
    name="Wheelwright",
    kind="shop",
    description="A shop full of axles and yokes.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWW",
        "WRFFFFRW",
        "WFFAFFFW",
        "WFFFFFFW",
        "WFFFTFFW",
        "WRFFFFRW",
        "WWWDWWWW",
    ),
)


FOREMANS_HALL = Blueprint(
    name="Foreman's Hall",
    kind="hall",
    description="A long log hall where the foreman keeps the ledgers.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWWWWW",
        "WPFFFFFTRW",
        "WFFFFFFFFW",
        "WFFFTFFFCW",
        "WFFFFFFFFW",
        "WRFFFFFFFW",
        "WWWWDWWWWW",
    ),
)


STONEPINE_SMITHY = Blueprint(
    name="Stonepine Smithy",
    kind="forge",
    description="A small forge for repairing picks and saws.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWW",
        "WPFFRRW",
        "WFFAFRW",
        "WFFFFFW",
        "WRFFFFW",
        "WWWDWWW",
    ),
)


CAMP_TAVERN = Blueprint(
    name="Camp Tavern",
    kind="tavern",
    description="Rough-hewn benches, a barrel of strong ale.",
    npc_class="merchant", npc_count=1,
    grid=_g(
        "WWWWWWW",
        "WPFFTRW",
        "WFFFFFW",
        "WFTFFRW",
        "WRFFFFW",
        "WWWDWWW",
    ),
)


WATCHTOWER = Blueprint(
    name="Watchtower", kind="watchtower",
    description="A tall stone tower from which guards scan the road.",
    npc_class="guard", npc_count=1,
    grid=_g("WWWWW", "WCFFW", "WFFFW", "WFFFW", "WFFRW", "WWDWW"),
)

SMALL_FARMHOUSE = Blueprint(
    name="Farmhouse", kind="farmhouse",
    description="A modest farmhouse with a curl of chimney smoke.",
    npc_class="villager", npc_count=2,
    grid=_g("WWWWWWW", "WPFFFBW", "WFFTFFW", "WFFFFFW",
            "WFFBFFW", "WWWDWWW"),
)

STABLE = Blueprint(
    name="Stable", kind="stable",
    description="The warm scent of hay and horses.",
    npc_class="villager", npc_count=1,
    grid=_g("WWWWWWWW", "WFFRFFFW", "WFFFFFFW",
            "WFFFFFRW", "WFFFFFFW", "WWWDWWWW"),
)

LIBRARY = Blueprint(
    name="Library", kind="library",
    description="Shelves of books reach the ceiling.",
    npc_class="wizard", npc_count=1,
    grid=_g("WWWWWWWW", "WRRFFFRW", "WFFFTFFW",
            "WFFFFFFW", "WFFCFFFW", "WRFFFFRW", "WWWDWWWW"),
)

MARKET_STALL = Blueprint(
    name="Market Stall", kind="stall",
    description="A canvas stall heaped with vegetables and pots.",
    npc_class="merchant", npc_count=1,
    grid=_g("WWWWWW", "WTRRTW", "WFFFFW", "WWDWWW"),
)

WELL_HOUSE = Blueprint(
    name="Well", kind="well",
    description="A round stone well — the village's water.",
    grid=_g("WWWW", "WSSW", "WSSW", "WWDW"),
)

WIZARD_TOWER = Blueprint(
    name="Wizard's Tower", kind="tower",
    description="A slender tower with a faint blue glow at its peak.",
    npc_class="wizard", npc_count=1,
    grid=_g("WWWWW", "WSFCW", "WFFFW", "WFTFW", "WFFRW", "WWDWW"),
)

HUNTERS_LODGE = Blueprint(
    name="Hunter's Lodge", kind="lodge",
    description="Trophies on the walls; the scent of pine.",
    npc_class="ranger", npc_count=1,
    grid=_g("WWWWWW", "WPFFTW", "WFFFFW", "WFBFRW", "WWWDWW"),
)

ROADSIDE_SHRINE = Blueprint(
    name="Wayside Shrine", kind="shrine",
    description="A small wayside shrine. Lichen creeps over the stone.",
    grid=_g("WWWW", "WSFW", "WFFW", "WWDW"),
)


BLUEPRINT_LIBRARY: Dict[str, Blueprint] = {
    "tavern": SMALL_TAVERN,
    "forge": SMALL_FORGE,
    "shop": GENERAL_STORE,
    "temple": TEMPLE_OF_LIGHT,
    "inn": RIVERSIDE_INN,
    "chapel": HAMLET_CHAPEL,
    "wheelwright": WHEELWRIGHT_SHOP,
    "hall": FOREMANS_HALL,
    "smithy": STONEPINE_SMITHY,
    "camp_tavern": CAMP_TAVERN,
    "watchtower": WATCHTOWER,
    "farmhouse": SMALL_FARMHOUSE,
    "stable": STABLE,
    "library": LIBRARY,
    "stall": MARKET_STALL,
    "well": WELL_HOUSE,
    "tower": WIZARD_TOWER,
    "lodge": HUNTERS_LODGE,
    "shrine": ROADSIDE_SHRINE,
}


# Map a free-form location name -> blueprint key
def blueprint_for_location(loc_name: str) -> Optional[Blueprint]:
    name = (loc_name or "").lower()
    keywords = (
        ("oakvale tavern", "tavern"),
        ("camp tavern", "camp_tavern"),
        ("riverside inn", "inn"),
        ("hamlet chapel", "chapel"),
        ("foreman", "hall"),
        ("stonepine smithy", "smithy"),
        ("wheelwright", "wheelwright"),
        ("watchtower", "watchtower"),
        ("farmhouse", "farmhouse"),
        ("cottage", "farmhouse"),
        ("stable", "stable"),
        ("library", "library"),
        ("market", "stall"),
        ("stall", "stall"),
        ("well", "well"),
        ("wizard", "tower"),
        ("tower", "tower"),
        ("lodge", "lodge"),
        ("hunter", "lodge"),
        ("wayside", "shrine"),
        ("tavern", "tavern"),
        ("forge", "forge"),
        ("smith", "forge"),
        ("temple", "temple"),
        ("store", "shop"),
        ("shop", "shop"),
        ("chapel", "chapel"),
        ("shrine", "shrine"),
        ("inn", "inn"),
    )
    for keyword, key in keywords:
        if keyword in name:
            return BLUEPRINT_LIBRARY.get(key)
    return None


# Helpful: cell type -> human-readable furniture name
CELL_NAME = {
    "T": "Table",
    "B": "Bed",
    "A": "Anvil / Workbench",
    "C": "Chest",
    "P": "Hearth",
    "R": "Barrel / Shelves",
    "S": "Altar",
}
