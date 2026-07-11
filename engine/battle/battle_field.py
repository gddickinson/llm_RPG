"""Battle field (P17.2) — the grid a battle is fought on.

A self-contained tile grid (independent of the world map) with the
pieces a battle needs: terrain per tile, WALL/GATE structures as HP
objects that break into RUBBLE breaches (reusing the P10.2 damage
model's semantics without importing the world engine), soldier
occupancy for pathing/collision, and a squad registry. The
tick loop (P17.3) and the renderer (P17.4) read this; the resolver
(P17.1) is the abstract sibling used off-screen.

Kept deliberately small and dependency-light so it is trivially
testable headless.
"""

from typing import Dict, List, Optional, Tuple

from engine.battle.battle_data import fort_stats, terrain_cover
from engine.battle.battle_unit import Squad

# terrain kinds a battle field understands (strings, not the world
# TerrainType enum — a battle is its own arena). forest/hedge/sandbags
# are passable COVER terrains (P17.6): you fight from them, they blunt
# incoming ranged fire.
PASSABLE = ("grass", "road", "rubble", "scorched", "mud",
            "forest", "hedge", "sandbags")
WALL = "wall"
GATE = "gate"
BLOCKING = ("wall", "gate", "water", "mountain")


class BattleField:
    def __init__(self, width: int, height: int,
                 default: str = "grass"):
        self.width = width
        self.height = height
        self.terrain = [[default for _ in range(width)]
                        for _ in range(height)]
        self.struct_hp: Dict[Tuple[int, int], int] = {}
        self.struct_kind: Dict[Tuple[int, int], str] = {}
        self.squads: Dict[str, Squad] = {}
        self._occupied: Dict[Tuple[int, int], str] = {}   # pos->sid
        # capture points (P17.6c): each is a dict with id/tile/radius/
        # hold and mutable holder/hold_count/captured_by.
        self.objectives: List[dict] = []

    # ---- terrain / structures ------------------------------------

    def set_terrain(self, x: int, y: int, kind: str) -> None:
        if self.in_bounds(x, y):
            self.terrain[y][x] = kind

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def add_wall(self, x: int, y: int, fort_type: str = "stone_wall"
                 ) -> None:
        """Raise a wall/gate segment as an HP structure."""
        if not self.in_bounds(x, y):
            return
        self.terrain[y][x] = GATE if "gate" in fort_type else WALL
        self.struct_hp[(x, y)] = int(fort_stats(fort_type)["hp"])
        self.struct_kind[(x, y)] = fort_type

    def damage_struct(self, x: int, y: int, dmg: float) -> bool:
        """Batter a wall/gate. Returns True on the breach."""
        if (x, y) not in self.struct_hp:
            return False
        self.struct_hp[(x, y)] = max(
            0, self.struct_hp[(x, y)] - int(dmg))
        if self.struct_hp[(x, y)] <= 0:
            self.struct_hp.pop((x, y), None)
            self.struct_kind.pop((x, y), None)
            self.terrain[y][x] = "rubble"     # a breach = a lane
            return True
        return False

    def is_blocking(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        return self.terrain[y][x] in BLOCKING

    def cover_at(self, x: int, y: int) -> float:
        """Cover (0..1) for a soldier standing here (P17.6)."""
        if not self.in_bounds(x, y):
            return 0.0
        return terrain_cover(self.terrain[y][x])

    # ---- occupancy -----------------------------------------------

    def passable(self, x: int, y: int) -> bool:
        return (self.in_bounds(x, y) and
                not self.is_blocking(x, y) and
                (x, y) not in self._occupied)

    def place(self, soldier) -> bool:
        if soldier.pos in self._occupied:
            return False
        self._occupied[soldier.pos] = soldier.sid
        return True

    def move_soldier(self, soldier, nx: int, ny: int) -> bool:
        if not self.passable(nx, ny):
            return False
        self._occupied.pop(soldier.pos, None)
        soldier.x, soldier.y = nx, ny
        self._occupied[(nx, ny)] = soldier.sid
        return True

    def vacate(self, soldier) -> None:
        if self._occupied.get(soldier.pos) == soldier.sid:
            self._occupied.pop(soldier.pos, None)

    def soldier_at(self, x: int, y: int) -> Optional[str]:
        return self._occupied.get((x, y))

    # ---- squads --------------------------------------------------

    def add_squad(self, squad: Squad) -> None:
        self.squads[squad.squad_id] = squad
        for s in squad.alive_soldiers:
            self.place(s)

    def teams(self) -> List[str]:
        return sorted({sq.team for sq in self.squads.values()})

    def team_active(self, team: str) -> bool:
        return any(sq.active for sq in self.squads.values()
                   if sq.team == team)

    def enemies_of(self, team: str) -> List[Squad]:
        return [sq for sq in self.squads.values()
                if sq.team != team and sq.active]

    # ---- capture points ------------------------------------------

    def add_objective(self, oid: str, tile, radius: int = 2,
                      hold: int = 20) -> None:
        self.objectives.append({
            "id": oid, "tile": [int(tile[0]), int(tile[1])],
            "radius": int(radius), "hold": int(hold),
            "holder": None, "hold_count": 0, "captured_by": None,
        })

    def team_counts_near(self, tile, radius: int) -> Dict[str, int]:
        """Living soldiers of each team within `radius` of a tile
        (Chebyshev) — who is contesting a capture point."""
        tx, ty = tile
        counts: Dict[str, int] = {}
        for sq in self.squads.values():
            n = sum(1 for s in sq.alive_soldiers
                    if max(abs(s.x - tx), abs(s.y - ty)) <= radius)
            if n:
                counts[sq.team] = counts.get(sq.team, 0) + n
        return counts

    def captured_team(self):
        """The team that has fully seized a capture point, or None."""
        for o in self.objectives:
            if o.get("captured_by"):
                return o["captured_by"]
        return None

    # ---- persistence ---------------------------------------------

    def to_dict(self) -> dict:
        return {
            "width": self.width, "height": self.height,
            "terrain": self.terrain,
            "struct_hp": [[x, y, hp] for (x, y), hp in
                          self.struct_hp.items()],
            "struct_kind": [[x, y, k] for (x, y), k in
                            self.struct_kind.items()],
            "squads": [sq.to_dict() for sq in self.squads.values()],
            "objectives": self.objectives,
        }

    @staticmethod
    def from_dict(d: dict) -> "BattleField":
        bf = BattleField(d["width"], d["height"])
        bf.terrain = d["terrain"]
        bf.struct_hp = {(x, y): hp for x, y, hp in
                        d.get("struct_hp", [])}
        bf.struct_kind = {(x, y): k for x, y, k in
                          d.get("struct_kind", [])}
        for sd in d.get("squads", []):
            bf.add_squad(Squad.from_dict(sd))
        bf.objectives = d.get("objectives", [])
        return bf
