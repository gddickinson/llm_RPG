"""Battlefield elevation (P17.E1) — the advantage of high ground.

The terrain itself as a combatant. A tile carries an ELEVATION on the
field (`field.elevation_at`); this module reads the height difference
between two positions and turns it into the classic edge of the high
ground, all pure and testable:

  * DOWNHILL you strike easier — +1 to-hit per level you stand above
    your foe (capped); UPHILL costs you the same.
  * A charge DOWNHILL gathers momentum (more damage); UPHILL it stalls.
  * HEIGHT extends a bow's range and a lookout's sight — you shoot and
    see farther from a hill or a rampart.

Zero-cost on flat ground (the common case), so a battle with no
elevation set behaves exactly as before.
"""

MAX_TO_HIT = 3          # cap the height-of-advantage to-hit swing
MAX_REACH = 2           # cap the extra ranged tiles from height


def _diff(field, atk_pos, def_pos) -> int:
    return field.elevation_at(*atk_pos) - field.elevation_at(*def_pos)


def height_to_hit(field, atk_pos, def_pos) -> int:
    """+to-hit downhill, −to-hit uphill (capped) — the high-ground edge."""
    d = _diff(field, atk_pos, def_pos)
    return max(-MAX_TO_HIT, min(MAX_TO_HIT, d))


def charge_dmg_mult(field, atk_pos, def_pos) -> float:
    """A charge DOWNHILL hits harder (momentum); UPHILL it's blunted."""
    d = _diff(field, atk_pos, def_pos)
    if d > 0:
        return 1.0 + 0.15 * min(d, 2)          # up to +30%
    if d < 0:
        return max(0.6, 1.0 + 0.2 * d)          # down to −40%
    return 1.0


def height_reach(field, pos) -> int:
    """Extra ranged tiles (and sight) from standing high (P17.E1)."""
    return max(0, min(MAX_REACH, field.elevation_at(*pos)))
