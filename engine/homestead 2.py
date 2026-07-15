"""Claim a home (P15.7) — a derelict you buy, fix up, and make yours.

The homes system (P9A.3) already flags buildings nobody lives in as
DERELICT. This turns one into a project the player can own:

  1. **Claim** — stand inside an unowned derelict and buy it (a
     size-scaled price). You now own a ruin.
  2. **Repair** — a staged ConstructionProject: press E to shore it up,
     each stage spending timber + stone + a little coin and a couple of
     hours. The final stage clears the derelict flag, restores the
     interior's description, and FURNISHES it — a bed, a hearth, and a
     storage chest are guaranteed.
  3. **Live in it** — sleeping at home rests you Well Rested for free
     (you own the bed), the hearth cooks (P9A.2 furniture), and the
     chest is your own persistent storage (deposit from the I-panel,
     withdraw at the chest).

All state is save-safe with no new save code: ownership rides the
location's `properties` (already serialised), and the project, the
"ready" flag, and the stored goods ride `player.metadata`. One home at
a time keeps it simple.
"""

import logging
from typing import Optional

from engine.furniture import _kind

logger = logging.getLogger("llm_rpg.homestead")

CLAIM_BASE = 40           # gold, before size
SIZE_COST = 3             # gold per interior tile
REPAIR_STAGES = 3
STAGE_GOLD = 15
STAGE_WOOD = 3
STAGE_STONE = 2
STAGE_MINUTES = 120
REST_DURATION = 240       # Well Rested, in minutes (matches the inn)

WOOD_IDS = ("logs", "oak_logs", "yew_logs", "wood", "timber", "plank")
STONE_IDS = ("stone", "cracked_riverstone", "rock", "cut_stone")

# Infrastructure that's derelict (no residents) but is NOT a home you
# could move into — a well or a shrine (P15.12 playtest finding).
NON_DWELLING = {"well", "shrine", "stall", "statue", "fountain",
                "monument", "sign", "gate"}


# ---- ownership / lookup --------------------------------------------

def home_name(player) -> Optional[str]:
    return (getattr(player, "metadata", {}) or {}).get("home")


def owns_home(player) -> bool:
    return home_name(player) is not None


def is_ready(player) -> bool:
    """True once the repair project has finished."""
    return owns_home(player) and \
        bool(player.metadata.get("home_ready"))


def _loc_named(engine, name):
    for loc in engine.world.locations:
        if loc.name == name:
            return loc
    return None


def inside_home(engine):
    """The player's own home location if they are standing in it, else
    None (works inside the interior or on the overworld footprint)."""
    p = engine.player
    hn = home_name(p)
    if not hn:
        return None
    loc = engine.player_location()
    return loc if loc is not None and loc.name == hn else None


# ---- claiming -------------------------------------------------------

def claim_price(loc) -> int:
    return CLAIM_BASE + loc.width * loc.height * SIZE_COST


def _is_dwelling(loc) -> bool:
    """A derelict you could actually live in — not a well or a shrine."""
    try:
        from world.blueprints import blueprint_for_location
        bp = blueprint_for_location(loc.name)
        kind = getattr(bp, "kind", "") if bp else ""
    except Exception:
        kind = ""
    return kind not in NON_DWELLING


def claimable_here(engine):
    """The derelict HOME the player may buy right now, or None."""
    if owns_home(engine.player):
        return None
    loc = engine.player_location()
    if loc is None:
        return None
    if not loc.get_property("derelict", False):
        return None
    if loc.get_property("owner"):
        return None
    if not _is_dwelling(loc):
        return None
    return loc


def claim(engine) -> Optional[str]:
    p = engine.player
    if owns_home(p):
        return f"You already keep a home at {home_name(p)}."
    loc = claimable_here(engine)
    if loc is None:
        return None
    price = claim_price(loc)
    if getattr(p, "gold", 0) < price:
        return (f"The {loc.name} could be yours for {price}g — "
                f"you're short {price - p.gold}g.")
    p.gold -= price
    loc.add_property("owner", "player")
    p.metadata["home"] = loc.name
    p.metadata["home_project"] = {"stage": 0, "total": REPAIR_STAGES}
    p.metadata["home_ready"] = False
    msg = (f"[Home] You buy the derelict {loc.name} for {price}g. "
           f"It needs work — bring timber and stone, press E to repair.")
    engine.memory_manager.add_event(msg)
    return msg


# ---- the repair project --------------------------------------------

def repairable_here(engine):
    loc = inside_home(engine)
    if loc is None:
        return None
    return None if is_ready(engine.player) else loc


def _count(player, ids) -> int:
    return sum(getattr(it, "quantity", 1) for it in player.inventory
               if getattr(it, "id", "") in ids)


def _consume(player, ids, n) -> bool:
    for it in list(player.inventory):
        if n <= 0:
            break
        if getattr(it, "id", "") in ids:
            q = getattr(it, "quantity", 1)
            take = min(q, n)
            it.quantity = q - take
            n -= take
            if it.quantity <= 0:
                player.inventory.remove(it)
    return n <= 0


