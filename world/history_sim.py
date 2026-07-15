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
    event_id: str = ""
    relic_id: str = ""
    relic_place: str = ""     # placement keyword
    legend: str = ""          # revealed when the relic is found


# (id, description, impact, relic item, placement, legend)
EVENT_POOL = [
    ("watchtower", "Bandits sacked an old watchtower by the road.",
     {"brigands": -10, "guards": +5}, "watchman_signet", "keep",
     "The Sack of the Watchtower: the garrison held two nights before the "
     "bandits fired the stair. The watch-captain's signet was never "
     "recovered — until now."),
    ("plague", "A plague swept the river hamlet; the priest's vigil saved many.",
     {"temple": +10}, "vigil_candle", "chapel",
     "The Forty-Night Vigil: Brother Anselm burned a candle for every soul "
     "in the hamlet and prayed until the fever broke. The stubs were kept "
     "as charms."),
    ("troll_farm", "Trolls came down from the mountains and burned a farm.",
     {"monsters": -15, "villagers": +5}, "charred_doll", "forest",
     "The Burning of Hearthfield Farm: the family fled through the forest "
     "by night. What the trolls left behind, the ash kept."),
    ("silver_commission", "A merchant prince commissioned the silver blade in Durgan's forge.",
     {"merchants": +5}, "princes_letter", "forge",
     "The Uncollected Commission: a hooded prince paid Durgan triple for a "
     "silver blade and vanished. His sealed letter of credit still waits."),
    ("festival", "A bardic festival drew folk from every corner; the village prospered.",
     {"bardic": +10, "villagers": +5}, "festival_ribbon", "village",
     "The Festival of a Hundred Songs: for three days no one worked and no "
     "one fought. Ribbons from that year still turn up in odd corners."),
    ("goblin_raid", "A goblin raid was repelled at great cost.",
     {"monsters": -10, "villagers": +5}, "goblin_warhorn", "keep",
     "The Raid of the Broken Horn: the goblin warchief blew the charge so "
     "hard his horn split — the defenders laughed, then fought, and held."),
    ("dry_river", "The river ran dry one summer; tensions rose with the next harvest.",
     {"merchants": -5}, "cracked_riverstone", "river",
     "The Dry Summer: the river shrank to a ribbon and neighbors counted "
     "each other's buckets. The stones of the riverbed split in the sun."),
    ("druid_blessing", "A wandering druid blessed the woods, and forage grew thick.",
     {"temple": +5}, "druid_charm", "forest",
     "The Druid's Gift: she stayed one season, wove charms of reed and "
     "stone, and left the woods richer than she found them."),
]


def simulate(rng: random.Random = None, years: int = 5) -> List[HistoricalEvent]:
    rng = rng or random.Random()
    n = min(years, len(EVENT_POOL))
    picks = rng.sample(EVENT_POOL, k=n)
    history: List[HistoricalEvent] = []
    for i, (eid, desc, impact, relic, place, legend) in enumerate(picks):
        history.append(HistoricalEvent(
            year=-(years - i),    # negative years = before campaign
            description=desc,
            faction_impact=impact,
            event_id=eid, relic_id=relic,
            relic_place=place, legend=legend,
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

    # Every event leaves a findable relic in a themed spot (Qud pattern)
    try:
        placed = _place_relics(engine, events)
        logger.info(f"History placed {placed} relics")
    except Exception as e:
        logger.warning(f"relic placement failed: {e}")

    # Record the history on the engine (Legends journal + gossip)
    engine.world_history = [
        {"event_id": ev.event_id, "year": ev.year,
         "description": ev.description, "legend": ev.legend,
         "relic_id": ev.relic_id}
        for ev in events
    ]

    # Surface 1-2 history lines in the player's starting memory
    for ev in events[-2:]:
        engine.memory_manager.add_event(
            f"[Lore] Year {ev.year}: {ev.description}")
    return flavor


def _place_relics(engine, events: List[HistoricalEvent]) -> int:
    from items.item_registry import create_item
    placed = 0
    for ev in events:
        if not ev.relic_id:
            continue
        relic = create_item(ev.relic_id)
        if relic is None:
            continue
        spot = _themed_spot(engine, ev.relic_place)
        if spot is None:
            continue
        engine.world.add_item_to_ground(relic, *spot)
        placed += 1
    return placed


_PLACE_TO_LOCATION = {
    "keep": "Ruined Keep",
    "chapel": "Hamlet Chapel",
    "forge": "Durgan's Forge",
    "village": "Oakvale Village",
}


def _themed_spot(engine, place: str) -> Tuple[int, int]:
    """A passable tile at/near the themed spot for a relic."""
    wmap = engine.world.map
    loc_name = _PLACE_TO_LOCATION.get(place)
    if loc_name:
        for loc in engine.world.locations:
            if loc.name == loc_name:
                # Search around the location for a grass/road tile
                for r in range(1, 6):
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            x, y = loc.x + dx, loc.y + dy
                            if 0 <= x < wmap.width and \
                                    0 <= y < wmap.height and \
                                    wmap.terrain[y][x] in (
                                        TerrainType.GRASS,
                                        TerrainType.ROAD):
                                return (x, y)
    target = TerrainType.FOREST if place == "forest" else None
    if place == "river":
        # First grass tile beside water
        for y in range(1, wmap.height - 1):
            for x in range(1, wmap.width - 1):
                if wmap.terrain[y][x] == TerrainType.GRASS and \
                        wmap.terrain[y][x + 1] == TerrainType.WATER:
                    return (x, y)
    if target is not None:
        for y in range(wmap.height):
            for x in range(wmap.width):
                if wmap.terrain[y][x] == target:
                    return (x, y)
    return None


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
