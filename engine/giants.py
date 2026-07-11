"""Giants and labor (P10.5) — actors shape the world.

GIANTS (behavior flag "giant" on the monster template): each
conflict tick a giant either SMASHES an adjacent building wall —
STR-scaled siege damage, no lock or DC consulted, and a collapsed
wall gains an extra layer of debris (giants leave DEEP rubble,
blocked until cleared) — or HURLS A BOULDER at the player from
range: direct hit plus splash to anyone adjacent, siege damage to
the tiles, and a scatter of debris where it lands.

LABOR (nightly): villagers repair their world back. Work crews
clear rubble layers near their settlement's buildings (through
clear_rubble — debris is moved, never deleted), and the forest
creeps back: scorched ground beside living woods has a small
chance to regrow each night. The world wounds AND heals.

Cooperative ConstructionProjects (materials + workers → stamped
tiles) are the P10.5 remainder, noted in the plan.
"""

import logging
import random

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.giants")

BOULDER_RANGE = 8
BOULDER_MIN_RANGE = 3
BOULDER_DAMAGE = 10
BOULDER_SPLASH = 5
BOULDER_TILE_DAMAGE = 15
GIANT_COOLDOWN = 3          # conflict ticks between big acts
LABOR_LAYERS_PER_NIGHT = 3
REBUILD_PER_NIGHT = 2       # wall tiles the masons raise
REGROWTH_CHANCE = 0.05
REGROWTH_CAP = 5


def is_giant(npc) -> bool:
    return bool(npc.metadata.get("behavior", {}).get("giant"))


def giant_tick(engine, giant) -> bool:
    """One giant act per cooldown: smash > hurl. True if it acted."""
    meta = giant.metadata
    cd = meta.get("giant_cd", 0)
    if cd > 0:
        meta["giant_cd"] = cd - 1
        return False
    gx, gy = giant.position
    wmap = engine.world.map
    # SMASH an adjacent wall
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = gx + dx, gy + dy
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            continue
        if wmap.terrain[ny][nx] == TerrainType.BUILDING:
            str_mod = (getattr(giant, "strength", 20) - 10) // 2
            from engine.presence import in_earshot
            if in_earshot(engine, (nx, ny)):
                engine.memory_manager.add_event(
                    f"{giant.name} smashes at the wall!")
            msg = engine.tile_damage.damage_tile(
                nx, ny, 15 + 3 * str_mod, "siege")
            if msg and "rubble" in msg:
                engine.tile_damage.add_rubble(nx, ny, 1)  # DEEP
            meta["giant_cd"] = GIANT_COOLDOWN
            return True
    # HURL a boulder at the player
    px, py = engine.player.position
    dist = ((gx - px) ** 2 + (gy - py) ** 2) ** 0.5
    if BOULDER_MIN_RANGE <= dist <= BOULDER_RANGE and \
            engine.active_zone() is None:
        try:
            from world.fov import overworld_los
            if not overworld_los(engine, (gx, gy), (px, py)):
                return False
        except Exception:
            pass
        engine.memory_manager.add_event(
            f"{giant.name} hurls a boulder at you!")
        engine.player.take_damage(BOULDER_DAMAGE)
        if engine.player.hp <= 0:
            engine.player.hp = 1     # boulders maim; the story kills
        engine.memory_manager.add_event(
            f"The boulder strikes you (-{BOULDER_DAMAGE} HP)!")
        # splash to anyone beside the player
        for npc in engine.npc_manager.npcs.values():
            if npc.id == giant.id or not npc.is_active():
                continue
            nx2, ny2 = npc.position
            if abs(nx2 - px) <= 1 and abs(ny2 - py) <= 1:
                npc.take_damage(BOULDER_SPLASH)
                if not npc.is_alive():
                    npc.defeat()
                    engine.world.map.remove_character(npc)
                    engine.memory_manager.add_event(
                        f"{npc.name} is crushed by the boulder!")
        engine.tile_damage.damage_radius(px, py, BOULDER_TILE_DAMAGE,
                                         1.0, "siege")
        if wmap.terrain[py][px] == TerrainType.GRASS:
            engine.tile_damage.add_rubble(px, py, 1)
        meta["giant_cd"] = GIANT_COOLDOWN
        return True
    return False


# ------------------------------------------------------------- labor

def run_night_labor(engine, rng: random.Random = None) -> int:
    """Villagers clear rubble near their buildings; the forest
    creeps back over scorched ground. Returns acts performed."""
    rng = rng or random.Random()
    wmap = engine.world.map
    acts = 0
    # 1) work crews clear rubble beside buildings
    cleared = 0
    for loc in engine.world.locations:
        if cleared >= LABOR_LAYERS_PER_NIGHT:
            break
        if loc.name not in getattr(engine, "interiors", {}):
            continue
        for ey in range(loc.y - 1, loc.y + loc.height + 1):
            for ex in range(loc.x - 1, loc.x + loc.width + 1):
                if cleared >= LABOR_LAYERS_PER_NIGHT:
                    break
                if engine.tile_damage.depth_at(ex, ey) > 0:
                    if engine.tile_damage.clear_rubble(ex, ey):
                        cleared += 1
    if cleared:
        engine.memory_manager.add_event(
            "[Realm] Work crews haul broken stone away from the "
            "buildings.")
        acts += cleared
    # 2) masons rebuild breached walls (P10.6 — minimal cooperative
    #    construction: footprint tiles cleared of rubble are raised
    #    back to BUILDING, and the interior hole closes with them)
    rebuilt = 0
    for loc in engine.world.locations:
        if rebuilt >= REBUILD_PER_NIGHT:
            break
        inter = getattr(engine, "interiors", {}).get(loc.name)
        if inter is None:
            continue
        for ey in range(loc.y, loc.y + loc.height):
            for ex in range(loc.x, loc.x + loc.width):
                if rebuilt >= REBUILD_PER_NIGHT:
                    break
                if wmap.terrain[ey][ex] not in (TerrainType.GRASS,
                                                TerrainType.SCORCHED):
                    continue
                if engine.tile_damage.depth_at(ex, ey) > 0:
                    continue
                wmap.set_terrain(ex, ey, TerrainType.BUILDING)
                engine.tile_damage.tile_hp.pop((ex, ey), None)
                try:
                    from engine.earthworks import close_breach
                    close_breach(loc, inter, ex, ey)
                except Exception:
                    pass
                engine.memory_manager.add_event(
                    f"[Realm] Masons raise fresh masonry at the "
                    f"{loc.name}.")
                rebuilt += 1
    acts += rebuilt
    # 3) the forest creeps back
    regrown = 0
    for y in range(wmap.height):
        for x in range(wmap.width):
            if regrown >= REGROWTH_CAP:
                break
            if wmap.terrain[y][x] != TerrainType.SCORCHED:
                continue
            neighbors = sum(
                1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= x + dx < wmap.width
                and 0 <= y + dy < wmap.height
                and wmap.terrain[y + dy][x + dx] ==
                TerrainType.FOREST)
            if neighbors >= 2 and rng.random() < REGROWTH_CHANCE:
                wmap.set_terrain(x, y, TerrainType.FOREST)
                regrown += 1
        if regrown >= REGROWTH_CAP:
            break
    if regrown >= 3:
        engine.memory_manager.add_event(
            "[Realm] Green shoots stand where the burnt ground was.")
    return acts + regrown
