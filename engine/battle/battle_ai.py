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

MELEE_REACH = 1
RANGED_REACH = 5


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def reach_of(squad) -> int:
    return RANGED_REACH if squad.stats.get("ranged", 0) > 0 \
        else MELEE_REACH


def pick_target(field, soldier, squad):
    """Focus-fire: the squad's ordered target squad first, else any
    enemy — lowest HP, then nearest. Returns an enemy Soldier."""
    order_sid = squad.order_target if squad.order == "focus" else None
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
    if d <= MELEE_REACH:
        power = st.get("melee", 0)
    elif d <= RANGED_REACH and st.get("ranged", 0) > 0:
        power = st.get("ranged", 0)
    else:
        return False
    # d20 + power vs 10 + defence of the target's squad
    tgt_squad = field.squads.get(target.squad_id)
    defence = tgt_squad.stats.get("defense", 0) if tgt_squad else 0
    roll = rng.randint(1, 20) + power
    if roll < 10 + defence:
        return False
    dmg = max(1, power // 3 + rng.randint(0, 2))
    target.hurt(dmg)
    if not target.alive:
        field.vacate(target)
        return True
    return False


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
