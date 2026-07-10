"""Furniture with functions (P9A.2) — interiors are places to DO things.

The AW survey's top-ranked port: their `face_tile ==` dispatch, rebuilt
for our Interior furniture dicts (which already render — they just did
nothing). Stand on/beside a piece and press E:

- BED — rest: heal 30% of max HP, once per game day. Doors (P9A.1)
  already gate who can reach a bed; trespass costs come with P9A.4.
- HEARTH — cook: the first cooking recipe you have ingredients for is
  made on the spot (raw trout → cooked trout, …).
- ALTAR — pray, exactly like SHIFT+P at a shrine (the altar overrides
  the holy-place check — you are definitionally somewhere holy).
- SHELVES / BOOKSHELF — read: a rumor or legend surfaces, once a day.
- CHEST / CRATES / BARREL — rummage: once a day per building, a small
  find (a few coins, a common item) or dusty nothing.
- Anvils, bars, counters, pews, stairs give directional flavor (the
  forge points at [K] crafting, the bar at [B] wares…).

No per-piece persistent state: daily cooldowns ride player.metadata,
so saves are free and rebuilt interiors stay consistent.
"""

import random
from typing import Dict, Optional

REST_FRACTION = 0.30
RUMMAGE_CHANCE = 0.45
RUMMAGE_ITEMS = ("potion", "herb_bundle", "bread")

FLAVOR = {
    "bar": "The tavernkeeper nods at you. ([B] to see the wares.)",
    "anvil": "A good anvil. ([K] to craft here.)",
    "forge": "The forge glows hot. ([K] to craft, [R] to repair.)",
    "workbench": "Tools of the smith's trade, neatly kept.",
    "counter": "The counter is polished smooth by years of trade.",
    "pew": "You sit a moment. The quiet does you good.",
    "statue": "A stern saint watches you without eyes.",
    "table": "A sturdy table, ringed with the ghosts of old tankards.",
    "stairs up": "Step onto the stairs to climb them.",
    "stairs down": "Step onto the stairs to descend.",
    "wall rack": "Spears and shields, all accounted for.",
}


def _kind(name: str) -> str:
    low = name.lower()
    if "bed" in low:
        return "bed"
    if "hearth" in low or "fireplace" in low or "stove" in low:
        return "hearth"
    if "altar" in low:
        return "altar"
    if "shel" in low or "book" in low:
        return "shelf"
    if "chest" in low or "crate" in low or "barrel" in low:
        return "stash"
    if "anvil" in low:
        return "anvil"
    if "well" in low:
        return "well"
    if "inscription" in low:
        return "inscription"
    if "sigil" in low:
        return "sigil"
    return low


def piece_near(interior, x: int, y: int) -> Optional[Dict]:
    """The piece underfoot wins; otherwise the first adjacent one."""
    adjacent = None
    for piece in getattr(interior, "furniture", []):
        px, py = piece.get("x", -9), piece.get("y", -9)
        if (px, py) == (x, y):
            return piece
        if adjacent is None and abs(px - x) <= 1 and abs(py - y) <= 1:
            adjacent = piece
    return adjacent


def interact(engine) -> Optional[str]:
    """E beside furniture. None = nothing here (caller falls through)."""
    interior = engine.current_interior
    if interior is None:
        return None
    piece = piece_near(interior, *engine.player.position)
    if piece is None:
        return None
    kind = _kind(piece.get("name", ""))
    if kind == "sigil":
        try:
            return engine.structures.touch_sigil(interior, piece)
        except Exception:
            return "The sigil is cold and inert."
    if kind == "inscription":
        msg = f"The carving reads: \"{piece.get('text', '...')}\""
        engine.memory_manager.add_event(msg)
        return msg
    handler = {"bed": _rest, "hearth": _cook, "altar": _pray,
               "shelf": _read, "stash": _rummage,
               "anvil": _smith, "well": _drink}.get(kind)
    if handler is not None:
        msg = handler(engine, interior)
    else:
        msg = FLAVOR.get(kind)
    if msg:
        engine.memory_manager.add_event(msg)
    return msg


