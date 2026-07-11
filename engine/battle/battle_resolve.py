"""Lanchester auto-resolver (P17.1) — the headless battle math.

Ported from autonomous_world's `warfare.BattleField.resolve` onto
llm_RPG's data layer, kept a pure seeded function so it's fully
deterministic and testable and carries NO UI or per-tick loop. An
`Army` is a bag of `Unit`s (a homogeneous body of N soldiers), an
optional commander bonus, a formation, and (for the defender)
fortifications. `resolve(attacker, defender, ...)` runs up to
`max_rounds` of a melee (linear Lanchester) + ranged (square
Lanchester) + siege exchange and returns who won, survivor counts,
and a round log.

The two combat laws, faithfully: MELEE casualties scale with the
STRENGTH DIFFERENCE (linear — the classic melee attrition), RANGED
casualties scale with the SQUARE of firepower share (concentration
of fire wins). Matchups (cavalry>archer, spear>cavalry via the
unit stat, siege>fortification), terrain, formation and commander
multipliers all feed the totals. War-beast terror and medic
healing tick each round.
"""

import random
from typing import List, Optional

from engine.battle.battle_data import (category_of, formation,
                                       fort_stats, matchup_bonus,
                                       terrain_mod, unit_stats)


def unit_category(unit_type: str) -> str:
    return category_of(unit_type)


class Unit:
    """A homogeneous body of N soldiers of one type."""

    def __init__(self, unit_type: str, size: int, quality: float = 1.0):
        self.unit_type = unit_type
        self.stats = unit_stats(unit_type)
        self.size = size
        self.max_size = size
        self.quality = max(0.5, min(2.0, quality))
        self.morale = 70
        self.routed = False

    @property
    def category(self) -> str:
        return self.stats.get("category", "infantry")

    @property
    def alive(self) -> bool:
        return self.size > 0 and not self.routed

    @property
    def effectiveness(self) -> float:
        # shrinks with casualties; grows with equipment quality
        return (self.size / max(1, self.max_size)) * self.quality

    def melee_power(self) -> float:
        return self.stats.get("melee", 0) * self.size * self.effectiveness

    def ranged_power(self) -> float:
        return self.stats.get("ranged", 0) * self.size * self.effectiveness

    def defense_power(self) -> float:
        return self.stats.get("defense", 0) * self.size * self.effectiveness

    def take_casualties(self, n: int) -> None:
        self.size = max(0, self.size - max(0, n))
        if self.size <= 0:
            self.routed = True

    def heal(self, n: int) -> None:
        self.size = min(self.max_size, self.size + n)


class Fort:
    def __init__(self, fort_type: str):
        self.fort_type = fort_type
        st = fort_stats(fort_type)
        self.hp = st["hp"]
        self.max_hp = st["hp"]
        self.defense_bonus = st.get("defense_bonus", 1.0)
        self.breached = False

    def take_damage(self, dmg: float) -> None:
        self.hp = max(0, self.hp - dmg)
        if self.hp <= 0:
            self.breached = True


class Army:
    def __init__(self, name: str, units: List[Unit],
                 commander_bonus: float = 0.0,
                 form: Optional[str] = None,
                 forts: Optional[List[Fort]] = None):
        self.name = name
        self.units = units
        self.commander_bonus = commander_bonus
        self.formation = form
        self.forts = forts or []

    # ---- convenience builders ------------------------------------

    @staticmethod
    def make(name: str, roster, commander_bonus: float = 0.0,
             form: Optional[str] = None, forts=None) -> "Army":
        """roster: list of (unit_type, size) or (unit_type, size,
        quality). forts: list of fort-type strings."""
        units = [Unit(*(spec if len(spec) == 3 else (*spec, 1.0)))
                 for spec in roster]
        fobjs = [Fort(f) for f in (forts or [])]
        return Army(name, units, commander_bonus, form, fobjs)

    # ---- aggregate stats -----------------------------------------

    @property
    def active(self) -> List[Unit]:
        return [u for u in self.units if u.alive]

    def defeated(self) -> bool:
        return not self.active

    def survivors(self) -> int:
        return sum(u.size for u in self.units)

    def _form_mult(self, key: str) -> float:
        return formation(self.formation).get(key, 1.0)

    def total_melee(self) -> float:
        base = sum(u.melee_power() for u in self.active)
        return base * self._form_mult("attack_mult")

    def total_ranged(self) -> float:
        return sum(u.ranged_power() for u in self.active)

    def total_defense(self) -> float:
        base = sum(u.defense_power() for u in self.active)
        return base * self._form_mult("defense_mult")


