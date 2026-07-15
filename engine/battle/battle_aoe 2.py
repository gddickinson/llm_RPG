"""Area effects & battle magic (P17.12).

A single strike hits one man; an EXPLOSION hits a cluster. This is the
blast geometry the grid battle was missing — a catapult stone or a
trebuchet's payload crumping down among packed ranks, a war-mage's
fireball, a cauldron of boiling oil — landing damage across a radius
(fiercest at the point of impact, fading one ring outward) and, for the
fiery sort, PAINTING the P17.E4 surface layer so the scorched ground
keeps killing after the flash. Armour still resists by damage type
(P17.10), but flame ignores it.

Pure over the field; the session routes siege bombardment and battle-mage
casts here.
"""

from engine.battle import battle_fire
from engine.battle import battle_armour as armour


def tiles_in_radius(field, cx: int, cy: int, radius: int):
    """The in-bounds tiles within a Chebyshev `radius` of the impact."""
    out = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x, y = cx + dx, cy + dy
            if field.in_bounds(x, y):
                out.append((x, y))
    return out


def _soldiers_by_pos(field) -> dict:
    m = {}
    for sq in field.squads.values():
        for s in sq.alive_soldiers:
            m[s.pos] = (s, sq)
    return m


def _falloff(damage: int, dist: int, radius: int) -> int:
    """Full at the point of impact, fading to the edge of the burst."""
    return max(1, int(round(damage * (1.0 - dist / (radius + 1)))))


def blast(field, cx: int, cy: int, radius: int, damage: int,
          damage_type=None, hit_structs: bool = True):
    """Damage everything in the burst — soldiers (armour-typed) and, unless
    `hit_structs` is off, structures. Returns (soldiers_hit, killed)."""
    occ = _soldiers_by_pos(field)
    hit = killed = 0
    for (x, y) in tiles_in_radius(field, cx, cy, radius):
        dist = max(abs(x - cx), abs(y - cy))
        dmg = _falloff(damage, dist, radius)
        if (x, y) in occ:
            sol, sq = occ[(x, y)]
            d = armour.apply_resist(dmg, sq.stats.get("armour_type"),
                                    damage_type)
            sol.hurt(d)
            hit += 1
            if not sol.alive:
                field.vacate(sol)
                killed += 1
        if hit_structs and (x, y) in field.struct_hp:
            field.damage_struct(x, y, dmg)
    return hit, killed


def fireball(field, cx: int, cy: int, radius: int = 1, damage: int = 8):
    """A burst of flame: a blast that also SETS the cluster alight (fire
    ignores armour), so the fire then lingers and spreads via the E4
    `battle_fire.tick`. Returns (soldiers_hit, killed)."""
    h, k = blast(field, cx, cy, radius, damage, damage_type="fire",
                 hit_structs=True)
    for (x, y) in tiles_in_radius(field, cx, cy, radius):
        battle_fire.ignite(field, x, y)
    return h, k


def cast(field, spell: str, cx: int, cy: int, radius: int, power: int):
    """Route a battle-mage's spell to its effect. `fireball` blasts &
    ignites; `oil` slicks the ground for a later spark; anything else is a
    plain concussive blast. Returns (soldiers_hit, killed)."""
    if spell == "fireball":
        return fireball(field, cx, cy, radius, power)
    if spell == "oil":
        battle_fire.pour_oil(field, cx, cy, radius)
        return (0, 0)
    return blast(field, cx, cy, radius, power, damage_type="blunt")
