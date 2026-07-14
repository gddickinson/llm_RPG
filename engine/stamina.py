"""P34.16 run stamina & tiring.

Sprinting (SHIFT-run) costs STAMINA; when it runs out you're WINDED and can only
walk until you catch your breath. How fast you tire depends on the body: your
CONSTITUTION sets the pool, a heavy pack and leg injuries drain it faster, and a
magic enhancement (haste / endurance / a `tireless` flag) lets you run without
tiring at all. Pure-ish over `char.metadata` (rides the save); no per-tick LLM.
"""

from characters.status_effects import has_effect

BASE = 100.0
MIN_RUN = 8.0            # need at least this much to launch a sprint
RECOVER = 28.0          # once emptied you must recover to here (hysteresis)
DRAIN = 7.0             # stamina per sprint stride
REGEN = 4.0             # recovered per turn while not sprinting
ENDURANCE_EFFECTS = ("haste", "endurance", "second_wind", "tireless")


def _mod(score):
    return (int(score) - 10) // 2


def max_stamina(char):
    """The pool — set by CONSTITUTION (a hardy hero runs longer)."""
    con = getattr(char, "constitution", 10) or 10
    return max(45.0, min(220.0, BASE + _mod(con) * 15))


def get(char):
    md = getattr(char, "metadata", None)
    if not isinstance(md, dict):
        return BASE
    if "run_stamina" not in md:
        md["run_stamina"] = max_stamina(char)
    return md["run_stamina"]


def tireless(char):
    """A magic/enhancement bypass — run without ever tiring."""
    md = getattr(char, "metadata", None) or {}
    if md.get("tireless"):
        return True
    return any(has_effect(char, e) for e in ENDURANCE_EFFECTS)


def drain_mult(char, engine=None):
    """>1 tires you FASTER — a heavy pack and injured legs both cost you."""
    mult = 1.0
    try:
        from engine import carry
        cap = max(1, carry.capacity(char))
        frac = carry.used_slots(char) / cap
        if frac > 0.65:
            mult += (frac - 0.65) * 2.0
    except Exception:
        pass
    try:
        from engine.wounds import severity
        mult += severity(char, "legs") * 0.35
    except Exception:
        pass
    return mult


def can_run(char, engine=None):
    if tireless(char):
        return True
    md = getattr(char, "metadata", None) or {}
    if md.get("_winded"):
        return get(char) >= RECOVER
    return get(char) >= MIN_RUN


def spend(char, engine=None):
    """Cost one sprint stride; latch WINDED at empty."""
    if tireless(char):
        return
    md = getattr(char, "metadata", None)
    if not isinstance(md, dict):
        return
    md["run_stamina"] = max(0.0, get(char) - DRAIN * drain_mult(char, engine))
    if md["run_stamina"] <= 0.0:
        md["_winded"] = True


def recover(char, amount=REGEN):
    """Catch your breath (called each non-sprint turn)."""
    md = getattr(char, "metadata", None)
    if not isinstance(md, dict):
        return
    if tireless(char):
        md["run_stamina"] = max_stamina(char)
        md.pop("_winded", None)
        return
    md["run_stamina"] = min(max_stamina(char), get(char) + amount)
    if md.get("_winded") and md["run_stamina"] >= RECOVER:
        md.pop("_winded", None)


def is_winded(char):
    return bool((getattr(char, "metadata", None) or {}).get("_winded"))


def ratio(char):
    return get(char) / max_stamina(char)
