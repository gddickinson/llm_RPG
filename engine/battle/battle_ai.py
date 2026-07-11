"""Group AI (P17.3) — the colosseum brain, grid-native.

Ported from autonomous_world's `colosseum` heuristics onto the
battle grid: FOCUS-FIRE target selection (low HP first, closer
first, the squad's ordered target preferred), ROLE movement
(archers kite, infantry/cavalry close, everyone steps the flow
field toward the enemy), and squad MORALE (strength ratio,
outnumbered, allies routed). Deterministic — a seeded rng — and
LLM-free.

Combat here is self-contained on the battle's own Soldier tokens
(a d20 vs the archetype's melee/ranged and defence). When a battle
is embodied in the world (P17.7+), that bridges to combat_system;
the headless skirmish stays pure so it tests instantly.
"""

from typing import Optional

from engine.battle import battle_facing as facing

MELEE_REACH = 1
RANGED_REACH = 5

_NEIGH8 = ((1, 0), (-1, 0), (0, 1), (0, -1),
           (1, 1), (1, -1), (-1, 1), (-1, -1))


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _squad_of(field, sid: str):
    return field.squads.get(sid.rsplit("_", 1)[0]) if sid else None


def adjacent_enemies(field, sol) -> int:
    """How many enemy soldiers are pressed against this one (8-dir) —
    a man engaged on several sides can't guard them all."""
    n = 0
    for dx, dy in _NEIGH8:
        occ = field.soldier_at(sol.x + dx, sol.y + dy)
        sq = _squad_of(field, occ) if occ else None
        if sq is not None and sq.team != sol.team:
            n += 1
    return n


def is_surrounded(field, sol) -> bool:
    """Boxed in: four+ enemies on him, or no free tile to fall back
    to. Surrounded men take extra punishment (P17.11)."""
    if adjacent_enemies(field, sol) >= 4:
        return True
    for dx, dy in _NEIGH8:
        if field.passable(sol.x + dx, sol.y + dy):
            return False
    return True


def _position_mods(field, atk_sol, target):
    """(to-hit bonus, damage multiplier) from where the blow lands —
    flank/rear arc, being ganged up on, and being surrounded."""
    ar = facing.arc(target.facing, atk_sol.pos, target.pos)
    to_hit = facing.ARC_TO_HIT[ar]
    dmg = facing.ARC_DMG[ar]
    if adjacent_enemies(field, target) >= 2:      # multiple sides
        to_hit += 2
        dmg *= 1.25
    if is_surrounded(field, target):
        dmg *= 1.5
    return to_hit, dmg


def nearest_struct(field, x: int, y: int):
    """The wall/gate tile nearest (x, y), or None — siege engines
    home on it when the enemy is walled off (P17.6b)."""
    best, bd = None, None
    for (sx, sy) in field.struct_hp:
        d = max(abs(sx - x), abs(sy - y))
        if bd is None or d < bd:
            best, bd = (sx, sy), d
    return best


def step_toward(field, sol, tx: int, ty: int):
    """Greedy: the passable neighbour nearest to (tx, ty). Closes the
    final tiles into contact when the flow field (aimed at the enemy
    centroid) is blocked by the enemy's own front rank — otherwise a
    big line gridlocks a few tiles short and never fights."""
    best, best_d = None, None
    for dx, dy in _NEIGH8:
        nx, ny = sol.x + dx, sol.y + dy
        if not field.passable(nx, ny):
            continue
        d = max(abs(nx - tx), abs(ny - ty))
        if best_d is None or d < best_d:
            best, best_d = (nx, ny), d
    return best


def reach_of(squad) -> int:
    return RANGED_REACH if squad.stats.get("ranged", 0) > 0 \
        else MELEE_REACH


def pick_target(field, soldier, squad):
    """Focus-fire: the squad's ordered target squad first, else any
    enemy — lowest HP, then nearest. Returns an enemy Soldier."""
    from engine.battle import battle_orders as orders
    order_sid = squad.order_target if orders.is_focus(squad.order) \
        else None
    best, best_key = None, None
    for enemy in field.squads.values():
        if enemy.team == soldier.team or not enemy.active:
            continue
        priority = 0 if enemy.squad_id == order_sid else 1
        for es in enemy.alive_soldiers:
            key = (priority, es.hp, _dist(soldier.pos, es.pos))
            if best_key is None or key < best_key:
                best, best_key = es, key
    return best


