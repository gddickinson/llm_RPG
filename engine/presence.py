"""Interior presence (P9A.7) — who is indoors, and where you see them.

George's follow-up playtest: NPCs drawn on building tiles outside were
absent when he entered, and walls were see-through from the street.
Both are ONE mechanism — an NPC standing within an enterable
building's footprint is INDOORS:

- From the street they are hidden (you can't see through walls; the
  windows/magical-sight refinement can come later).
- When you enter the building they appear inside it — the SAME
  entities, given deterministic zone-local display positions
  (npc_spots first, then free floor tiles), talkable, barterable and
  attackable through `npc_adjacent_to_player`, which every adjacency
  check (talk, hints, shop, melee) now routes through.

The overworld position stays authoritative for the simulation (AI,
schedules, conflict); presence only translates it for display and
reach. No copies, no desync.
"""

from typing import Dict, Optional, Tuple

ADJACENT = 1.5


def building_containing(engine, x: int, y: int) -> Optional[str]:
    """The enterable building whose footprint covers (x, y)."""
    for loc in engine.world.locations:
        if loc.name in getattr(engine, "interiors", {}) and \
                loc.contains(x, y):
            return loc.name
    return None


def is_indoors(engine, npc) -> Optional[str]:
    if npc.id == engine.player.id:
        return None
    return building_containing(engine, *npc.position)


def assign_visitors(engine, interior, loc_name: str) -> Dict:
    """Deterministic zone-local positions for everyone inside."""
    from world.interiors import _free_tiles
    inside = sorted(
        (n for n in engine.npc_manager.npcs.values()
         if n.is_active() and is_indoors(engine, n) == loc_name),
        key=lambda n: n.id)
    spots = list(interior.npc_spots)
    spots += [t for t in _free_tiles(interior)
              if t not in spots and t != interior.door]
    mapping = {}
    for npc, spot in zip(inside, spots):
        mapping[npc.id] = spot
    interior.visitors = mapping
    return mapping


def zone_position(engine, npc) -> Optional[Tuple[int, int]]:
    """npc's display position in the current interior, if present."""
    interior = getattr(engine, "current_interior", None)
    if interior is None:
        return None
    return getattr(interior, "visitors", {}).get(npc.id)


def npc_adjacent_to_player(engine, npc,
                           radius: float = ADJACENT) -> bool:
    """Adjacency that respects walls: indoors uses the interior
    positions; from the street, someone indoors is out of reach."""
    px, py = engine.player.position
    interior = getattr(engine, "current_interior", None)
    if interior is not None:
        zp = zone_position(engine, npc)
        if zp is None and getattr(npc, "metadata", {}).get("zone") == \
                getattr(interior, "name", None):
            zp = npc.position          # zone native (P9.1)
        if zp is None:
            return False
        return ((zp[0] - px) ** 2 + (zp[1] - py) ** 2) ** 0.5 <= radius
    if is_indoors(engine, npc):
        return False
    nx, ny = npc.position
    return ((nx - px) ** 2 + (ny - py) ** 2) ** 0.5 <= radius


EARSHOT_RADIUS = 14


def in_earshot(engine, pos, radius: int = EARSHOT_RADIUS) -> bool:
    """P14.3a (George: 'the event log shows events occurring a long
    distance away'): actor-local events only reach the log when the
    player could plausibly see or hear them."""
    try:
        px, py = engine.player.position
        return max(abs(pos[0] - px), abs(pos[1] - py)) <= radius
    except Exception:
        return True
