"""T4.1 away-hero building entry — lights up dormant autoplay features.

The away/agent hero SKIRTS buildings (the freeze-proofing of 2026-07-12b),
so shipped indoor autoplay — a proper inn REST (well-rested), trading with
an INDOOR merchant — never fires. This gives the ACTIVE away-hero a
tight, loop-proof enter → act → exit: when it is badly hurt beside an inn,
or carrying junk beside a shop, it steps inside, does the one thing, and
leaves — then a hard COOLDOWN + a `visited` mark keep it from bouncing.

Only the social, active away-hero (which IS `engine.player`, so its
interior state is real and unmasked by `acting_as`) ever enters;
adventurer NPCs (`social=False`) are skipped. Isolated here to hold the
line and contain the risk in the freeze-prone agent.
"""

from engine import agent_nav as nav

INDOOR_COOLDOWN = 30                 # turns before the hero enters ANY building again
LOW_HP = 0.4                         # badly hurt → an inn bed is worth it
BUNK_COST = 5                        # can't rest at an inn for free
INN_KINDS = ("inn", "tavern")
SHOP_KINDS = ("shop", "store", "smithy", "blacksmith", "market",
              "apothecary", "general", "trader", "emporium")


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _kind_of(loc):
    props = getattr(loc, "properties", None) or {}
    return (props.get("kind") or props.get("type") or "").lower()


def _matches(loc, kinds) -> bool:
    if _kind_of(loc) in kinds:
        return True
    name = (getattr(loc, "name", "") or "").lower()
    return any(w in name for w in kinds)


def _beside_building(engine, char, kinds):
    """The nearest ENTERABLE building of a matching kind whose footprint the
    hero stands within 2 tiles of (i.e. beside its wall/door), or None."""
    interiors = getattr(engine, "interiors", {})
    px, py = char.position
    best, bestd = None, 99
    for loc in getattr(engine.world, "locations", []):
        if loc.name not in interiors or not _matches(loc, kinds):
            continue
        w = getattr(loc, "width", 1)
        h = getattr(loc, "height", 1)
        cx = min(max(px, loc.x), loc.x + w - 1)
        cy = min(max(py, loc.y), loc.y + h - 1)
        d = _dist((px, py), (cx, cy))
        if d <= 2 and d < bestd:
            best, bestd = loc, d
    return best


def _has_junk(char) -> bool:
    try:
        from engine.trade_info import junk_items
        return bool(junk_items(char))
    except Exception:
        return False


def enter_intent(ctrl, engine, char):
    """(loc, task) if the hero should step into a building this turn, else
    None. Gated to the social active hero, off cooldown, on the overworld."""
    if not getattr(ctrl, "social", True):
        return None
    if getattr(ctrl, "_indoor_cd", 0) > 0:
        return None
    if nav.active_zone(engine) is not None:
        return None
    hp = char.hp / max(1, getattr(char, "max_hp", 1))
    if hp < LOW_HP and getattr(char, "gold", 0) >= BUNK_COST:
        loc = _beside_building(engine, char, INN_KINDS)
        if loc is not None:
            return (loc, "rest")
    if _has_junk(char):
        loc = _beside_building(engine, char, SHOP_KINDS)
        if loc is not None:
            return (loc, "trade")
    return None


def _merchant_inside(engine, char):
    """A merchant colocated with the hero in the interior it just entered."""
    from engine.agent_sense import _colocated
    zone = nav.active_zone(engine)
    zname = getattr(zone, "name", None)
    px, py = char.position
    best, bestd = None, 99
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        kls = getattr(getattr(npc, "character_class", None), "value", "")
        if kls not in ("merchant", "shopkeeper", "blacksmith", "trader"):
            continue
        if not _colocated(zname, npc):
            continue
        d = _dist((px, py), tuple(npc.position))
        if d < bestd:
            best, bestd = npc, d
    return best


def inside_plan(ctrl, engine, char):
    """Once inside for a task: do it once, then leave (and set the cooldown
    so we never bounce back in). Returns None if there is no pending task."""
    ind = getattr(ctrl, "indoor", None)
    if ind is None:
        return None
    if not ind.get("acted"):
        ind["acted"] = True
        if ind["task"] == "rest":
            return ("rest",)
        if ind["task"] == "trade":
            m = _merchant_inside(engine, char)
            if m is not None:
                return ("trade", m)
    _leave(ctrl)
    return ("exit_building",)


def _leave(ctrl):
    ind = getattr(ctrl, "indoor", None)
    if ind:
        ctrl.visited.add(ind["loc"])
    ctrl._indoor_cd = INDOOR_COOLDOWN
    ctrl.indoor = None


def on_entered(ctrl, engine, loc, task) -> None:
    """Called by the executor after a SUCCESSFUL enter."""
    ctrl.indoor = {"loc": loc.name, "task": task, "acted": False}


def on_entry_failed(ctrl) -> None:
    """A locked door turned us back — don't retry for a while."""
    ctrl._indoor_cd = INDOOR_COOLDOWN
    ctrl.indoor = None


def tick_cooldown(ctrl) -> None:
    cd = getattr(ctrl, "_indoor_cd", 0)
    if cd > 0:
        ctrl._indoor_cd = cd - 1
