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
MOVE_SHOOT_PENALTY = -4  # P17.9: loosing on the move, un-braced, is wild
ROUT_CASCADE_R = 4       # a rout within this many tiles panics neighbours

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


def _is_pinned(field, squad, exclude=None) -> bool:
    """Held in place by an enemy pressed against a man's FRONT — the
    ANVIL. Hammer-and-anvil is two forces, so the frontal pin must be a
    DIFFERENT squad than `exclude` (the flanking hammer); a lone squad
    enveloping on its own isn't one (P17.18)."""
    for s in squad.alive_soldiers:
        for dx, dy in _NEIGH8:
            occ = field.soldier_at(s.x + dx, s.y + dy)
            esq = _squad_of(field, occ) if occ else None
            if esq is not None and esq.team != squad.team and \
                    esq is not exclude and \
                    facing.arc(s.facing, (s.x + dx, s.y + dy), s.pos) \
                    == "front":
                return True
    return False


def _position_mods(field, atk_sol, target):
    """(to-hit bonus, damage multiplier) from where the blow lands —
    flank/rear arc, being ganged up on, and being surrounded. An all-
    facing RING (P17.17) shows its front to every side, so no arc bonus."""
    from engine.battle import battle_formation as form
    from engine.battle import battle_terrain as terrain
    tgt_sq = field.squads.get(target.squad_id)
    ar = form.effective_arc(tgt_sq, facing.arc(target.facing,
                                               atk_sol.pos, target.pos))
    # a flank anchored on impassable terrain can't be turned (P17.E2)
    if ar in ("flank", "rear") and \
            terrain.anchored(field, atk_sol.pos, target.pos, target.facing):
        ar = "front"
    to_hit = facing.ARC_TO_HIT[ar]
    dmg = facing.ARC_DMG[ar]
    if adjacent_enemies(field, target) >= 2:      # multiple sides
        to_hit += 2
        dmg *= 1.25
    if is_surrounded(field, target):
        dmg *= 1.5
    # P17.15: a routed squad is RUN DOWN — fleeing men can't defend, so
    # a blow lands easy and bites deep.
    if tgt_sq is not None and tgt_sq.routed:
        to_hit += 4
        dmg *= 1.5
    return to_hit, dmg


def nearest_struct(field, x: int, y: int):
    """The wall/gate a siege engine heads for: the WEAKEST first (a
    timber gate over sound stone — concentrate on the breach point),
    then the nearest. None if no walls (P17.6b/P17.6d)."""
    best, best_key = None, None
    for (sx, sy) in field.struct_hp:
        key = (field.struct_hp[(sx, sy)], max(abs(sx - x), abs(sy - y)))
        if best_key is None or key < best_key:
            best, best_key = (sx, sy), key
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


def ranged_reach(squad) -> int:
    """P17.9: a shooter's reach scales with its `range_factor` — a
    longbow (1.5) outranges a crossbow (1.3) outranges a thrown weapon
    (< 1). Base RANGED_REACH at factor 1.0."""
    rf = squad.stats.get("range_factor", 1.0)
    return max(1, int(RANGED_REACH * rf))


def reach_of(squad) -> int:
    return ranged_reach(squad) if squad.stats.get("ranged", 0) > 0 \
        else MELEE_REACH


