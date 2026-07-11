"""Squad & soldier model (P17.2) — the grid battle's pieces.

The tick-based battle (P17.3+) works in individuals on a grid so
you can zoom in to a real melee, but COMMANDS and MORALE live on
the SQUAD (the Total War model): one bar per body of men, not per
soldier. A `Soldier` is a light grid token; a `Squad` owns its
soldiers, an archetype (→ battle_data unit stats), a team, a
formation, a current order and objective, morale and a commander
flag. Both round-trip to dict so a battle can be saved mid-fight.

This is the STATE. The AI that moves them and the loop that ticks
them arrive in P17.3.
"""

from typing import List, Optional, Tuple

from engine.battle.battle_data import unit_stats

MORALE_START = 70
ROUT_FLOOR = 15          # below their threshold, a squad routs


class Soldier:
    """One fighter: a grid token that belongs to a squad."""

    __slots__ = ("sid", "squad_id", "team", "x", "y", "hp",
                 "max_hp", "alive", "move_accum")

    def __init__(self, sid: str, squad_id: str, team: str,
                 x: int, y: int, hp: int):
        self.sid = sid
        self.squad_id = squad_id
        self.team = team
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = hp
        self.alive = True
        # fractional movement budget (P17.4c): each marching tick adds
        # the squad's `speed`; whole tiles are spent, the remainder
        # carries — so cavalry (2.0) cover ground twice as fast as
        # foot (1.0) and a catapult (0.2) crawls one tile per 5 ticks.
        self.move_accum = 0.0

    @property
    def pos(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def hurt(self, dmg: int) -> None:
        self.hp = max(0, self.hp - max(0, dmg))
        if self.hp <= 0:
            self.alive = False

    def to_dict(self) -> dict:
        return {"sid": self.sid, "squad_id": self.squad_id,
                "team": self.team, "x": self.x, "y": self.y,
                "hp": self.hp, "max_hp": self.max_hp,
                "alive": self.alive, "move_accum": self.move_accum}

    @staticmethod
    def from_dict(d: dict) -> "Soldier":
        s = Soldier(d["sid"], d["squad_id"], d["team"], d["x"],
                    d["y"], d["max_hp"])
        s.hp = d["hp"]
        s.alive = d["alive"]
        s.move_accum = d.get("move_accum", 0.0)
        return s


class Squad:
    """A commandable body of soldiers sharing ONE morale bar."""

    def __init__(self, squad_id: str, team: str, archetype: str,
                 soldiers: List[Soldier], commander: bool = False):
        self.squad_id = squad_id
        self.team = team
        self.archetype = archetype
        self.soldiers = soldiers
        self.commander = commander
        self.morale = MORALE_START
        self.routed = False
        self.order = "hold"          # move/hold/charge/focus/fallback
        self.order_target = None     # a tile or a squad id
        self.formation = None

    # ---- construction --------------------------------------------

    @staticmethod
    def raise_squad(squad_id: str, team: str, archetype: str,
                    positions: List[Tuple[int, int]],
                    commander: bool = False) -> "Squad":
        """Muster a squad of len(positions) soldiers of one type."""
        hp = int(unit_stats(archetype).get("hp", 20))
        sq = Squad(squad_id, team, archetype, [], commander)
        for i, (x, y) in enumerate(positions):
            sq.soldiers.append(
                Soldier(f"{squad_id}_{i}", squad_id, team, x, y, hp))
        return sq

    # ---- state ---------------------------------------------------

    @property
    def stats(self) -> dict:
        return unit_stats(self.archetype)

    @property
    def category(self) -> str:
        return self.stats.get("category", "infantry")

    @property
    def speed(self) -> float:
        """Tiles per marching tick (P17.4c). Horse > foot > siege."""
        return float(self.stats.get("speed", 1.0))

    @property
    def structural_dmg(self) -> int:
        """Damage this squad deals to a wall it batters (P17.6b);
        0 for everything but siege engines (and huge creatures)."""
        return int(self.stats.get("structural_dmg", 0))

    @property
    def charge_bonus(self) -> float:
        """Momentum multiplier when this squad charges home (P17.13);
        > 1 marks a charge-capable body — horse and huge beasts."""
        return float(self.stats.get("charge_bonus", 1.0))

    @property
    def alive_soldiers(self) -> List[Soldier]:
        return [s for s in self.soldiers if s.alive]

    @property
    def strength(self) -> int:
        return len(self.alive_soldiers)

    @property
    def active(self) -> bool:
        return self.strength > 0 and not self.routed

    def centroid(self) -> Optional[Tuple[int, int]]:
        live = self.alive_soldiers
        if not live:
            return None
        return (round(sum(s.x for s in live) / len(live)),
                round(sum(s.y for s in live) / len(live)))

    def morale_threshold(self) -> int:
        return int(self.stats.get("morale_threshold", 20))

    def adjust_morale(self, delta: int) -> None:
        self.morale = max(0, min(100, self.morale + delta))
        if self.morale <= self.morale_threshold():
            self.routed = True

    def set_order(self, order: str, target=None) -> None:
        self.order = order
        self.order_target = target

    # ---- persistence ---------------------------------------------

    def to_dict(self) -> dict:
        return {
            "squad_id": self.squad_id, "team": self.team,
            "archetype": self.archetype, "commander": self.commander,
            "morale": self.morale, "routed": self.routed,
            "order": self.order, "order_target": self.order_target,
            "formation": self.formation,
            "soldiers": [s.to_dict() for s in self.soldiers],
        }

    @staticmethod
    def from_dict(d: dict) -> "Squad":
        sq = Squad(d["squad_id"], d["team"], d["archetype"],
                   [Soldier.from_dict(s) for s in d["soldiers"]],
                   d.get("commander", False))
        sq.morale = d.get("morale", MORALE_START)
        sq.routed = d.get("routed", False)
        sq.order = d.get("order", "hold")
        sq.order_target = d.get("order_target")
        sq.formation = d.get("formation")
        return sq