def repair(engine) -> Optional[str]:
    loc = repairable_here(engine)
    if loc is None:
        return None
    p = engine.player
    proj = p.metadata.get("home_project") or {"stage": 0,
                                              "total": REPAIR_STAGES}
    have_w, have_s = _count(p, WOOD_IDS), _count(p, STONE_IDS)
    if have_w < STAGE_WOOD or have_s < STAGE_STONE or \
            getattr(p, "gold", 0) < STAGE_GOLD:
        return (f"[Home] To work on the {loc.name} you need "
                f"{STAGE_WOOD} timber ({have_w}), {STAGE_STONE} stone "
                f"({have_s}) and {STAGE_GOLD}g.")
    _consume(p, WOOD_IDS, STAGE_WOOD)
    _consume(p, STONE_IDS, STAGE_STONE)
    p.gold -= STAGE_GOLD
    engine.world.advance_time(STAGE_MINUTES)
    proj["stage"] = proj.get("stage", 0) + 1
    p.metadata["home_project"] = proj
    try:   # repairing your home trains Carpentry (P15.9b)
        from engine.skill_progression import train_skill
        train_skill(engine, "carpentry", 60)
    except Exception:
        pass
    if proj["stage"] >= proj.get("total", REPAIR_STAGES):
        return _finish(engine, loc)
    msg = (f"[Home] You shore up the {loc.name} "
           f"(stage {proj['stage']}/{proj['total']}). "
           f"More timber and stone will see it done.")
    engine.memory_manager.add_event(msg)
    return msg


def _finish(engine, loc) -> str:
    p = engine.player
    p.metadata["home_ready"] = True
    loc.add_property("derelict", False)
    inter = engine.interiors.get(loc.name)
    if inter is not None:
        inter.description = (inter.description
                             .replace(" Dust lies thick — no one lives "
                                      "here.", ""))
        if "your own" not in inter.description:
            inter.description += " Yours now — restored, swept, and warm."
        _furnish(engine, inter)
    msg = (f"[Home] The {loc.name} is yours — repaired and warm. "
           f"Sleep here to rest well; the chest keeps your goods safe.")
    engine.memory_manager.add_event(msg)
    return msg


def _furnish(engine, inter) -> None:
    """Guarantee a bed, a hearth, and a storage chest in the finished
    home — placed on any free interior floor tiles."""
    present = {_kind(pc.get("name", "")) for pc in inter.furniture}
    wanted = [("Bed", "bed"), ("Hearth", "hearth"),
              ("Storage Chest", "stash")]
    need = [(nm, kd) for nm, kd in wanted if kd not in present]
    if not need:
        return
    taken = {(pc.get("x"), pc.get("y")) for pc in inter.furniture}
    if inter.door:
        taken.add(tuple(inter.door))
    spots = []
    for y in range(1, max(2, inter.height - 1)):
        for x in range(1, max(2, inter.width - 1)):
            if (x, y) not in taken:
                spots.append((x, y))
    for (nm, _kd), (x, y) in zip(need, spots):
        inter.furniture.append({"name": nm, "x": x, "y": y})


def home_action(engine) -> Optional[str]:
    """The E-key verb inside a ruin/home: repair your own unfinished
    home if you're standing in it, else buy the derelict you're in."""
    if repairable_here(engine) is not None:
        return repair(engine)
    if claimable_here(engine) is not None:
        return claim(engine)
    return None


# ---- storage chest --------------------------------------------------

def _storage(player) -> list:
    return player.metadata.setdefault("home_storage", [])


def stored_names(player) -> list:
    return [d.get("name", "?") for d in _storage(player)]


def deposit(engine, item_name: str) -> str:
    """Move a carried item into the home chest (from the I-panel)."""
    p = engine.player
    if not is_ready(p):
        return "You have no furnished home to store things in."
    for it in list(p.inventory):
        if it.name == item_name or getattr(it, "id", "") == item_name:
            try:
                from characters.equipment import equipped_items
                if it in equipped_items(p):
                    return f"Unequip the {it.name} before storing it."
            except Exception:
                pass
            _storage(p).append(it.to_dict())
            p.inventory.remove(it)
            msg = f"[Home] Stored {it.name} in your chest."
            engine.memory_manager.add_event(msg)
            return msg
    return f"You aren't carrying a {item_name}."


def withdraw(engine, item_name: str) -> str:
    p = engine.player
    store = _storage(p)
    for d in list(store):
        if d.get("name") == item_name or d.get("id") == item_name:
            from engine.carry import can_carry
            if not can_carry(p):
                return "Your pack is full — no room to take that."
            from items.item import Item
            p.inventory.append(Item.from_dict(d))
            store.remove(d)
            msg = f"[Home] You take {d.get('name')} from your chest."
            engine.memory_manager.add_event(msg)
            return msg
    return f"There's no {item_name} in your chest."


def chest_interact(engine) -> Optional[str]:
    """E on your home chest: take the top item back, or report it's
    empty. (Depositing is done from the inventory panel.)"""
    if inside_home(engine) is None or not is_ready(engine.player):
        return None
    names = stored_names(engine.player)
    if not names:
        return ("[Home] Your chest is empty. Store goods from your "
                "pack ([I], then H).")
    top = names[0]
    rest = f" ({len(names) - 1} more inside)" if len(names) > 1 else ""
    return withdraw(engine, top) + rest


# ---- rest -----------------------------------------------------------

def can_rest_home(engine) -> bool:
    return inside_home(engine) is not None and is_ready(engine.player)