# ------------------------------------------------------------ handlers

def _day(engine) -> int:
    return engine.world.time // (24 * 60)


def _rest(engine, interior) -> str:
    player = engine.player
    if player.metadata.get("bed_rest_day") == _day(engine):
        return "You've already rested today. Nightfall is for sleeping."
    player.metadata["bed_rest_day"] = _day(engine)
    heal = max(1, int(player.max_hp * REST_FRACTION))
    before = player.hp
    player.hp = min(player.max_hp, player.hp + heal)
    engine.world.advance_time(60)
    return (f"You stretch out on the bed and rest an hour "
            f"(+{player.hp - before} HP).")


def _cook(engine, interior) -> str:
    from items.crafting import list_recipes
    counts: Dict[str, int] = {}
    for item in engine.player.inventory:
        iid = getattr(item, "id", "")
        counts[iid] = counts.get(iid, 0) + 1
    for recipe in list_recipes():
        if getattr(recipe, "skill", "") != "cooking":
            continue
        need = recipe.ingredients
        if all(counts.get(iid, 0) >= n for iid, n in need.items()):
            return engine.craft(recipe.output_id)
    return ("The fire crackles invitingly. Bring something raw "
            "to cook — the river has trout.")


def _pray(engine, interior) -> str:
    return engine.pantheon.pray(at_altar=True)


def _read(engine, interior) -> str:
    player = engine.player
    if player.metadata.get("shelf_read_day") == _day(engine):
        return "You've read enough for one day; the letters swim."
    player.metadata["shelf_read_day"] = _day(engine)
    line = None
    try:
        rumors = engine.world_director.rumors
        if rumors:
            line = rumors[-1]
    except Exception:
        pass
    if not line:
        line = "Most of it is inventory ledgers and weather complaints."
    return f"You leaf through the shelves. One page catches your " \
           f"eye: \"{line}\""


def _smith(engine, interior) -> str:
    """E at the anvil: repair every damaged piece you carry (P9A.6)."""
    from engine.durability import repair, repair_cost
    from characters.equipment import equipped_items
    player = engine.player
    candidates = list(equipped_items(player)) + list(player.inventory)
    damaged = [it for it in candidates
               if it is not None and repair_cost(it) > 0]
    if not damaged:
        return "Your gear is in good order. ([K] to craft here.)"
    lines = []
    for item in damaged:
        lines.append(repair(player, item, at_forge=True))
    return " ".join(lines)


def _drink(engine, interior) -> str:
    player = engine.player
    if player.metadata.get("well_drink_day") == _day(engine):
        return "The water is cold and clear. You've had your fill."
    player.metadata["well_drink_day"] = _day(engine)
    player.hp = min(player.max_hp, player.hp + 2)
    return "You draw up the bucket and drink deep (+2 HP)."


def _rummage(engine, interior) -> str:
    player = engine.player
    # Structure chests carry authored/swept treasure (P9.2)
    piece = piece_near(interior, *player.position)
    if piece is not None:
        try:
            msg = engine.structures.loot_chest(interior, piece)
            if msg is not None:
                return msg
        except Exception:
            pass
    marks = player.metadata.setdefault("rummage_days", {})
    if marks.get(interior.name) == _day(engine):
        return "You've already been through everything here today."
    marks[interior.name] = _day(engine)
    rng = random.Random(hash((interior.name, _day(engine))) & 0xffff)
    if rng.random() < RUMMAGE_CHANCE:
        from items.item_registry import create_item
        item = create_item(rng.choice(RUMMAGE_ITEMS))
        if item is not None:
            player.inventory.append(item)
            return f"Tucked at the bottom you find: {item.name}."
    coins = rng.randint(2, 7)
    player.gold = getattr(player, "gold", 0) + coins
    return f"Dust, straw — and {coins} loose coppers."
