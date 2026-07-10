"""Failure as story — defeat outcomes (P4.7, the Kenshi lesson).

Losing a fight on the overworld usually doesn't end the game; it
produces a new situation:

- ROBBED (~60%): you wake at the nearest temple, stripped of ~30% of
  carried gold (banked gold is untouchable — banking finally earns its
  keep). A couple of game-hours pass.
- LEFT FOR DEAD (~30%): you come to where you fell at 1 HP, six hours
  later, ravenous.
- SLAIN (~10%, and ALWAYS inside dungeons/zones): the classic death
  popup / game over.
"""

import logging
import random
from typing import Tuple

logger = logging.getLogger("llm_rpg.defeat")

ROBBED_GOLD_FRACTION = 0.30
ROBBED_HOURS = 2
LEFT_FOR_DEAD_HOURS = 6


def handle_player_defeat(engine, attacker,
                         rng: random.Random = None) -> Tuple[bool, str]:
    """Resolve the player's defeat. Returns (survived, message)."""
    rng = rng or random.Random()
    player = engine.player

    # Inside a dungeon/interior nobody drags you to safety
    in_zone = False
    try:
        in_zone = engine.active_zone() is not None
    except Exception:
        pass

    roll = rng.random()
    if in_zone or roll < 0.10:
        return (False, "You have been defeated!")

    # The victor remembers besting you
    try:
        from engine.npc_memory import remember
        remember(attacker, f"I defeated {player.name} in battle.",
                 6, engine.world.time)
    except Exception:
        pass

    if roll < 0.70:
        return (True, _robbed(engine, attacker, rng))
    return (True, _left_for_dead(engine))


def _revive(engine, hp: int) -> None:
    player = engine.player
    player.status = "alive"
    player.hp = max(1, min(hp, player.max_hp))


def _robbed(engine, attacker, rng) -> str:
    player = engine.player
    stolen = int(player.gold * ROBBED_GOLD_FRACTION)
    player.gold -= stolen
    _revive(engine, hp=max(1, player.max_hp // 3))

    pos = _sanctuary_position(engine)
    try:
        engine.world.map.remove_character(player)
    except Exception:
        pass
    player.position = pos
    engine.world.map.place_character(player, *pos)
    engine.world.advance_time(ROBBED_HOURS * 60)

    msg = (f"Darkness takes you... You wake at a place of sanctuary, "
           f"aching and lighter of purse ({stolen}g gone). "
           f"Your banked gold, at least, is safe.")
    engine.memory_manager.add_event(msg)
    return msg


def _left_for_dead(engine) -> str:
    player = engine.player
    _revive(engine, hp=1)
    try:
        player.metadata["hunger"] = max(
            player.metadata.get("hunger", 20), 75)
    except Exception:
        pass
    engine.world.advance_time(LEFT_FOR_DEAD_HOURS * 60)
    msg = ("You come to hours later where you fell — bloodied, "
           "starving, but alive. Barely.")
    engine.memory_manager.add_event(msg)
    return msg


def _sanctuary_position(engine) -> Tuple[int, int]:
    """The nearest temple/chapel; failing that, the village center."""
    px, py = engine.player.position
    best, best_d = None, None
    for loc in engine.world.locations:
        kind = (loc.properties or {}).get("type", "")
        if kind not in ("temple", "chapel") and \
                "Temple" not in loc.name and "Chapel" not in loc.name:
            continue
        cx, cy = loc.x + loc.width // 2, loc.y + loc.height // 2
        d = abs(cx - px) + abs(cy - py)
        if best_d is None or d < best_d:
            best, best_d = (cx, cy + max(1, loc.height // 2) + 1), d
    if best is None:
        for loc in engine.world.locations:
            if "Village" in loc.name:
                best = (loc.x + loc.width // 2, loc.y + loc.height + 1)
                break
    if best is None:
        best = (engine.world.map.width // 2,
                engine.world.map.height // 2)
    # Nudge onto a passable tile
    from world.world_map import TerrainType
    wmap = engine.world.map
    bx, by = best
    for r in range(0, 6):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = bx + dx, by + dy
                if 0 <= x < wmap.width and 0 <= y < wmap.height and \
                        wmap.terrain[y][x] in (TerrainType.GRASS,
                                               TerrainType.ROAD):
                    return (x, y)
    return best
