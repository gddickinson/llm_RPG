"""Lightweight pre-game history simulation.

Generates a brief world history: a few "years" of simulated events that
leave traces in the world — a ruined keep, a sacked watchtower, faction
tensions baked into starting reputation, NPC backstory memories.

This is intentionally simple: not a full economy/society simulation,
just enough lore for flavor.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import List, Tuple

from world.world_map import TerrainType
from world.location import Location

logger = logging.getLogger("llm_rpg.history_sim")


@dataclass
class HistoricalEvent:
    year: int
    description: str
    faction_impact: dict = field(default_factory=dict)


EVENT_POOL = [
    ("Bandits sacked an old watchtower by the road.",
     {"brigands": -10, "guards": +5}),
    ("A plague swept the river hamlet; the priest's vigil saved many.",
     {"temple": +10}),
    ("Trolls came down from the mountains and burned a farm.",
     {"monsters": -15, "villagers": +5}),
    ("A merchant prince commissioned the silver blade in Durgan's forge.",
     {"merchants": +5}),
    ("A bardic festival drew folk from every corner; the village prospered.",
     {"bardic": +10, "villagers": +5}),
    ("A goblin raid was repelled at great cost.",
     {"monsters": -10, "villagers": +5}),
    ("The river ran dry one summer; tensions rose with the next harvest.",
     {"merchants": -5}),
    ("A wandering druid blessed the woods, and forage grew thick.",
     {"temple": +5}),
]


def simulate(rng: random.Random = None, years: int = 5) -> List[HistoricalEvent]:
    rng = rng or random.Random()
    n = min(years, len(EVENT_POOL))
    picks = rng.sample(EVENT_POOL, k=n)
    history: List[HistoricalEvent] = []
    for i, (desc, impact) in enumerate(picks):
        history.append(HistoricalEvent(
            year=-(years - i),    # negative years = before campaign
            description=desc,
            faction_impact=impact,
        ))
    return history


def apply_history(engine, events: List[HistoricalEvent]) -> List[str]:
    """Apply historical impact to the engine state. Returns flavor lines."""
    flavor = []
    # Faction reputation shifts
    try:
        from characters.factions import modify_rep, Faction
        for ev in events:
            for fac_name, delta in ev.faction_impact.items():
                try:
                    fac = Faction(fac_name)
                except ValueError:
                    continue
                modify_rep(engine.player, fac, delta)
    except Exception as e:
        logger.warning(f"history rep apply failed: {e}")

    # Carve a ruined building somewhere in the wilderness
    try:
        _add_ruined_keep(engine)
        flavor.append("A ruined keep stands silent at the edge of the wilds.")
    except Exception:
        pass

    # Surface 1-2 history lines in the player's starting memory
    for ev in events[-2:]:
        engine.memory_manager.add_event(
            f"[Lore] Year {ev.year}: {ev.description}")
    return flavor


def _add_ruined_keep(engine) -> None:
    """Place a small ruined building in a wilderness corner."""
    wmap = engine.world.map
    candidates: List[Tuple[int, int]] = []
    # NE quadrant near mountains, far from settlements
    for y in range(2, max(3, wmap.height // 3)):
        for x in range(int(wmap.width * 0.5), wmap.width - 4):
            if wmap.terrain[y][x] != TerrainType.GRASS:
                continue
            # Stay away from existing locations
            loc = engine.world.get_location_at(x, y)
            if loc is not None:
                continue
            candidates.append((x, y))
    if not candidates:
        return
    cx, cy = candidates[len(candidates) // 2]
    for dy in range(0, 2):
        for dx in range(0, 2):
            if (cy + dy) < wmap.height and (cx + dx) < wmap.width:
                wmap.terrain[cy + dy][cx + dx] = TerrainType.BUILDING
    engine.world.add_location(Location(
        "Ruined Keep",
        "Crumbled stone walls, long abandoned. Lore says bandits stripped it.",
        cx, cy, 2, 2,
    ))
