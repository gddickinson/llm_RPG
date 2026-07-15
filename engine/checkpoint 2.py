"""Soulslike death recovery (user-directed) — the game-over, replaced.

Falling to the bottom of the dying ladder (P12.4) no longer ends the run.
Instead everything you carried stays where you fell — a BLOODSTAIN holding
your gold, your pack, and a slice of your XP — and you wake diminished at
the nearest sanctuary (temple, else town). Walk back to the bloodstain to
reclaim it all. Die again before you get there and the fresh fall
OVERWRITES the old stain (the old hoard is lost — the classic soulslike
sting). State lives on `player.metadata["bloodstain"]`, so it round-trips
through a save.

Equipped gear stays on your body; it's the PACK (inventory), carried
coin, and hard-won XP that you have to go earn back.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.checkpoint")

REVIVE_HP_FRACTION = 1.0 / 3.0
RECOVER_HOURS = 4
DEATH_XP_FRACTION = 0.20        # share of XP dropped (never de-levels you)
MARKER = "Bloodstain"


def _region_key(engine) -> str:
    try:
        rx, ry = engine.world_streamer.cw.current_region
        return f"{rx},{ry}"
    except Exception:
        return "0,0"


def has_bloodstain(engine) -> bool:
    return bool(engine.player.metadata.get("bloodstain"))


def bloodstain_pos(engine):
    bs = engine.player.metadata.get("bloodstain")
    return tuple(bs["pos"]) if bs else None


def _take_xp(player) -> int:
    """Skim a fifth of XP for the corpse, but never below the current
    level's floor — a fall costs you progress, not a level."""
    from engine.leveling import xp_threshold, level_for_xp
    xp = int(player.metadata.get("xp", 0))
    lvl = getattr(player, "level", None) or level_for_xp(xp)
    floor = xp_threshold(lvl)
    held = min(int(xp * DEATH_XP_FRACTION), max(0, xp - floor))
    player.metadata["xp"] = xp - held
    return held


def _clear_marker(engine) -> None:
    bs = engine.player.metadata.get("bloodstain")
    if not bs:
        return
    try:
        engine.world.remove_item_from_ground(MARKER, bs["pos"][0],
                                             bs["pos"][1])
    except Exception:
        pass


def fall_and_recover(engine, attacker) -> str:
    """The terminal defeat outcome — always survivable. Drop the pack as
    a bloodstain, wake at sanctuary, take the XP hit."""
    player = engine.player
    site = (int(player.position[0]), int(player.position[1]))

    items = [it.to_dict() for it in list(player.inventory)
             if hasattr(it, "to_dict")]
    gold = int(getattr(player, "gold", 0))

    _clear_marker(engine)                      # a prior stain is overwritten
    held_xp = _take_xp(player)
    player.metadata["bloodstain"] = {
        "pos": [site[0], site[1]], "region": _region_key(engine),
        "gold": gold, "items": items, "xp": held_xp,
    }
    player.inventory = [it for it in player.inventory
                        if not hasattr(it, "to_dict")]
    player.gold = 0
    try:
        engine.world.add_item_to_ground(MARKER, site[0], site[1])
    except Exception:
        pass

    from engine.defeat import _revive, _sanctuary_position
    _revive(engine, hp=max(1, int(player.max_hp * REVIVE_HP_FRACTION)))
    dest = _sanctuary_position(engine)
    try:
        engine.world.map.remove_character(player)
    except Exception:
        pass
    player.position = dest
    engine.world.map.place_character(player, *dest)
    engine.world.advance_time(RECOVER_HOURS * 60)

    try:   # the world remembers where a hero fell (P12.13 bones)
        from engine.bones import record_bones
        record_bones(engine, attacker)
    except Exception as e:
        logger.debug(f"bones record failed: {e}")

    msg = ("Darkness takes you... You wake at a place of sanctuary, "
           f"diminished. Your remains lie where you fell "
           f"({site[0]}, {site[1]}) — return to reclaim them.")
    engine.memory_manager.add_event("[!] " + msg)
    return msg


def reclaim_bloodstain(engine) -> Optional[str]:
    """Standing on your bloodstain (same region, overworld) gives it all
    back — pack, coin, and the lost XP."""
    player = engine.player
    bs = player.metadata.get("bloodstain")
    if not bs:
        return None
    try:
        if engine.active_zone() is not None:
            return None
    except Exception:
        pass
    if bs.get("region") != _region_key(engine):
        return None
    px, py = int(player.position[0]), int(player.position[1])
    if [px, py] != list(bs["pos"]):
        return None

    from items.item import Item
    restored = 0
    for d in bs.get("items", []):
        try:
            player.inventory.append(Item.from_dict(d))
            restored += 1
        except Exception:
            pass
    player.gold = int(getattr(player, "gold", 0)) + int(bs.get("gold", 0))
    player.metadata["xp"] = int(player.metadata.get("xp", 0)) + \
        int(bs.get("xp", 0))
    _clear_marker(engine)
    player.metadata.pop("bloodstain", None)

    msg = (f"You reclaim your remains: {bs.get('gold', 0)}g, "
           f"{restored} item(s), and the knowledge you'd lost.")
    engine.memory_manager.add_event(msg)
    return msg


def tick(engine) -> Optional[str]:
    """Auto-reclaim the moment the player steps onto their bloodstain —
    called from the turn pipeline."""
    if has_bloodstain(engine):
        return reclaim_bloodstain(engine)
    return None
