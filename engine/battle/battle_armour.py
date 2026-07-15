"""P17.10 armour, shields & damage types — the protection layer (pure).

The flat `defense` number becomes three things an archetype can opt into,
all data-driven (`data/battles/armour.json`) and all OPTIONAL — an
archetype naming none of them behaves exactly as it did before:

- ARMOUR (`armour_type` → a resist table). Mail shrugs a slash but an
  arrow or a pick (pierce) punches straight through it; plate turns both
  blade and point, yet a mace's blunt shock transfers through regardless.
  This is what finally lets heavy cavalry ride out an arrow-storm.
- a SHIELD (`shield: true`) — a FRONT-ARC bonus to the defender's
  dodge/parry DC, worth MORE against arrows than blades (you catch shafts
  on it, but a flanker steps around it).
- WEIGHT — armour and a shield slow the wearer: a tax on `speed`.

Zero state; `battle_ai.attack` and `Squad.speed` call in.
"""

from engine.battle import battle_data


def _classes() -> dict:
    return battle_data.ARMOUR.get("classes", {})


def _shield_cfg() -> dict:
    return battle_data.ARMOUR.get("shield", {})


def resist_mult(armour_type, damage_type) -> float:
    """Multiplier on damage of `damage_type` that gets through
    `armour_type`. <1 turns the blow, >1 is punched through. Unknown
    pairings (or missing data) are neutral 1.0."""
    cls = _classes().get(armour_type)
    if not cls:
        return 1.0
    return float(cls.get("resist", {}).get(damage_type, 1.0))


def apply_resist(dmg: int, armour_type, damage_type) -> int:
    """Fold the armour-vs-type resist into a damage figure. A blow with
    no declared type, or against unarmoured foes, lands unchanged."""
    if not armour_type or not damage_type:
        return dmg
    return max(1, round(dmg * resist_mult(armour_type, damage_type)))


def shield_dc_bonus(stats: dict, arc: str, ranged: bool) -> int:
    """The defender's shield adds to the to-hit DC only across its FRONT
    arc — and blocks arrows better than blades. 0 from the flank/rear or
    with no shield."""
    if not stats.get("shield") or arc != "front":
        return 0
    cfg = _shield_cfg()
    return int(cfg.get("ranged", 4) if ranged else cfg.get("melee", 2))


def weight_of(stats: dict) -> float:
    """Total carried weight — armour class + shield. 0 for the unarmoured
    (so speed is untouched)."""
    w = 0.0
    cls = _classes().get(stats.get("armour_type"))
    if cls:
        w += float(cls.get("weight", 0))
    if stats.get("shield"):
        w += float(_shield_cfg().get("weight", 0))
    return w


def speed_penalty(stats: dict) -> float:
    """Speed lost to the weight carried (0 for the unarmoured)."""
    tax = float(battle_data.ARMOUR.get("weight_tax", 0.0))
    return weight_of(stats) * tax