def _best_matchup(atk: Army, dfn: Army) -> float:
    """The strongest RPS edge the attacker's categories have over
    the defender's (autonomous_world takes the max)."""
    best = 1.0
    atk_cats = {u.category for u in atk.active}
    dfn_cats = {u.category for u in dfn.active}
    for a in atk_cats:
        for d in dfn_cats:
            best = max(best, matchup_bonus(a, d))
    return best


def _anti_cavalry(defender: Army, attacker: Army) -> float:
    """Spear/pike blunt the CHARGE: if the defender fields
    anti-cavalry infantry and the attacker fields cavalry, the
    attacker's cavalry hits softer. Returns the divisor (>=1)."""
    if not any(u.category == "cavalry" for u in attacker.active):
        return 1.0
    best = 1.0
    for u in defender.active:
        best = max(best, u.stats.get("bonus_vs_cavalry", 1.0))
    return best


def _defense_factor(army: Army) -> float:
    """How much this army SHRUGS OFF incoming melee: formation
    defense, standing forts, and average unit armor. >= 0.3."""
    factor = army._form_mult("defense_mult")
    act = army.active
    if act:
        avg_def = sum(u.stats.get("defense", 0) for u in act) / \
            len(act)
        factor *= 1.0 + avg_def / 10.0
    for f in army.forts:
        if not f.breached:
            factor *= f.defense_bonus
    return max(0.3, factor)


def _charge_bonus(army: Army) -> float:
    """The strongest cavalry charge multiplier in the line."""
    best = 1.0
    for u in army.active:
        if u.category == "cavalry":
            best = max(best, u.stats.get("charge_bonus", 1.0))
    return best


def _evasion(army: Army) -> float:
    """Fast units dodge volleys and close on archers. >= 1."""
    act = army.active
    if not act:
        return 1.0
    avg_speed = sum(u.stats.get("speed", 1.0) for u in act) / len(act)
    return max(1.0, avg_speed)


def _wall_standing(defender: Army) -> bool:
    """A real wall (an HP fort that isn't a moat/trench) still up."""
    from engine.battle.battle_data import fort_stats
    for f in defender.forts:
        if f.breached:
            continue
        if fort_stats(f.fort_type).get("hp", 0) < 9999:
            return True
    return False


