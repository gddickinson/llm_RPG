"""OAKVALE T6 — POPULATE the town with role NPCs (a living town).

Every service/civic building gets a keeper of the right calling (a shop → a
shopkeeper, a tavern → a tavernkeeper, a smithy → a blacksmith, a temple → a
priest, the town hall → the MAYOR, a guildhall → a guildmaster, the bank → a
banker); a capped share of dwellings gets a townsperson; and the streets get
their thieves, urchins, vagrants and roaming guards. A keeper's `home_location`
is set to its BUILDING NAME so `engine/shop._category_for_npc` stocks the right
wares (a "Smithy" name → blacksmith stock) AND the P9A.7 presence system seats
them INDOORS — you meet them when you step inside. Data: `data/town/roles.json`.

`populate_town(engine, town_name, seed)` returns how many townsfolk were seated.
"""

import logging
import random

from characters.character_types import CharacterClass
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.town_population")

_STREET_OK = (TerrainType.ROAD, TerrainType.GRASS, TerrainType.BRIDGE)
_SKIP_KINDS = ("well",)                          # 1×1 markers with no keeper


def _roles() -> dict:
    from items.data_loader import load_data_file
    try:
        return load_data_file("town/roles.json") or {}
    except Exception:                                # pragma: no cover
        return {}


def _klass(name: str) -> CharacterClass:
    try:
        return CharacterClass(name)
    except Exception:                                # pragma: no cover
        return CharacterClass.VILLAGER


def _free_tile_in(engine, loc):
    """A tile inside a building footprint not already holding a character."""
    wm = engine.world.map
    for dy in range(loc.height):
        for dx in range(loc.width):
            x, y = loc.x + dx, loc.y + dy
            if 0 <= x < wm.width and 0 <= y < wm.height \
                    and (x, y) not in wm.characters:
                return (x, y)
    return loc.center()


def _seat(engine, klass, role, workplace, pos):
    npc = engine.npc_manager.create_random_npc(char_class=klass)
    if workplace:
        npc.home_location = workplace            # → shop category + presence
        npc.metadata["workplace"] = workplace
    npc.metadata["role"] = role
    npc.metadata["townsfolk"] = True
    x, y = pos
    try:
        engine.world.map.remove_character(npc)
    except Exception:
        pass
    npc.position = (x, y)
    engine.world.map.place_character(npc, x, y)
    return npc


def _street_tiles(engine, cx, cy, radius, n, rng):
    wm = engine.world.map
    out = []
    tries = 0
    while len(out) < n and tries < n * 40:
        tries += 1
        a = rng.random() * 6.2832
        r = rng.uniform(radius * 0.15, radius * 0.9)
        x = int(cx + r * __import__("math").cos(a))
        y = int(cy + r * __import__("math").sin(a))
        if 0 <= x < wm.width and 0 <= y < wm.height \
                and wm.terrain[y][x] in _STREET_OK and (x, y) not in wm.characters:
            out.append((x, y))
    return out


def populate_town(engine, town_name: str = "Oakvale", seed: int = 0) -> int:
    """Seat keepers, home-dwellers and street folk. Returns the count."""
    rng = random.Random(seed)
    data = _roles()
    kind_roles = data.get("kind_roles", {})
    town = next((l for l in engine.world.locations
                 if l.name == town_name and l.get_property("town")), None)
    cx, cy = town.center() if town else (engine.world.map.width // 2,
                                         engine.world.map.height // 2)
    radius = (town.width // 2) if town else 40

    buildings = [l for l in engine.world.locations if l.get_property("kind")]
    homes, seated = [], 0
    for b in buildings:
        kind = b.get_property("kind")
        if kind in _SKIP_KINDS:
            continue
        rr = kind_roles.get(kind)
        if rr is None:
            continue
        if kind in ("home", "cottage"):
            homes.append((b, rr))
            continue
        _seat(engine, _klass(rr[1]), rr[0], b.name, _free_tile_in(engine, b))
        seated += 1

    rng.shuffle(homes)
    for (b, rr) in homes[:int(data.get("max_home_residents", 20))]:
        _seat(engine, _klass(rr[1]), rr[0], b.name, _free_tile_in(engine, b))
        seated += 1

    for role, klass, count in data.get("street_folk", []):
        for pos in _street_tiles(engine, cx, cy, radius, int(count), rng):
            _seat(engine, _klass(klass), role, None, pos)
            seated += 1

    logger.info("Populated %s with %d townsfolk.", town_name, seated)
    return seated
