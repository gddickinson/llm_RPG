"""Ransom & rescue (P13.2) — the KO economy meets the factions.

SHIFT+G on a knocked-out person's body HOISTS them over your
shoulder: the body weighs BODY_SLOTS of your pack and every step
under the load costs an extra minute and fatigue. SHIFT+G again
sets them down — and WHO is standing beside you decides what that
means:

- A CLERIC or PALADIN adjacent: a RESCUE. They wake at half
  health, press gratitude gold into your hand, remember it warmly
  (+30, faction rep +8). Virtue pays.
- THE FENCE adjacent: a RANSOM. Wulf pays hard coin for a captive
  the brigands can sell back to the watch — the victim saw your
  face (bounty +25, witnessed), their faction despises you a
  little more (-15), and they will remember being sold (weight 9).
- Nobody special: the body is simply set down where you stand.

If the KO wears off mid-carry, they wake in your arms — set down
beside you, confused, giving you the benefit of the doubt (+5).
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.ransom")

BODY_SLOTS = 6
CARRY_EXTRA_MINUTES = 1
RESCUE_GOLD = 15
RESCUE_REL = 30
RESCUE_REP = 8
RANSOM_BASE = 25
RANSOM_PER_LEVEL = 10
RANSOM_REP = -15
RANSOM_BOUNTY = 25


def carrying(engine) -> Optional[object]:
    npc_id = engine.player.metadata.get("carrying_body")
    if not npc_id:
        return None
    return engine.npc_manager.npcs.get(npc_id)


def hoist_or_deliver(engine) -> str:
    """SHIFT+G: pick a body up, or set it down where it matters."""
    if carrying(engine) is not None:
        return _put_down(engine)
    return _hoist(engine)


def _body_here(engine):
    x, y = engine.player.position
    for spot in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1),
                 (x, y - 1)):
        for it in engine.world.get_items_at(*spot):
            if isinstance(it, str) and it.endswith("'s body"):
                name = it[:-7]
                npc = next(
                    (n for n in engine.npc_manager.npcs.values()
                     if n.name == name and not n.is_active()
                     and n.metadata.get("ko_until")), None)
                if npc is not None:
                    return npc, it, spot
    return None, None, None


def _hoist(engine) -> str:
    npc, marker, spot = _body_here(engine)
    if npc is None:
        return "There's no one here to carry."
    from engine.carry import capacity, used_slots
    if used_slots(engine.player) + BODY_SLOTS > capacity(engine.player):
        return (f"You need {BODY_SLOTS} free pack slots' worth of "
                f"strength to shoulder {npc.name}.")
    engine.world.remove_item_from_ground(marker, *spot)
    engine.player.metadata["carrying_body"] = npc.id
    msg = (f"You heave {npc.name} over your shoulder. "
           f"(SHIFT+G to set them down — beside a priest to rescue, "
           f"beside the fence to ransom.)")
    engine.memory_manager.add_event(msg)
    return msg


def _adjacent_of(engine, classes=(), fence=False):
    try:
        from engine.presence import npc_adjacent_to_player
    except Exception:
        return None
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        if fence and not npc.metadata.get("fence"):
            continue
        if classes and getattr(npc.character_class, "value", "") \
                not in classes:
            continue
        if npc_adjacent_to_player(engine, npc, 1.5):
            return npc
    return None


def _place_beside(engine, npc) -> None:
    from world.world_map import TerrainType
    wmap = engine.world.map
    px, py = engine.player.position
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = px + dx, py + dy
        if 0 <= nx < wmap.width and 0 <= ny < wmap.height and \
                wmap.terrain[ny][nx] not in (
                    TerrainType.WATER, TerrainType.MOUNTAIN,
                    TerrainType.BUILDING) and \
                wmap.get_character_at(nx, ny) is None:
            npc.position = (nx, ny)
            return
    npc.position = (px, py)


def _put_down(engine) -> str:
    npc = carrying(engine)
    engine.player.metadata.pop("carrying_body", None)
    if npc is None:
        return "Your shoulders are empty."
    healer = _adjacent_of(engine, classes=("cleric", "paladin"))
    if healer is not None:
        return _rescue(engine, npc, healer)
    fence = _adjacent_of(engine, fence=True)
    if fence is not None:
        return _ransom(engine, npc, fence)
    x, y = engine.player.position
    engine.world.add_item_to_ground(f"{npc.name}'s body", x, y)
    npc.position = (x, y)
    msg = f"You set {npc.name} down, gently enough."
    engine.memory_manager.add_event(msg)
    return msg


def _rescue(engine, npc, healer) -> str:
    npc.metadata.pop("ko_until", None)
    npc.status = "alive"
    npc.hp = max(1, npc.max_hp // 2)
    _place_beside(engine, npc)
    engine.world.map.place_character(npc, *npc.position)
    engine.player.gold += RESCUE_GOLD
    npc.modify_relationship(engine.player.id, RESCUE_REL)
    try:
        from characters.factions import (Faction, faction_of_class,
                                         modify_rep)
        fac = faction_of_class(
            getattr(npc.character_class, "value", ""))
        if fac != Faction.NEUTRAL:
            modify_rep(engine.player, fac, RESCUE_REP)
    except Exception:
        pass
    try:
        from engine.npc_memory import remember
        remember(npc, f"{engine.player.name} carried me to "
                      f"{healer.name} when I was beaten senseless.",
                 8, engine.world.time)
    except Exception:
        pass
    msg = (f"{healer.name} takes {npc.name} from your shoulders. "
           f"They come to, gripping your hand — {RESCUE_GOLD}g "
           f"pressed into it. Word of this will travel.")
    engine.memory_manager.add_event(msg)
    return msg


def _ransom(engine, npc, fence) -> str:
    price = RANSOM_BASE + RANSOM_PER_LEVEL * getattr(npc, "level", 1)
    engine.player.gold += price
    npc.modify_relationship(engine.player.id, -60)
    fx, fy = fence.position
    npc.position = (fx, fy)
    engine.world.add_item_to_ground(f"{npc.name}'s body", fx, fy)
    try:
        from characters.factions import (Faction, faction_of_class,
                                         modify_rep)
        fac = faction_of_class(
            getattr(npc.character_class, "value", ""))
        if fac != Faction.NEUTRAL:
            modify_rep(engine.player, fac, RANSOM_REP)
    except Exception:
        pass
    try:
        engine.law.add_bounty(RANSOM_BOUNTY,
                              reason=f"{npc.name} was sold to the "
                                     f"brigands", witnessed=True)
    except Exception:
        pass
    try:
        from engine.npc_memory import remember
        remember(npc, f"{engine.player.name} SOLD me to the "
                      f"brigands while I lay senseless.", 9,
                 engine.world.time)
    except Exception:
        pass
    msg = (f"{fence.name} counts out {price}g and has {npc.name} "
           f"bundled into the back room. \"The watch pays better "
           f"than you'd think to get their own back.\"")
    engine.memory_manager.add_event(msg)
    return msg


def wake_in_arms(engine, npc) -> bool:
    """Called by wake_the_fallen when the sleeper is on your back."""
    if engine.player.metadata.get("carrying_body") != npc.id:
        return False
    engine.player.metadata.pop("carrying_body", None)
    npc.metadata.pop("ko_until", None)
    npc.status = "alive"
    npc.hp = max(1, npc.max_hp // 3)
    _place_beside(engine, npc)
    engine.world.map.place_character(npc, *npc.position)
    npc.modify_relationship(engine.player.id, 5)
    engine.memory_manager.add_event(
        f"{npc.name} stirs awake in your arms and finds their own "
        f"feet — confused, but you were carrying them SOMEWHERE, "
        f"and they choose to believe it was somewhere good.")
    return True
