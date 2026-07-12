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
from engine.battle import battle_facing as facing
from engine.battle import battle_orders as orders
from engine.battle.battle_flow import distance_field

MAX_STEPS = 3            # tiles a soldier may cover in one tick (cap)
SIEGE_RANGE = 10         # tiles a bombard-capable engine lobs at a wall


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

        from engine.battle import battle_doctrine as doctrine
        for sq in field.squads.values():
            ai.update_morale(field, sq)
            doctrine.apply(field, sq)      # P17.19 commander instincts

        # deterministic soldier order: by squad id then soldier id.
        # Routed-but-alive squads stay in the list so they keep FLEEING
        # every tick (and horse-archers loose the Parthian shot), not
        # just the one tick they break.
        soldiers = []
        for sq in sorted(field.squads.values(),
                         key=lambda s: s.squad_id):
            if sq.strength == 0:
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
            # a siege engine attacks a wall before all else, and does
            # NOT shoot the garrison through the stones: a ram must
            # touch it (reach 1); artillery (a ranged engine) stands
            # off and BOMBARDS from up to SIEGE_RANGE.
            if sq.structural_dmg > 0:
                arty = sq.stats.get("ranged", 0) > 0
                reach = SIEGE_RANGE if arty else 1
                wall = self._wall_in_range(sol, reach, target)
                if wall is not None:
                    if arty:                 # a visible lobbed shot
                        self.tracers.append((sol.x, sol.y,
                                             wall[0], wall[1]))
                    field.damage_struct(wall[0], wall[1],
                                        sq.structural_dmg)
                    continue
            d = ai._dist(sol.pos, target.pos)
            reach = ai.reach_of(sq)
            ranged_unit = sq.stats.get("ranged", 0) > 0
            shoot_ok = True
            if ranged_unit:                      # high ground shoots farther,
                from engine.battle import battle_terrain as terrain
                reach += terrain.height_reach(field, sol.pos)
                shoot_ok = terrain.has_los(field, sol.pos, target.pos)  # E3
            if d <= reach and shoot_ok:
                # face what you fight — so a foe striking from outside
                # this front takes the flank/rear bonus (P17.11)
                sol.facing = facing.face_toward(sol.x, sol.y,
                                                target.x, target.y)
                if sq.charge_bonus > 1 and d <= ai.MELEE_REACH:
                    self._charge_melee(sol, sq, target)
                else:
                    if d > ai.MELEE_REACH and \
                            sq.stats.get("ranged", 0) > 0:
                        self.tracers.append((sol.x, sol.y,
                                             target.x, target.y))
                    ai.attack(field, sol, sq, target, self.rng)
            else:
                self._order_move(sol, sq, target,
                                 flows.get(sq.team, {}))

        from engine.battle import battle_fire     # P17.E4 fire spreads/burns
        battle_fire.tick(field, self.rng)
        self._update_objectives()            # capture points last

    def _charge_melee(self, sol, sq, target) -> None:
        """A charge-capable soldier (horse, huge beast) hits home: it
        tramples through loose foes (overrun → ride into the cleared
        tile and keep going, up to its speed) and shatters on braced
        spears. One d20 exchange per victim via `charge_attack`."""
        field = self.field
        for _ in range(max(1, int(sq.speed))):     # momentum = speed
            if not sol.alive:
                break
            if (target is None or not target.alive
                    or ai._dist(sol.pos, target.pos) > ai.MELEE_REACH):
                target = ai.pick_target(field, sol, sq)
                if target is None or \
                        ai._dist(sol.pos, target.pos) > ai.MELEE_REACH:
                    break
            tgt_sq = field.squads.get(target.squad_id)
            tx, ty = target.x, target.y
            res = ai.charge_attack(field, sol, sq, target, tgt_sq,
                                   self.rng)
            if res == "overrun":
                self._move(sol, tx, ty)            # ride into the gap
                target = None
                continue
            break                                  # stopped or repelled

    def _order_move(self, sol, sq, target, flow) -> None:
        """Move a soldier out of reach according to its squad's order:
        hold roots, fall-back retreats, move marches to the tile, all
        else charges into contact (siege engines batter a wall first)."""
        intent = orders.advance_intent(sq)
        if intent == "hold":
            return
        if intent == "retreat":
            self._retreat(sol, sq, target)
        elif intent == "goto":
            self._goto(sol, sq, sq.order_target)
        elif sq.structural_dmg > 0 and self._siege_approach(sol, sq):
            return
        else:
            self._advance(sol, sq, target, flow)

    def _wall_in_range(self, sol, reach, target):
        """The wall tile within `reach` worth hitting — the WEAKEST
        first (batter the gate/breach, not the sound stone), then the
        one nearest the enemy. reach 1 = a ram at touch; reach
        SIEGE_RANGE = artillery bombarding."""
        field = self.field
        best, best_key = None, None
        for (sx, sy) in field.struct_hp:
            if max(abs(sx - sol.x), abs(sy - sol.y)) > reach:
                continue
            key = (field.struct_hp[(sx, sy)],
                   ai._dist((sx, sy), target.pos))
            if best_key is None or key < best_key:
                best, best_key = (sx, sy), key
        return best

    def _siege_approach(self, sol, sq) -> bool:
        """Not in range of a wall yet: a siege engine crawls to the
        nearest one (the tick loop hits it once in range). Returns
        True if it spent the tick heading for a wall."""
        field = self.field
        near = ai.nearest_struct(field, sol.x, sol.y)
        if near is None:
            return False                     # no walls: fight normally
        reach = SIEGE_RANGE if sq.stats.get("ranged", 0) > 0 else 1
        for _ in range(self._steps(sol, sq)):
            goal = ai.step_toward(field, sol, near[0], near[1])
            if goal is None or not self._move(sol, *goal):
                break
            if self._wall_in_range(sol, reach, sol) is not None:
                break                        # in range; hit it next tick
        return True

    def _move(self, sol, nx, ny) -> bool:
        """Step a soldier and turn him to face the way he moved — so a
        man in flight shows his back (P17.11)."""
        ox, oy = sol.x, sol.y
        if self.field.move_soldier(sol, nx, ny):
            sol.facing = facing.face_toward(ox, oy, nx, ny)
            return True
        return False

    @staticmethod
    def _steps(sol, sq) -> int:
        """Whole tiles this soldier may move this tick from its speed
        budget; the fractional remainder carries to the next tick. A
        dense LINE marches at half pace (P17.16)."""
        from engine.battle import battle_formation as form
        sol.move_accum += sq.speed * form.speed_mult(sq)
        n = int(sol.move_accum)
        sol.move_accum -= n
        return min(n, MAX_STEPS)

    def _advance(self, sol, sq, target, flow) -> None:
        """March toward the target, up to the speed budget; stop the
        moment a step brings the target into reach (attack next tick).
        Wading slow ground (a stream, a bog) spends extra budget (E2)."""
        field = self.field
        from engine.battle import battle_terrain as terrain
        melee = sq.stats.get("ranged", 0) == 0
        budget = self._steps(sol, sq)
        while budget >= 1:
            goal = ai.role_goal(field, sol, sq, flow)
            if goal is None and melee:
                # flow blocked by the enemy line — push into contact
                goal = ai.step_toward(field, sol, target.x, target.y)
            if goal is None or not self._move(sol, *goal):
                break
            budget -= terrain.move_cost(field, *goal)
            if ai._dist(sol.pos, target.pos) <= ai.reach_of(sq):
                break

    def _retreat(self, sol, sq, target) -> None:
        """Ordered fall-back: withdraw from the target, at speed."""
        field = self.field
        for _ in range(self._steps(sol, sq)):
            dx = (sol.x > target.x) - (sol.x < target.x)
            dy = (sol.y > target.y) - (sol.y < target.y)
            if (dx or dy) and self._move(sol, sol.x + dx,
                                          sol.y + dy):
                continue
            break

    def _goto(self, sol, sq, tile) -> None:
        """Ordered move: march toward an objective tile, ignoring the
        enemy; stop once standing on it."""
        if not (isinstance(tile, (tuple, list)) and len(tile) == 2):
            return
        field = self.field
        tx, ty = int(tile[0]), int(tile[1])
        for _ in range(self._steps(sol, sq)):
            if (sol.x, sol.y) == (tx, ty):
                break
            goal = ai.step_toward(field, sol, tx, ty)
            if goal is None or not self._move(sol, *goal):
                break

    def _flee(self, sol, sq, flows) -> None:
        """A routed squad's men run from the nearest enemy — at speed
        (fast units outrun the rout, slow ones get caught)."""
        field = self.field
        target = ai.pick_target(field, sol, sq)
        if target is None:
            return
        # the Parthian shot (P17.20): a fleeing horse-archer looses over
        # its shoulder at the pursuer before spurring on
        if ai.can_parthian(sq) and \
                ai._dist(sol.pos, target.pos) <= ai.RANGED_REACH:
            self.tracers.append((sol.x, sol.y, target.x, target.y))
            ai.attack(field, sol, sq, target, self.rng)
        for _ in range(self._steps(sol, sq)):
            dx = (sol.x > target.x) - (sol.x < target.x)
            dy = (sol.y > target.y) - (sol.y < target.y)
            if not self._move(sol, sol.x + dx, sol.y + dy):
                break

    # -------------------------------------------------- objectives

    def _update_objectives(self) -> None:
        """Advance each capture point: the team that dominates the
        radius pushes its meter; holding for `hold` ticks seizes it."""
        for o in self.field.objectives:
            if o["captured_by"]:
                continue
            counts = self.field.team_counts_near(o["tile"], o["radius"])
            dom = self._dominant(counts)
            if dom is None:                  # empty or contested — bleed
                o["hold_count"] = max(0, o["hold_count"] - 1)
                if o["hold_count"] == 0:
                    o["holder"] = None
            elif dom == o["holder"]:
                o["hold_count"] += 1
            else:
                o["holder"], o["hold_count"] = dom, 1
            if o["hold_count"] >= o["hold"]:
                o["captured_by"] = o["holder"]

    @staticmethod
    def _dominant(counts):
        if not counts:
            return None
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            return ranked[0][0]
        return None                          # tie: contested, no gain

    # ---------------------------------------------------- outcome

    def over(self) -> bool:
        if self.field.captured_team():
            return True
        live = [t for t in self.field.teams()
                if self.field.team_active(t)]
        return len(live) <= 1

    def result(self) -> dict:
        cap = self.field.captured_team()
        live = [t for t in self.field.teams()
                if self.field.team_active(t)]
        survivors = {t: sum(sq.strength
                            for sq in self.field.squads.values()
                            if sq.team == t)
                     for t in self.field.teams()}
        winner = cap if cap else (live[0] if len(live) == 1 else None)
        return {
            "winner": winner,
            "ticks": self.tick_count,
            "survivors": survivors,
            "objective": cap,
        }

    def run_headless(self, max_ticks: int = 300) -> dict:
        while not self.over() and self.tick_count < max_ticks:
            self.tick()
        return self.result()
