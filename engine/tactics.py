"""Player tactical verbs (P5.3): opportunity attacks, disengage, shove.

SHIFT is the tactical modifier:
- SHIFT+move  — disengage: retreat carefully, immune to opportunity
                attacks, but the care costs an extra minute.
- SHIFT+F     — shove: STR contest; push the adjacent enemy back one
                tile and open space to flee or shoot.
- SHIFT+R     — aimed shot: +2 damage, +1 minute (in game_api_mixin).

Plain movement away from an adjacent hostile now provokes a free strike
— retreat is a decision, not a freebie.
"""

import logging
import random
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.tactics")

DISENGAGE_EXTRA_MINUTES = 1


def adjacent_hostiles(engine, pos: Tuple[int, int]) -> List:
    out = []
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("brigand", "monster", "troll"):
            continue
        d = max(abs(npc.position[0] - pos[0]),
                abs(npc.position[1] - pos[1]))
        if d <= 1:
            out.append(npc)
    return out


def opportunity_attack(engine, old_pos: Tuple[int, int]) -> Optional[str]:
    """After the player moves: hostiles adjacent to the OLD position
    that are no longer adjacent get one free strike (the nearest one)."""
    new_pos = engine.player.position
    leavers = [h for h in adjacent_hostiles(engine, old_pos)
               if max(abs(h.position[0] - new_pos[0]),
                      abs(h.position[1] - new_pos[1])) > 1]
    if not leavers:
        return None
    striker = leavers[0]
    engine.memory_manager.add_event(
        f"{striker.name} lashes out as you turn to flee!")
    try:
        return engine.combat_system._resolve(striker, engine.player)
    except Exception as e:
        logger.debug(f"opportunity strike failed: {e}")
        return None


def disengage_cost(engine) -> None:
    engine.world.advance_time(DISENGAGE_EXTRA_MINUTES)


def shove(engine, rng: random.Random = None) -> str:
    """STR contest vs the nearest adjacent hostile; push them one tile
    directly away. Blocked tiles make the shove fail."""
    rng = rng or random.Random()
    player = engine.player
    hostiles = adjacent_hostiles(engine, player.position)
    if not hostiles:
        return "No enemy close enough to shove."
    target = hostiles[0]

    mine = rng.randint(1, 20) + player.get_stat_modifier("strength")
    theirs = rng.randint(1, 20) + target.get_stat_modifier("strength")
    if mine <= theirs:
        msg = f"You shove {target.name}, but they hold their ground!"
        engine.memory_manager.add_event(msg)
        engine.advance_turn()
        return msg

    dx = target.position[0] - player.position[0]
    dy = target.position[1] - player.position[1]
    step = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    nx, ny = target.position[0] + step[0], target.position[1] + step[1]
    wmap = engine.world.map
    from world.world_map import TerrainType
    pushable = (0 <= nx < wmap.width and 0 <= ny < wmap.height and
                wmap.get_terrain_at(nx, ny) not in
                (TerrainType.WATER, TerrainType.MOUNTAIN,
                 TerrainType.BUILDING) and
                not any(n.is_active() and n.position == (nx, ny)
                        for n in engine.npc_manager.npcs.values()))
    if pushable:
        wmap.remove_character(target)
        target.position = (nx, ny)
        wmap.place_character(target, nx, ny)
        msg = f"You slam into {target.name} and send them staggering back!"
    else:
        msg = (f"You shove {target.name} against the "
               f"obstruction — they stumble but hold.")
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg
