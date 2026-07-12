"""P28.2a — mounts of every kind (data-driven).

Generalises the P15.8b pack mule to a ROSTER in `data/mounts.json`: mule,
donkey, horse, war-horse, elephant, magic carpet… each with extra carry,
cost, road speed, where it's sold, the terrain it can cross (P28.2b), and
combat/trample/flight flags. "Basically anything can serve as a mount" — the
data decides.

The active mount rides on `player.metadata["mount"]` (`{kind, pos}`), and this
layer HONOURS the legacy `player.metadata["mule"]` flag too, so old saves and
the P15.8b mule path keep working. `carry.capacity` and the move-follow hook
read this layer instead of the mule constant.
"""

import logging

logger = logging.getLogger("llm_rpg.mounts")

_MOUNTS = None

# P28.2c mount care — loyalty like the P12.14 pet
LOYALTY_MAX = 20
LOYALTY_START = 10


def _load() -> dict:
    global _MOUNTS
    if _MOUNTS is None:
        try:
            from items.data_loader import load_data_file
            _MOUNTS = load_data_file("mounts.json").get("mounts", {}) or {}
        except Exception as e:
            logger.debug(f"mounts.json: {e}")
            _MOUNTS = {}
    return _MOUNTS


# ---- roster queries (pure) -----------------------------------------

def all_mounts() -> dict:
    return _load()


def mount_spec(kind: str) -> dict:
    return _load().get(kind, {})


def carry_of(kind: str) -> int:
    return int(mount_spec(kind).get("carry", 0))


def cost_of(kind: str) -> int:
    return int(mount_spec(kind).get("cost", 0))


def speed_of(kind: str) -> float:
    return float(mount_spec(kind).get("speed_mult", 1.0))


def sold_at(kind: str) -> str:
    return mount_spec(kind).get("sold_at", "stable")


def traverses(kind: str) -> tuple:
    return tuple(mount_spec(kind).get("traverses", ()))


def display_name(kind: str) -> str:
    return mount_spec(kind).get("name", kind)


# ---- the ridden mount ----------------------------------------------

def active_mount(player) -> str:
    """The kind of mount the player rides now, or None. Honours the generic
    `mount` metadata AND the legacy P15.8b `mule` flag."""
    meta = getattr(player, "metadata", {}) or {}
    m = meta.get("mount")
    if isinstance(m, dict) and m.get("kind"):
        return m["kind"]
    if meta.get("mule"):
        return "mule"
    return None


def carry_bonus(player) -> int:
    kind = active_mount(player)
    return carry_of(kind) if kind else 0


def mount_position(engine):
    meta = getattr(engine.player, "metadata", {}) or {}
    m = meta.get("mount")
    if isinstance(m, dict) and m.get("pos"):
        return tuple(m["pos"])
    mule = meta.get("mule")
    if isinstance(mule, dict) and mule.get("pos"):
        return tuple(mule["pos"])
    return None


def _seller_nearby(engine, kind_word: str, radius: int = 2) -> bool:
    """A location of the mount's `sold_at` kind (stable/market/…) is at hand."""
    px, py = engine.player.position
    for loc in engine.world.locations:
        name = (loc.name or "").lower()
        props = loc.properties or {}
        if kind_word in name or props.get("type") == kind_word:
            if (loc.x - radius <= px <= loc.x + loc.width + radius and
                    loc.y - radius <= py <= loc.y + loc.height + radius):
                return True
    return False


def buy_mount(engine, kind: str) -> str:
    """Buy a mount of `kind` at the right seller. Player-facing line."""
    player = engine.player
    spec = mount_spec(kind)
    if not spec:
        return f"There's no such beast as a {kind} to buy."
    if active_mount(player):
        return "You already have a mount at your heel."
    where = sold_at(kind)
    if not _seller_nearby(engine, where):
        return (f"You'll find no {display_name(kind)} without "
                f"a {where} at hand.")
    cost = cost_of(kind)
    if int(getattr(player, "gold", 0)) < cost:
        return (f"A {display_name(kind)} costs {cost}g — "
                f"your purse won't stretch to it.")
    player.gold -= cost
    player.metadata["mount"] = {
        "kind": kind, "pos": list(player.position),
        "loyalty": LOYALTY_START,
        "fed_day": engine.world.time // (24 * 60)}
    player.metadata["mounted"] = True
    player.metadata.pop("mule", None)          # the generic slot supersedes it
    tv = list(traverses(kind))                 # P28.2b terrain crossings
    if tv:
        player.metadata["mount_traverses"] = tv
    else:
        player.metadata.pop("mount_traverses", None)
    msg = f"You buy {display_name(kind)} for {cost}g."
    engine.memory_manager.add_event(msg)
    return msg


def release_mount(engine) -> str:
    player = engine.player
    if not active_mount(player):
        return "You have no mount to part with."
    player.metadata.pop("mount", None)
    player.metadata.pop("mule", None)
    player.metadata.pop("mount_traverses", None)
    player.metadata["mounted"] = False
    msg = "You part ways with your mount."
    engine.memory_manager.add_event(msg)
    return msg


def mount_follow(engine, prev_pos) -> None:
    """Run each move: the mount steps onto the tile the player just left, so it
    trails one step behind. Handles the generic mount AND the legacy mule."""
    meta = getattr(engine.player, "metadata", {}) or {}
    m = meta.get("mount")
    if not (isinstance(m, dict) and m.get("pos")):
        m = meta.get("mule")
    if not (isinstance(m, dict) and prev_pos is not None):
        return
    if tuple(prev_pos) != tuple(engine.player.position):
        m["pos"] = [int(prev_pos[0]), int(prev_pos[1])]


# ---- P28.2c lifecycle & care ---------------------------------------

def _mount_meta(player):
    """The active mount's state dict (generic `mount`, else legacy `mule`)."""
    meta = getattr(player, "metadata", {}) or {}
    m = meta.get("mount")
    if isinstance(m, dict):
        return m
    m = meta.get("mule")
    return m if isinstance(m, dict) else None


def mount_loyalty(player) -> int:
    m = _mount_meta(player)
    return int(m.get("loyalty", LOYALTY_START)) if m else 0


def is_riding(player) -> bool:
    """Mounted (the road-pace lever on) WITH a mount to hand."""
    meta = getattr(player, "metadata", {}) or {}
    return bool(active_mount(player)) and bool(meta.get("mounted"))


def dismount(engine) -> str:
    """Step down and lead the mount on foot — keeps it, drops the road pace."""
    player = engine.player
    if not active_mount(player):
        return "You have no mount to dismount."
    player.metadata["mounted"] = False
    return "You dismount and lead your mount on foot."


def remount(engine) -> str:
    player = engine.player
    if not active_mount(player):
        return "You have no mount to ride."
    player.metadata["mounted"] = True
    return "You swing back into the saddle."


def _a_food(player):
    for it in getattr(player, "inventory", []):
        eff = getattr(it, "use_effect", None) or {}
        if isinstance(eff, dict) and eff.get("food") \
                and getattr(it, "heal_amount", 0) > 0:
            return it
    try:
        from engine.food import is_food
        for it in getattr(player, "inventory", []):
            if is_food(it):
                return it
    except Exception:
        pass
    return None


def feed_mount(engine) -> str:
    """Feed the mount to build loyalty (like the P12.14 pet treat) — spends a
    food item, +1 loyalty, and marks it fed today so the night isn't neglect."""
    player = engine.player
    m = _mount_meta(player)
    if m is None:
        return "You have no mount to feed."
    food = _a_food(player)
    if food is None:
        return "You've nothing to feed your mount."
    if getattr(food, "quantity", 1) > 1:
        food.quantity -= 1
    else:
        try:
            player.inventory.remove(food)
        except ValueError:
            pass
    m["loyalty"] = min(LOYALTY_MAX, mount_loyalty(player) + 1)
    m["fed_day"] = engine.world.time // (24 * 60)
    name = display_name(active_mount(player))
    msg = (f"You feed your {name} — it nickers, content. "
           f"(loyalty {m['loyalty']}/{LOYALTY_MAX})")
    engine.memory_manager.add_event(msg)
    return msg


def run_night(engine) -> None:
    """Nightly: an unfed mount's loyalty slips a point; at 0 it bolts by
    morning (the P12.14 pet-neglect pattern)."""
    player = getattr(engine, "player", None)
    if player is None:
        return
    m = _mount_meta(player)
    if m is None:
        return
    today = engine.world.time // (24 * 60)
    if m.get("fed_day") == today:
        return                               # fed today — no neglect
    loy = mount_loyalty(player) - 1
    if loy <= 0:
        name = display_name(active_mount(player))
        release_mount(engine)
        try:
            engine.memory_manager.add_event(
                f"Your {name} is gone by morning — "
                f"neglect wore the bond through.")
        except Exception:
            pass
        return
    m["loyalty"] = loy