def attack(field, atk_soldier, atk_squad, target, rng) -> bool:
    """Resolve one strike. Returns True if the target fell."""
    st = atk_squad.stats
    d = _dist(atk_soldier.pos, target.pos)
    ranged = False
    if d <= MELEE_REACH:
        power = st.get("melee", 0)
    elif d <= RANGED_REACH and st.get("ranged", 0) > 0:
        power = st.get("ranged", 0)
        ranged = True
    else:
        return False
    # d20 + power vs 10 + defence of the target's squad; a RANGED shot
    # is further blunted by the cover the target stands in (P17.6), and
    # flank/rear/surround bonuses (P17.11) make it easier and harder.
    tgt_squad = field.squads.get(target.squad_id)
    defence = tgt_squad.stats.get("defense", 0) if tgt_squad else 0
    dc = 10 + defence
    if ranged:
        dc += round(field.cover_at(target.x, target.y) * 10)
    to_hit, dmg_mult = _position_mods(field, atk_soldier, target)
    roll = rng.randint(1, 20) + power + to_hit
    if roll < dc:
        return False
    dmg = max(1, int(power // 3 * dmg_mult) + rng.randint(0, 2))
    target.hurt(dmg)
    if not target.alive:
        field.vacate(target)
        return True
    return False


def _strike(rng, power, mult, defender, defender_def, to_hit=0) -> str:
    """One blow: d20+power(+to_hit) vs 10+def; on a hit, (power*mult)//3
    dmg. Returns 'kill' | 'hit' | 'miss'."""
    if rng.randint(1, 20) + int(power) + to_hit < 10 + defender_def:
        return "miss"
    dmg = max(1, int(power * mult) // 3 + rng.randint(0, 2))
    defender.hurt(dmg)
    return "kill" if not defender.alive else "hit"


def _shove(field, victim, charger) -> bool:
    """Barge a survived footman to the open tile FARTHEST from the
    charger, clearing the lane. False if the press leaves nowhere."""
    best, bd = None, -1
    for dx, dy in _NEIGH8:
        nx, ny = victim.x + dx, victim.y + dy
        if not field.passable(nx, ny):
            continue
        d = max(abs(nx - charger.x), abs(ny - charger.y))
        if d > bd:
            best, bd = (nx, ny), d
    if best is None:
        return False
    field.move_soldier(victim, *best)
    return True


def charge_attack(field, atk_sol, atk_sq, tgt_sol, tgt_sq, rng) -> str:
    """A charge into an occupied tile. Returns:
      'overrun'  — the way is cleared (footman killed or shoved), ride on
      'stopped'  — the charge is blunted; the charger holds
      'repelled' — horse or rider is down; the charger is dead
    Braced spears/pikes (bonus_vs_cavalry) set to receive and strike
    first; loose infantry get trampled unless they defend and counter."""
    a, t = atk_sq.stats, tgt_sq.stats
    anti_cav = t.get("bonus_vs_cavalry", 1.0)
    if anti_cav > 1.0:                     # the hedge of points
        r = _strike(rng, t.get("melee", 0), anti_cav, atk_sol,
                    a.get("defense", 0))
        if r == "kill":
            field.vacate(atk_sol)
            return "repelled"
        return "stopped"                  # the wall holds; charge blunted
    # a charge into a flank or rear is even more devastating (P17.11)
    ar = facing.arc(tgt_sol.facing, atk_sol.pos, tgt_sol.pos)
    r = _strike(rng, a.get("melee", 0),
                a.get("charge_bonus", 1.0) * facing.ARC_DMG[ar],
                tgt_sol, t.get("defense", 0),
                to_hit=facing.ARC_TO_HIT[ar])
    if r == "kill":
        field.vacate(tgt_sol)
        return "overrun"
    if r == "hit" and _shove(field, tgt_sol, atk_sol):
        return "overrun"                  # bowled aside — ride through
    if r == "miss":                       # a clean parry, then a riposte
        c = _strike(rng, t.get("melee", 0), 1.0, atk_sol,
                    a.get("defense", 0))
        if c == "kill":
            field.vacate(atk_sol)
            return "repelled"
    return "stopped"


def role_goal(field, soldier, squad, dist):
    """Where this soldier wants to be this tick. Archers KITE (back
    off if an enemy is adjacent), everyone else advances the flow
    field toward the enemy."""
    from engine.battle.battle_flow import step_down
    if squad.category == "archer":
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            adj = field.soldier_at(soldier.x + dx, soldier.y + dy)
            if adj is not None:
                sq_id = adj.split("_")[0] if "_" in adj else adj
                enemy = field.squads.get(sq_id)
                if enemy and enemy.team != soldier.team:
                    # step directly away — kite
                    bx, by = soldier.x - dx, soldier.y - dy
                    if field.passable(bx, by):
                        return (bx, by)
    return step_down(field, soldier.x, soldier.y, dist)


def update_morale(field, squad) -> None:
    """Strength ratio, being outnumbered locally, and allies routing
    all press on the squad's ONE morale bar (colosseum model)."""
    if not squad.active:
        return
    ratio = squad.strength / max(1, len(squad.soldiers))
    if ratio < 0.5:
        squad.adjust_morale(-4)
    elif ratio < 0.75:
        squad.adjust_morale(-2)
    # local numbers: enemies vs allies near the centroid
    c = squad.centroid()
    if c is not None:
        near_enemy = _count_near(field, c, squad.team, foe=True)
        near_ally = _count_near(field, c, squad.team, foe=False)
        if near_enemy > near_ally + 3:
            squad.adjust_morale(-3)
    # a routed friendly squad shakes the line
    routed_allies = sum(
        1 for sq in field.squads.values()
        if sq.team == squad.team and sq.routed and
        sq.squad_id != squad.squad_id)
    if routed_allies:
        squad.adjust_morale(-2 * routed_allies)
    if squad.morale < 40:      # slow rally when not pressed
        squad.adjust_morale(1)


def _count_near(field, pos, team: str, foe: bool, r: int = 6) -> int:
    n = 0
    for sq in field.squads.values():
        is_foe = sq.team != team
        if is_foe != foe or not sq.active:
            continue
        c = sq.centroid()
        if c and _dist(pos, c) <= r:
            n += sq.strength
    return n
