"""Battle session (P17.3) — the tick loop over the grid.

Drives the group AI: each tick recomputes one flow field per team
(toward the enemy centroids), updates every squad's morale and
rout, then moves and fights each soldier (focus-fire target, attack
if in reach else step the flow field). Deterministic with a seeded
rng; terminates when one side has no active squads or `max_ticks`
is hit. `run_headless` returns a result dict — the same shape as
the P17.1 auto-resolver, so callers can treat a ticked battle and
an auto-resolved one alike.

RTWP/turn-step and the zoomable view come in P17.4; this is the
pure simulation.
"""

import random
from typing import Dict, List, Tuple

from engine.battle import battle_ai as ai
from engine.battle.battle_flow import distance_field


class BattleSession:
    def __init__(self, field, seed: int = 0):
        self.field = field
        self.rng = random.Random(seed)
        self.tick_count = 0
        # ranged shots fired THIS tick, for the screen to draw as
        # tracers: (x0, y0, x1, y1). Refreshed every tick; the sim
        # never reads them, so they don't touch determinism.
        self.tracers = []

    # ------------------------------------------------------- flow

    def _team_targets(self, team: str) -> List[Tuple[int, int]]:
        """The enemy centroids a team advances toward."""
        out = []
        for sq in self.field.squads.values():
            if sq.team != team and sq.active:
                c = sq.centroid()
                if c is not None:
                    out.append(c)
        return out

    def _flows(self) -> Dict[str, dict]:
        return {team: distance_field(self.field,
                                     self._team_targets(team))
                for team in self.field.teams()}

    # ------------------------------------------------------- tick

    def tick(self) -> None:
        self.tick_count += 1
        field = self.field
        flows = self._flows()
        self.tracers = []

        for sq in field.squads.values():
            ai.update_morale(field, sq)

        # deterministic soldier order: by squad id then soldier id
        soldiers = []
        for sq in sorted(field.squads.values(),
                         key=lambda s: s.squad_id):
            if not sq.active:
                continue
            for sol in sorted(sq.alive_soldiers, key=lambda s: s.sid):
                soldiers.append((sol, sq))

        for sol, sq in soldiers:
            if not sol.alive or sq.routed:
                if sq.routed:
                    self._flee(sol, sq, flows)
                continue
            target = ai.pick_target(field, sol, sq)
            if target is None:
                continue
            d = ai._dist(sol.pos, target.pos)
            if d <= ai.reach_of(sq):
                if d > ai.MELEE_REACH and sq.stats.get("ranged", 0) > 0:
                    self.tracers.append((sol.x, sol.y,
                                         target.x, target.y))
                ai.attack(field, sol, sq, target, self.rng)
            else:
                goal = ai.role_goal(field, sol, sq,
                                    flows.get(sq.team, {}))
                if goal is not None:
                    field.move_soldier(sol, *goal)

    def _flee(self, sol, sq, flows) -> None:
        """A routed squad's men run from the nearest enemy."""
        field = self.field
        target = ai.pick_target(field, sol, sq)
        if target is None:
            return
        dx = (sol.x > target.x) - (sol.x < target.x)
        dy = (sol.y > target.y) - (sol.y < target.y)
        field.move_soldier(sol, sol.x + dx, sol.y + dy)

    # ---------------------------------------------------- outcome

    def over(self) -> bool:
        live = [t for t in self.field.teams()
                if self.field.team_active(t)]
        return len(live) <= 1

    def result(self) -> dict:
        live = [t for t in self.field.teams()
                if self.field.team_active(t)]
        survivors = {t: sum(sq.strength
                            for sq in self.field.squads.values()
                            if sq.team == t)
                     for t in self.field.teams()}
        return {
            "winner": live[0] if len(live) == 1 else None,
            "ticks": self.tick_count,
            "survivors": survivors,
        }

    def run_headless(self, max_ticks: int = 300) -> dict:
        while not self.over() and self.tick_count < max_ticks:
            self.tick()
        return self.result()
