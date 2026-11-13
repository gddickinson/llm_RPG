"""Tolerant anchors for module-pack structures.

A pack structure names the place it attaches to (`attach_to`, e.g. the sample
`smugglers_cache` pack's "Old Farmhouse"). That place exists in the classic
world but not in every world kind (the combined New Game world has "Oakvale
Farmhouse N" instead), so the pack used to be refused. The DM charter still
refuses an unknown anchor for the DM's OWN structures; only authored packs go
through `resolve_anchor` first:

1. a place whose name contains the anchor (what the structure builder matches);
2. else a building of the same KIND (the anchor's last word, e.g. "farmhouse"),
   preferring one nobody lives in and whose name no other place contains (the
   builder matches by substring);
3. else plant a small new building of that name on open ground.
"""
import logging
import random
from typing import Optional

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.pack_anchor")
MIN_FROM_SPAWN = 12


def _kind_word(anchor: str) -> str:
    words = anchor.lower().split()
    return words[-1] if words else ""


def _matches_kind(loc, word: str) -> bool:
    p = loc.properties or {}
    return word in loc.name.lower() or p.get("kind") == word or p.get("type") == word


def _unique_name(engine, loc) -> bool:
    low = loc.name.lower()
    return not any(o is not loc and low in o.name.lower() for o in engine.world.locations)


def _occupied(engine, loc) -> bool:
    homes = getattr(engine, "homes", None)
    try:
        return bool(homes and homes.occupants_of(loc.name))
    except Exception:
        return False


def _plant(engine, anchor: str, word: str) -> Optional[str]:
    """A 2x2 building called `anchor` on open grass, away from the player and every named place."""
    from world.location import Location
    wmap = engine.world.map
    try:
        sx, sy = engine.player.position
    except Exception:
        sx, sy = wmap.width // 2, wmap.height // 2
    taken = set()
    for loc in engine.world.locations:
        for y in range(loc.y - 1, loc.y + max(1, loc.height) + 1):
            for x in range(loc.x - 1, loc.x + max(1, loc.width) + 1):
                taken.add((x, y))
    spots = []
    for y in range(2, wmap.height - 3):
        for x in range(2, wmap.width - 3):
            if abs(x - sx) + abs(y - sy) < MIN_FROM_SPAWN:
                continue
            block = [(x + dx, y + dy) for dx in (-1, 0, 1, 2) for dy in (-1, 0, 1, 2)]
            if all(wmap.terrain[by][bx] == TerrainType.GRASS and (bx, by) not in taken
                   and (bx, by) not in wmap.characters for bx, by in block):
                spots.append((x, y))
    if not spots:
        return None
    x, y = random.Random(random.getrandbits(64)).choice(spots)
    for dy in (0, 1):
        for dx in (0, 1):
            wmap.set_terrain(x + dx, y + dy, TerrainType.BUILDING)
    loc = Location(anchor, f"A lonely {word} standing on its own.", x, y, 2, 2)
    loc.add_property("type", word)
    loc.add_property("kind", word)
    engine.world.add_location(loc)
    return anchor


def resolve_anchor(engine, anchor: str) -> Optional[str]:
    """The place name a pack structure should attach to (see the module docstring), or None."""
    if not anchor:
        return None
    low = anchor.lower()
    if any(low in loc.name.lower() for loc in engine.world.locations):
        return anchor
    word = _kind_word(anchor)
    cands = [loc for loc in engine.world.locations if word and _matches_kind(loc, word) and _unique_name(engine, loc)
             and getattr(engine.interiors.get(loc.name), "structure_id", None) is None]
    if cands:
        free = [loc for loc in cands if not _occupied(engine, loc)] or cands
        pick = random.Random(random.getrandbits(64)).choice(free)
        logger.info("pack anchor '%s' -> existing %s '%s'", anchor, word, pick.name)
        return pick.name
    name = _plant(engine, anchor, word or "building")
    if name:
        logger.info("pack anchor '%s' planted as a new %s", anchor, word)
    return name
