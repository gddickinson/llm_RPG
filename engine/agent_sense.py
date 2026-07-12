"""Away-agent sensing & eligibility (2026-07-12b) — the small, stateless
predicates the controller reads the world through: is this a foe, is it on
my grid, can I heal, can I shoot. Split from `agent_controller` to hold the
500-line line; pure functions, no state.
"""

_HOSTILE = ("brigand", "troll", "monster")   # matches the game's foe check


def _is_hostile(npc) -> bool:
    return getattr(getattr(npc, "character_class", None), "value", "") \
        in _HOSTILE


def _colocated(zone_name, npc) -> bool:
    """Is `npc` on the SAME grid as a hero whose zone is `zone_name` (or
    None on the overworld)? Perceiving a foe across coordinate spaces is
    what made the away-hero shoot a phantom forever (2026-07-12b)."""
    nz = (getattr(npc, "metadata", {}) or {}).get("zone")
    return nz == zone_name if zone_name else not nz


def _healing_item(char):
    """A drinkable in the bag that mends wounds (id-matched — the heal
    payload isn't on `use_effect`)."""
    for it in getattr(char, "inventory", []):
        try:
            if not it.is_consumable():
                continue
        except Exception:
            continue
        iid = getattr(it, "id", "").lower()
        if "potion" in iid or "heal" in iid or "remedy" in iid:
            return it
    return None


def _knows_heal(char) -> bool:
    m = getattr(char, "metadata", {}) or {}
    return "heal" in m.get("spells_known", []) and m.get("mana", 0) >= 3


def _can_shoot(char) -> bool:
    """A drawn bow is no use without arrows — an agent that dry-fires an
    empty quiver forever just stands and 'shoots' (bug-fix 2026-07-12).
    Require matching ammo unless the weapon is thrown."""
    try:
        from characters.equipment import equipped_weapon
        from items.item import Item
        w = equipped_weapon(char)
        if w is None or not w.is_ranged_weapon():
            return False
        if getattr(w, "weapon_kind", "") == "thrown":
            return True                       # thrown needs no ammo
        ammo = getattr(w, "ammo_type", "")
        if not ammo:
            return True
        return any(isinstance(it, Item) and it.is_ammo()
                   and it.ammo_type == ammo and it.quantity > 0
                   for it in getattr(char, "inventory", []))
    except Exception:
        return False


def _attack_spell(char, dist):
    """The best DAMAGE spell the caster knows, can afford the mana for, and
    that reaches `dist` — its id, or None. Lets a caster away-hero fight
    with magic instead of trading melee blows (M.8c)."""
    meta = getattr(char, "metadata", {}) or {}
    known = meta.get("spells_known", [])
    if not known:
        return None
    mana = meta.get("mana", 0)
    try:
        from engine.spells import SPELL_REGISTRY
    except Exception:
        return None
    # pick the most mana-EFFICIENT reachable spell (damage per mana), so
    # the pool lasts across many fights; a bigger nuke breaks ties
    scored = []
    for sid in known:
        sp = SPELL_REGISTRY.get(sid)
        if sp is None or sp.damage <= 0:
            continue
        if sp.mana_cost > mana or sp.range < dist:
            continue
        scored.append((sp.damage / max(1, sp.mana_cost), sp.damage, sid))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][2]


def _provisioned(char, need: int = 8) -> bool:
    """Enough food in the pack for a REAL camp (a proper half-heal, not a
    hungry doze). Gating rest on this is what keeps a wounded hero from
    sleeping the same fruitless night over and over (M.8a)."""
    total = 0
    for it in getattr(char, "inventory", []):
        eff = getattr(it, "use_effect", None) or {}
        heal = getattr(it, "heal_amount", 0)
        if eff.get("food") and heal > 0:
            total += heal * max(1, getattr(it, "quantity", 1))
            if total >= need:
                return True
    return False