def can_parthian(squad) -> bool:
    """A horse-archer that looses over its shoulder as it rides away —
    the Parthian shot (P17.20): it shoots WHILE fleeing, with no penalty
    for the direction it faces (the target's arc governs, not ours)."""
    return bool(squad.stats.get("parthian")) and \
        squad.stats.get("ranged", 0) > 0


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
    from engine.battle import battle_formation as form
    from engine.battle import battle_terrain as terrain
    from engine.battle import battle_armour as armour
    st = atk_squad.stats
    d = _dist(atk_soldier.pos, target.pos)
    ranged = False
    if d <= MELEE_REACH:
        power = st.get("melee", 0)
    elif d <= ranged_reach(atk_squad) + terrain.height_reach(
            field, atk_soldier.pos) and st.get("ranged", 0) > 0:
        if atk_soldier.reload_left > 0:
            return False                     # still loading — no shot (P17.9)
        if not terrain.has_los(field, atk_soldier.pos, target.pos):
            return False                     # can't shoot through cover (E3)
        power = st.get("ranged", 0)          # high ground shoots farther
        ranged = True
        # loosing spends the load: a heavy shooter must reload before the
        # next shot. A reload-0 weapon (a longbow) is never gated (+1 so
        # the decrement at tick's end leaves exactly `reload` idle ticks).
        if st.get("reload", 0) > 0:
            atk_soldier.reload_left = st["reload"] + 1
    else:
        return False
    # d20 + power vs 10 + defence of the target's squad; a RANGED shot
    # is further blunted by the cover the target stands in (P17.6), and
    # flank/rear/surround bonuses (P17.11) make it easier and harder.
    tgt_squad = field.squads.get(target.squad_id)
    defence = tgt_squad.stats.get("defense", 0) if tgt_squad else 0
    dc = 10 + defence
    # the defender's arc to this attacker (P17.11) — governs the shield
    # (P17.10) and the morale shock below; computed once.
    def_arc = form.effective_arc(
        tgt_squad, facing.arc(target.facing, atk_soldier.pos, target.pos)
    ) if tgt_squad is not None else None
    if ranged:
        dc += round(field.cover_at(target.x, target.y) * 10)
    if tgt_squad is not None:      # P17.16 LINE shield-overlap
        dc += form.defense_bonus(field, tgt_squad, target, atk_soldier)
        dc += armour.shield_dc_bonus(tgt_squad.stats, def_arc, ranged)  # P17.10
    to_hit, dmg_mult = _position_mods(field, atk_soldier, target)
    roll = rng.randint(1, 20) + power + to_hit
    roll += form.attack_penalty(atk_squad)     # P17.17 RING fights weaker
    roll += terrain.height_to_hit(field, atk_soldier.pos, target.pos)  # E1
    # P17.9 move-and-shoot: loosing the tick after you moved is wild —
    # unless you're a horse-archer trained to it (the Parthian shot).
    if ranged and atk_soldier.moved_last and not can_parthian(atk_squad):
        roll += MOVE_SHOOT_PENALTY
    if roll < dc:
        return False
    dmg = max(1, int(power // 3 * dmg_mult) + rng.randint(0, 2))
    if ranged and tgt_squad is not None:   # P17.16 LOOSE spreads the volley
        dmg = max(1, int(dmg * form.incoming_ranged_mult(tgt_squad)))
    if tgt_squad is not None:              # P17.10 armour turns some types
        dmg = armour.apply_resist(dmg, tgt_squad.stats.get("armour_type"),
                                  st.get("damage_type"))
    if ranged and st.get("fire_arrow"):    # P17.E4 fire arrows set tiles alight
        from engine.battle import battle_fire
        battle_fire.ignite(field, target.x, target.y)
    target.hurt(dmg)
    # P17.15: a blow from the flank or rear shakes the whole squad's
    # nerve — but an all-facing RING (P17.17) has no exposed side.
    if tgt_squad is not None and not tgt_squad.routed:
        ar = def_arc
        if ar in ("flank", "rear") and terrain.anchored(
                field, atk_soldier.pos, target.pos, target.facing):
            ar = "front"                      # anchored — no morale shock (E2)
        if ar == "rear":
            tgt_squad.adjust_morale(-3)
        elif ar == "flank":
            tgt_squad.adjust_morale(-2)
        # P17.18 hammer-and-anvil: flanked by THIS squad while a DIFFERENT
        # one pins the front — the anvil holds them fast while the hammer
        # falls = a rout trigger (two coordinating forces, not envelopment).
        if ar in ("flank", "rear") and \
                _is_pinned(field, tgt_squad, exclude=atk_squad):
            tgt_squad.adjust_morale(-6)
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


def _is_braced(squad) -> bool:
    """Set to receive (P17.17): a brace-capable squad only stops a charge
    when braced — holding still, facing the threat. On 'hold' it braces
    by default; caught charging or moving, the hedge is just infantry."""
    return getattr(squad, "braced", False) or squad.order == "hold"


def charge_attack(field, atk_sol, atk_sq, tgt_sol, tgt_sq, rng) -> str:
    """A charge into an occupied tile. Returns:
      'overrun'  — the way is cleared (footman killed or shoved), ride on
      'stopped'  — the charge is blunted; the charger holds
      'repelled' — horse or rider is down; the charger is dead
    Braced spears/pikes (bonus_vs_cavalry) set to receive and strike
    first; loose infantry get trampled unless they defend and counter."""
    a, t = atk_sq.stats, tgt_sq.stats
    anti_cav = t.get("bonus_vs_cavalry", 1.0)
    if anti_cav > 1.0 and _is_braced(tgt_sq):   # the hedge, SET TO RECEIVE
        # braced pike/spear negate the charge and strike the interrupt
        # first (P17.17); caught un-braced, the hedge is just infantry.
        r = _strike(rng, t.get("melee", 0), anti_cav, atk_sol,
                    a.get("defense", 0))
        if r == "kill":
            field.vacate(atk_sol)
            return "repelled"
        return "stopped"                  # the wall holds; charge blunted
    # a charge into a flank or rear is even more devastating (P17.11);
    # a WEDGE concentrates to breach (P17.18); DOWNHILL adds momentum (E1)
    from engine.battle import battle_formation as form
    from engine.battle import battle_terrain as terrain
    ar = facing.arc(tgt_sol.facing, atk_sol.pos, tgt_sol.pos)
    momentum = terrain.charge_dmg_mult(field, atk_sol.pos, tgt_sol.pos)
    r = _strike(rng, a.get("melee", 0),
                a.get("charge_bonus", 1.0) * facing.ARC_DMG[ar] * momentum,
                tgt_sol, t.get("defense", 0),
                to_hit=facing.ARC_TO_HIT[ar] + form.wedge_charge_bonus(atk_sq))
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


def cover_seek_step(field, soldier, squad, target):
    """P17.6e: a foot archer already in shooting range but caught in the
    OPEN sidesteps to the best nearby COVER that keeps the shot alive (the
    tile is in range AND has line of sight to the target) — hunkering in
    the treeline instead of trading arrows in the clear. Returns the tile
    to step to, or None to hold and shoot where it stands."""
    if squad.category != "archer":
        return None
    from engine.battle import battle_terrain as terrain
    reach = ranged_reach(squad)
    best, best_cover = None, field.cover_at(soldier.x, soldier.y)
    for dx, dy in _NEIGH8:
        nx, ny = soldier.x + dx, soldier.y + dy
        if not field.passable(nx, ny):
            continue
        cov = field.cover_at(nx, ny)
        if cov <= best_cover:
            continue
        if _dist((nx, ny), target.pos) > reach:
            continue
        if not terrain.has_los(field, (nx, ny), target.pos):
            continue
        best, best_cover = (nx, ny), cov
    return best


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
        # P17.15: a real SHARE of the squad hemmed in saps its nerve —
        # but a deep squad shrugs off a couple of trapped men (tempers
        # the fragile morale from the playtest).
        alive = squad.alive_soldiers
        if alive:
            boxed = sum(1 for s in alive if is_surrounded(field, s))
            if boxed / len(alive) >= 0.3:
                squad.adjust_morale(-4)
            elif boxed:
                squad.adjust_morale(-1)
    # P17.15: a routed ally shakes the line — a CLOSE rout PANICS it (the
    # cascade that collapses a wing), a distant one only unsettles it.
    for sq in field.squads.values():
        if sq.team != squad.team or not sq.routed or \
                sq.squad_id == squad.squad_id:
            continue
        oc = sq.centroid()
        if c is not None and oc is not None and _dist(c, oc) <= ROUT_CASCADE_R:
            squad.adjust_morale(-4)
        else:
            squad.adjust_morale(-1)
    # P17.16: a held formation steadies the line; a broken one takes a
    # one-time shock as it comes apart.
    from engine.battle import battle_formation as form
    squad.adjust_morale(form.steady(field, squad))
    form.check_break(field, squad)
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
