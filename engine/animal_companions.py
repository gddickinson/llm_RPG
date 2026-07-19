"""Animal companions (George: companion & hunting animals for all).

TAME an adjacent wild animal (a Hunting check, eased by a food lure) and
it joins your PARTY — a guardian (wolf, boar, aurochs…) that fights at
your side, or a hunter (fox, deer) that lends you an edge against beasts.
A wild horse (mustang) is tamed as a MOUNT instead.

Reuses everything: the tamed beast IS the same ANIMAL Character (already
rendered by the creature renderer, already in `npc_manager`) — re-flagged
friendly, stripped of its wildlife instincts, given natural weapons, and
added to `companion_manager.party`, so the companion AI walks it and
throws it into the fight for free. State on the character's metadata +
the party list, so it rides the save.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.animal_companions")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data",
                     "animal_companions.json")
_D = None
BEAST_CAP = 2                 # how many animal companions you can keep
TAME_BASE = 10                # Hunting + this must meet the species dc
FOOD_EASE = 4                 # a food lure lowers the dc by this


def _data():
    global _D
    if _D is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _D = json.load(fh)
        except Exception as e:                       # pragma: no cover
            logger.info(f"Animal companion data unavailable: {e}")
            _D = {"companions": {}, "as_mount": {}, "food_items": []}
    return _D


def _species_of(ch):
    return (getattr(ch, "metadata", None) or {}).get("species", "")


def companion_spec(species):
    return _data()["companions"].get(species)


def mount_for(species):
    return _data()["as_mount"].get(species)


def is_wild(ch) -> bool:
    return bool((getattr(ch, "metadata", None) or {}).get("wildlife"))


def tameable(ch):
    """The plan for taming this creature: ('companion', spec) / ('mount',
    kind) / None."""
    if not is_wild(ch):
        return None
    sp = _species_of(ch)
    spec = companion_spec(sp)
    if spec is not None:
        return ("companion", spec)
    m = mount_for(sp)
    if m is not None:
        return ("mount", m)
    return None


def has_food(player):
    foods = set(_data().get("food_items", []))
    for it in getattr(player, "inventory", []):
        iid = (getattr(it, "id", "") or "").lower()
        if iid in foods or any(f in iid for f in ("bread", "meat", "ration",
                                                  "jerky", "fish")):
            return it
    return None


def _hunting(player):
    try:
        from engine.skill_progression import get_skill_level
        return get_skill_level(player, "hunting")
    except Exception:
        return 0


def beast_companions(engine):
    party = getattr(engine.companion_manager, "party", [])
    out = []
    for cid in party:
        ch = engine.npc_manager.get_npc(cid)
        if ch is not None and (ch.metadata or {}).get("beast_companion"):
            out.append(ch)
    return out


def owner_hunting_bonus(engine, target) -> int:
    """The player's bonus damage vs a beast from a hunter companion."""
    klass = getattr(getattr(target, "character_class", None), "value", "")
    if klass not in ("monster", "animal", "beast"):
        return 0
    total = 0
    for ch in beast_companions(engine):
        sp = companion_spec(_species_of(ch)) or {}
        total += int(sp.get("hunt_bonus", 0))
    return total


def nearest_tameable(engine):
    """An adjacent wild animal the player could tame, or None."""
    px, py = engine.player.position
    best = None
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active() or tameable(npc) is None:
            continue
        nx, ny = npc.position
        if max(abs(nx - px), abs(ny - py)) <= 1:
            return npc
    return best


def tame(engine, wild_char) -> str:
    plan = tameable(wild_char)
    if plan is None:
        return "That creature won't be tamed."
    player = engine.player
    food = has_food(player)
    if food is None:
        return "You've no food to gently win it over."
    kind, spec = plan
    dc = (spec.get("dc", 12) if kind == "companion" else 12) - FOOD_EASE
    if _hunting(player) + TAME_BASE < dc:
        # a lost lure, and the beast bolts
        _consume(player, food)
        _flee(wild_char)
        return (f"The {wild_char.name} snatches the food and bolts — you "
                f"need a surer hand (more Hunting) to tame its kind.")
    _consume(player, food)
    if kind == "mount":
        return _tame_as_mount(engine, wild_char, spec)
    return _tame_as_companion(engine, wild_char, spec)


def _tame_as_companion(engine, ch, spec) -> str:
    if len(beast_companions(engine)) >= BEAST_CAP:
        return f"You can keep no more than {BEAST_CAP} animal companions."
    m = ch.metadata
    m.pop("wildlife", None)
    m.pop("timid", None)
    m.pop("preys_on", None)
    m["beast_companion"] = True
    m["role"] = spec.get("role", "guardian")
    m["natural_damage"] = spec.get("damage", 4)
    m["owner"] = engine.player.id
    try:
        ch.faction = getattr(engine.player, "faction", "neutral")
    except Exception:
        pass
    _drop_from_wildlife(engine, ch.id)
    if ch.id not in engine.companion_manager.party:
        engine.companion_manager.party.append(ch.id)
    engine.memory_manager.add_event(
        f"[Companion] You tame {ch.name} — {spec.get('desc', 'a loyal beast')}"
        f" — and it falls in at your side.")
    return f"{ch.name} is now your animal companion."


def _tame_as_mount(engine, ch, kind) -> str:
    player = engine.player
    try:
        from engine.mounts import mount_spec, traverses
        sp = mount_spec(kind) or {}
        player.metadata["mount"] = {"kind": kind,
                                    "pos": list(player.position)}
        player.metadata["mounted"] = True
        tv = traverses(kind)
        if tv:
            player.metadata["mount_traverses"] = tv
    except Exception:
        player.metadata["mount"] = {"kind": kind, "pos": list(player.position)}
    _drop_from_wildlife(engine, ch.id)
    try:
        engine.npc_manager.remove_npc(ch.id)
    except Exception:
        pass
    engine.memory_manager.add_event(
        f"[Companion] You break the wild {ch.name} to the saddle — a "
        f"{kind.replace('_', ' ')} to ride.")
    return f"You tame the wild horse into a {kind.replace('_', ' ')} mount."


def _consume(player, item):
    try:
        from engine.item_use import _remove_one
        _remove_one(player, item)
    except Exception:
        try:
            player.inventory.remove(item)
        except ValueError:
            pass


def _flee(ch):
    try:
        from engine import anim
        anim.emote(ch, "startle")
    except Exception:
        pass


def _drop_from_wildlife(engine, cid):
    ws = getattr(engine, "wildlife", None)
    if ws is None:
        return
    for attr in ("roster", "nearby", "animals", "_animals"):
        coll = getattr(ws, attr, None)
        try:
            if isinstance(coll, dict):
                coll.pop(cid, None)
            elif isinstance(coll, list) and cid in coll:
                coll.remove(cid)
        except Exception:
            pass


def try_tame(engine) -> str:
    """E-key hook: tame the nearest adjacent wild animal."""
    ch = nearest_tameable(engine)
    if ch is None:
        return ""
    return tame(engine, ch)