def resolve(attacker: Army, defender: Army, terrain: str = "plains",
            is_siege: bool = False, seed: int = 0,
            max_rounds: int = 12) -> dict:
    """Fight it out. Deterministic for a given seed."""
    rng = random.Random(seed)
    tmod = terrain_mod(terrain)
    log = []
    rounds = 0

    for rnd in range(1, max_rounds + 1):
        if attacker.defeated() or defender.defeated():
            break
        rounds = rnd
        acmd = 1.0 + attacker.commander_bonus
        dcmd = 1.0 + defender.commander_bonus

        # MELEE — each side's offense inflicts casualties, REDUCED
        # by the target's defense (formation, forts, unit armor), so
        # attack AND defense both matter (AW left defense unused).
        amel = attacker.total_melee() * acmd * \
            _best_matchup(attacker, defender)
        dmel = defender.total_melee() * dcmd * \
            _best_matchup(defender, attacker)
        if any(u.category == "cavalry" for u in attacker.active):
            amel *= tmod.get("cavalry_attack", 1.0)
            if rnd <= 2:                      # the CHARGE hits home
                amel *= _charge_bonus(attacker)
        if any(u.category == "cavalry" for u in defender.active):
            dmel *= tmod.get("cavalry_attack", 1.0)
        # spears blunt the enemy charge (reduce incoming cavalry)
        amel /= _anti_cavalry(defender, attacker)
        dmel /= _anti_cavalry(attacker, defender)
        # an unbreached wall keeps besiegers off the defenders:
        # only siege engines + ranged reach until the breach opens
        if is_siege and _wall_standing(defender):
            amel *= 0.15

        amel *= rng.uniform(0.85, 1.15)
        dmel *= rng.uniform(0.85, 1.15)
        def_cas = max(1, int(amel * 0.05 /
                             _defense_factor(defender)))
        atk_cas = max(1, int(dmel * 0.05 /
                             _defense_factor(attacker)))

        # RANGED — square Lanchester on firepower share, softened by
        # the RPS matchup and the target's SPEED (fast chargers close
        # the gap and eat fewer volleys)
        ar = attacker.total_ranged() * acmd * \
            tmod.get("archer_attack", 1.0) * \
            _best_matchup(attacker, defender)
        dr = defender.total_ranged() * dcmd * \
            tmod.get("archer_attack", 1.0) * \
            _best_matchup(defender, attacker)
        if ar + dr > 0:
            asq, dsq = ar * ar, dr * dr
            tot = asq + dsq + 0.01
            def_cas += int(ar * (asq / tot) * 0.05 /
                           _evasion(defender))
            atk_cas += int(dr * (dsq / tot) * 0.05 /
                           _evasion(attacker))

        # SIEGE — engines batter forts; oil + towers bite attackers
        if is_siege:
            for u in attacker.active:
                sd = u.stats.get("structural_dmg", 0)
                if sd > 0:
                    # each engine in the line batters (scale by size)
                    hit = sd * u.size * u.quality
                    for f in defender.forts:
                        if not f.breached:
                            f.take_damage(hit)
                            break
            for f in defender.forts:
                st = fort_stats(f.fort_type)
                if not f.breached:
                    atk_cas += int(st.get("damage_per_round", 0) * 0.3)
                    slots = st.get("archer_slots", 5)
                    atk_cas += int(st.get("ranged_attack", 0) *
                                   slots * 0.02)

        # apply casualties spread across the front line
        _spread(defender.active, def_cas)
        _spread(attacker.active, atk_cas)

        # TERROR — war beasts sap enemy morale
        _terror(attacker, defender)
        _terror(defender, attacker)
        _check_rout(attacker)
        _check_rout(defender)

        # MEDICS — patch the line
        _heal(attacker)
        _heal(defender)

        log.append({"round": rnd, "atk": attacker.survivors(),
                    "def": defender.survivors()})

    winner = None
    if attacker.defeated() and not defender.defeated():
        winner = defender.name
    elif defender.defeated() and not attacker.defeated():
        winner = attacker.name
    elif not attacker.defeated() and not defender.defeated():
        winner = (attacker.name if attacker.survivors() >=
                  defender.survivors() else defender.name)
    return {
        "winner": winner,
        "rounds": rounds,
        "attacker_survivors": attacker.survivors(),
        "defender_survivors": defender.survivors(),
        "breached": any(f.breached for f in defender.forts),
        "log": log,
    }


_FRONT = ("infantry", "cavalry", "beast")


def _spread(units: List[Unit], casualties: int) -> None:
    """Casualties hit the FRONT LINE first (infantry/cavalry/beast);
    siege engines and support shelter behind the escort, so a
    protected trebuchet keeps battering the wall (real sieges)."""
    if casualties <= 0 or not units:
        return
    front = [u for u in units if u.category in _FRONT]
    rear = [u for u in units if u.category not in _FRONT]
    left = casualties
    for tier in (front, rear):
        if left <= 0 or not tier:
            continue
        per = max(1, left // len(tier))
        for u in tier:
            take = min(per, left, u.size)
            u.take_casualties(take)
            left -= take
            if left <= 0:
                break
    if left > 0:
        units[0].take_casualties(left)


def _terror(src: Army, foe: Army) -> None:
    terror = sum(u.stats.get("terror", 0) for u in src.active)
    if terror <= 0:
        return
    for u in foe.active:
        u.morale -= int(terror * 0.1)


def _check_rout(army: Army) -> None:
    for u in army.units:
        if u.alive and u.morale <= u.stats.get("morale_threshold", 20):
            u.routed = True


def _heal(army: Army) -> None:
    for u in army.active:
        heal = u.stats.get("heal_per_round", 0)
        if heal <= 0:
            continue
        for target in army.active:
            if target.size < target.max_size:
                target.heal(heal)
                break
