"""Away-agent economy (M.8b) — the hero SPENDS instead of hoarding.

When the away-hero is standing by a merchant it deals: it clears its JUNK
loot for coin, and buys the essentials it's short of — a healing potion
when it carries none (which feeds the M.8a recovery loop), and ammunition
when it carries a bow it can't fire. Loot → gold → potions & arrows, the
scavenging turned into readiness.

Pure over (engine, char, merchant); executes through the real
`economy_system` buy/sell (acting-as the hero is set up by the caller).
"""

from engine.agent_sense import _healing_item, _can_shoot

_POTION = ("potion", "heal", "remedy")
_AMMO = ("arrow", "bolt")


def _buyable(engine, char, merchant, keywords):
    """A catalogue item this merchant sells matching a keyword that the
    hero can afford at the real (multiplier-shaped) buy price."""
    sm = getattr(engine, "shop_manager", None)
    if sm is None:
        return None
    try:
        cat = sm.catalog_for(merchant)
    except Exception:
        return None
    for it in getattr(cat, "items", []):
        iid = getattr(it, "id", "").lower()
        if not any(k in iid for k in keywords):
            continue
        try:
            if sm.buy_price(char, it, merchant) <= getattr(char, "gold", 0):
                return it
        except Exception:
            pass
    return None


def _needs_ammo(char) -> bool:
    """Carries a ranged weapon but can't fire it (out of matching ammo)."""
    try:
        from characters.equipment import equipped_weapon
        w = equipped_weapon(char)
        return w is not None and w.is_ranged_weapon() and not _can_shoot(char)
    except Exception:
        return False


def wants_to_trade(engine, char, merchant) -> bool:
    from engine.trade_info import junk_items
    if junk_items(char):
        return True
    if _healing_item(char) is None \
            and _buyable(engine, char, merchant, _POTION):
        return True
    if _needs_ammo(char) and _buyable(engine, char, merchant, _AMMO):
        return True
    return False


def do_trade(engine, char, merchant, deed=None) -> bool:
    """Sell all junk, then buy a potion (if we carry none) and ammo (if we
    can't fire our bow). Returns True if any deal was struck."""
    from engine.trade_info import junk_items
    sm = getattr(engine, "shop_manager", None)
    if sm is None:
        return False
    acted = False
    for it in list(junk_items(char)):
        if sm.sell_for(char, it, merchant):
            acted = True
    if _healing_item(char) is None:
        pot = _buyable(engine, char, merchant, _POTION)
        if pot is not None and sm.buy_for(char, pot, merchant):
            acted = True
    if _needs_ammo(char):
        ammo = _buyable(engine, char, merchant, _AMMO)
        if ammo is not None and sm.buy_for(char, ammo, merchant):
            acted = True
    if acted and deed is not None:
        deed(f"traded with {merchant.name}.")
    return acted
