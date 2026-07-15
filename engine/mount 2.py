"""The pack mule (P15.8b) — a beast you buy at a stable to haul your load
and keep good pace on the road.

A mule is bought at a STABLE (the P15.8 road-pace hook made `mounted` the
lever). Owning one: adds +8 carry slots (`carry.capacity`), flips
`mounted` so every SECOND road/bridge step is free (≈2× the road pace),
and trails one step behind you (`mule_follow`, run each move). State lives
on `player.metadata["mule"]`, so it round-trips through a save.

(The KO-able-body-under-ransom mule and the diary-unlocked Stonepine boat
crossing are the noted P15.8c remainder.)
"""

import logging

logger = logging.getLogger("llm_rpg.mount")

MULE_CARRY = 8          # extra pack slots a mule hauls
MULE_COST = 120         # gold at the stable


def has_mule(player) -> bool:
    return bool(getattr(player, "metadata", {}).get("mule"))


def stable_nearby(engine, radius: int = 2) -> bool:
    """The player stands at (or just outside) a stable — where mules are
    bought."""
    px, py = engine.player.position
    for loc in engine.world.locations:
        name = loc.name.lower()
        if "stable" not in name and \
                (loc.properties or {}).get("type") != "stable":
            continue
        if (loc.x - radius <= px <= loc.x + loc.width + radius and
                loc.y - radius <= py <= loc.y + loc.height + radius):
            return True
    return False


def buy_mule(engine, cost: int = MULE_COST) -> str:
    player = engine.player
    if has_mule(player):
        return "You already have a mule at your heel."
    if not stable_nearby(engine):
        return "You'll find no mule to buy without a stable at hand."
    if int(getattr(player, "gold", 0)) < cost:
        return f"A good mule costs {cost}g — your purse won't stretch to it."
    player.gold -= cost
    player.metadata["mule"] = {"pos": list(player.position)}
    player.metadata["mounted"] = True     # roads run 2x with the mule
    msg = (f"You buy a sturdy mule for {cost}g. It'll haul your load and "
           f"keep good pace on the road.")
    engine.memory_manager.add_event(msg)
    return msg


def release_mule(engine) -> str:
    player = engine.player
    if not has_mule(player):
        return "You have no mule to part with."
    player.metadata.pop("mule", None)
    player.metadata["mounted"] = False
    msg = "You part ways with your mule."
    engine.memory_manager.add_event(msg)
    return msg


def try_buy_at_stable(engine) -> bool:
    """The E-key hook: at a stable with nothing underfoot to pick up first,
    buy a mule. Returns True if it handled the key."""
    try:
        if engine.world.get_items_at(*engine.player.position):
            return False
    except Exception:
        return False
    if stable_nearby(engine) and not has_mule(engine.player):
        buy_mule(engine)
        return True
    return False


def mule_position(engine):
    m = engine.player.metadata.get("mule")
    return tuple(m["pos"]) if m else None


def mule_follow(engine, prev_pos) -> None:
    """Run each move: the mule steps onto the tile the player just left,
    so it trails one step behind (P15.8b). No-op without a mule."""
    m = engine.player.metadata.get("mule")
    if not m or prev_pos is None:
        return
    # only trail if the player actually moved
    if tuple(prev_pos) != tuple(engine.player.position):
        m["pos"] = [int(prev_pos[0]), int(prev_pos[1])]
