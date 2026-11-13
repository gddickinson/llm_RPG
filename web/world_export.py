"""A snapshot of one generated game world for the World page: the terrain grid, named places and where people stand.

It builds a real headless `GameEngine(world_kind="combined")` (the game's default New Game world: Oakvale, the
countryside, Bloodstone Castle, lairs, guild halls, waystones and the five adventures) and reads its map, so the picture
is exactly what the game generates. `GameEngine(seed=...)` makes worldgen reproducible, so the static site shows the
world for a fixed seed (DEFAULT_SEED) and the local app can show any other seed. Takes ~10 s; cached per seed.
"""
import os
import random
import tempfile
from functools import lru_cache

# terrain value -> one-letter code (the front end colours these)
CODES = {"grass": "g", "forest": "f", "mountain": "m", "water": "w", "road": "r", "building": "b", "cave": "c",
         "swamp": "s", "farmland": "a", "rubble": "u", "scorched": "x", "bridge": "d"}
DEFAULT_SEED = 7
_TEST_SWITCHES = ("LLM_RPG_NO_ADVENTURERS", "LLM_RPG_MODULE_PACKS")


def _kind(loc) -> str:
    p = loc.properties or {}
    for key in ("type", "kind"):
        if isinstance(p.get(key), str):
            return p[key]
    for flag in ("adventure", "lair", "tribe_camp", "guildhall", "waystone", "ruin", "village", "town", "camp",
                 "deepdelve_mouth", "wall_tower", "dungeon"):
        if p.get(flag):
            return flag
    return "place"


@lru_cache(maxsize=4)
def world_snapshot(seed: int = DEFAULT_SEED) -> dict:
    os.environ.setdefault("LLM_RPG_DM_LIBRARY", tempfile.mkdtemp(prefix="llmrpg_lib_"))   # never write data/dm_library
    from engine.game_engine import GameEngine
    state = random.getstate()                                # leave the caller's RNG as it was
    # the test suite switches adventurers and module packs off for speed; the web always shows the full New Game world
    saved = {k: os.environ.pop(k) for k in _TEST_SWITCHES if k in os.environ}
    try:
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False, world_kind="combined", seed=seed)
        eng.start_game()
    finally:
        random.setstate(state)
        os.environ.update(saved)
    m = eng.world.map
    terrain = "".join(CODES.get(t.value, "g") for row in m.terrain for t in row)
    places = []
    for loc in eng.world.locations:
        p = loc.properties or {}
        if p.get("hidden"):                                  # secret entrances stay secret
            continue
        places.append({"name": loc.name, "x": loc.x, "y": loc.y, "w": loc.width, "h": loc.height, "kind": _kind(loc),
                       "description": (loc.description or "")[:240]})
    hostile = ("brigand", "troll", "monster")
    people = []
    for npc in eng.npc_manager.npcs.values():
        x, y = npc.position
        if 0 <= x < m.width and 0 <= y < m.height and not npc.metadata.get("zone"):
            klass = getattr(npc.character_class, "value", "villager")
            people.append([int(x), int(y), 1 if klass in hostile else (2 if klass == "animal" else 0)])
    px, py = eng.player.position
    try:
        eng.end_game()
    except Exception:
        pass
    return {"seed": seed, "width": m.width, "height": m.height, "terrain": terrain, "codes": CODES,
            "places": places, "people": people, "spawn": [int(px), int(py)],
            "counts": {"places": len(places), "people": len(people),
                       "hostile": sum(1 for p in people if p[2] == 1)}}
