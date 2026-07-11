"""Environmental hazards (P11.2) — the land fights back.

FLOW — a water tile that is part of a channel (exactly two OPPOSITE
water neighbors) is a river, and rivers run: flow points along the
channel toward the map's south/east (downhill by convention). Open
water — a lake, three-plus water neighbors — is still.

IN DEEP WATER each turn the player makes a struggle check (the same
swim math as crossing: d20 + Swimming + STR mod vs the loaded/tired
DC). Fail in a current and you're SWEPT downstream a tile or two;
fail anywhere and the water starts winning — escalating drown
damage. The water never kills outright (the story kills): brought
to 1 HP the river spits you out — WASHED ASHORE at the nearest dry
land, battered, and the river keeps one item from your pack.

ON ROCK a badly failed climb is a TUMBLE: you fall off the face to
adjacent flat ground and take the hit there.

Everything telegraphs: `[!]`-prefixed log lines + a hint-bar
warning while you're in the water.
"""

import logging
from typing import Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.hazards")

DROWN_STEP = 2          # damage grows by this each failing turn
SWEEP_TILES = 2         # how far a current carries you per fail


FLOW_SCAN = 12          # how far along an axis we look for "river"


def flow_at(engine, x: int, y: int) -> Optional[Tuple[int, int]]:
    """The current at a water tile. A river is much longer than it
    is wide: flow runs along the clearly-longer water axis, toward
    the map's south/east (downhill by convention). Round lakes and
    bends are slack — None."""
    wmap = engine.world.map
    if wmap.terrain[y][x] != TerrainType.WATER:
        return None

    def run(dx, dy):
        n = 0
        nx, ny = x + dx, y + dy
        while (n < FLOW_SCAN and 0 <= nx < wmap.width
               and 0 <= ny < wmap.height
               and wmap.terrain[ny][nx] == TerrainType.WATER):
            n += 1
            nx, ny = nx + dx, ny + dy
        return n

    horiz = run(1, 0) + run(-1, 0) + 1
    vert = run(0, 1) + run(0, -1) + 1
    if horiz >= vert + 2:
        return (1, 0)                  # river runs east
    if vert >= horiz + 2:
        return (0, 1)                  # river runs south
    return None                        # open or slack water


def water_hazard_tick(engine) -> None:
    """Once per turn: deep water makes the player struggle."""
    player = engine.player
    if engine.active_zone() is not None:
        return
    x, y = player.position
    wmap = engine.world.map
    if wmap.terrain[y][x] != TerrainType.WATER or \
            engine.traversal.is_shallow(x, y):
        player.metadata.pop("drown_turns", None)
        return
    from characters.status_effects import has_effect
    if has_effect(player, "water_walking") or \
            has_effect(player, "flying"):        # P11.3 / P11.4
        player.metadata.pop("drown_turns", None)
        return
    trav = engine.traversal
    rule = trav.rules.get("water", {})
    from engine.skill_progression import get_skill_level
    from engine.skills import ability_modifier
    d20 = trav.rng.randint(1, 20)
    total = d20 + get_skill_level(player, "swimming") + \
        ability_modifier(getattr(player, "strength", 10)) + \
        trav.aid_bonus("swim")
    if total >= trav.check_dc(rule):
        player.metadata.pop("drown_turns", None)
        engine.memory_manager.add_event(
            "You tread water, keeping your head up.")
        return
    # the water is winning
    turns = player.metadata.get("drown_turns", 0) + 1
    player.metadata["drown_turns"] = turns
    trav._tire(4)
    flow = flow_at(engine, x, y)
    if flow is not None:
        _sweep(engine, flow)
    dmg = DROWN_STEP * turns
    player.take_damage(dmg)
    engine.memory_manager.add_event(
        f"[!] You go under — the water fills your throat! "
        f"(-{dmg} HP)")
    try:   # drop your pack or sink (P11.3)
        from engine.carry import capacity, used_slots
        if used_slots(player) / max(1, capacity(player)) >= 0.9:
            engine.memory_manager.add_event(
                "[!] Your pack drags you down — drop something "
                "([I]) or sink!")
    except Exception:
        pass
    if player.hp <= 1:
        player.hp = 1
        _wash_ashore(engine)


def _sweep(engine, flow: Tuple[int, int]) -> None:
    """The current drags the player downstream."""
    player = engine.player
    wmap = engine.world.map
    moved = 0
    for _ in range(SWEEP_TILES):
        nx = player.position[0] + flow[0]
        ny = player.position[1] + flow[1]
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            break
        if wmap.terrain[ny][nx] != TerrainType.WATER:
            break
        if wmap.get_character_at(nx, ny) is not None:
            break
        wmap.remove_character(player)
        player.position = (nx, ny)
        wmap.place_character(player, nx, ny)
        moved += 1
    if moved:
        engine.memory_manager.add_event(
            "[!] The current sweeps you downstream!")


def _wash_ashore(engine) -> None:
    """At 1 HP the river spits you out — and keeps a souvenir."""
    player = engine.player
    wmap = engine.world.map
    px, py = player.position
    # nearest dry, unoccupied, walkable tile (small BFS ring)
    best = None
    for r in range(1, 7):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                nx, ny = px + dx, py + dy
                if not (0 <= nx < wmap.width and
                        0 <= ny < wmap.height):
                    continue
                if wmap.terrain[ny][nx] in (
                        TerrainType.WATER, TerrainType.MOUNTAIN,
                        TerrainType.BUILDING):
                    continue
                if wmap.get_character_at(nx, ny) is not None:
                    continue
                best = (nx, ny)
                break
            if best:
                break
        if best:
            break
    if best is None:
        return                        # nowhere to wash up; struggle on
    wmap.remove_character(player)
    player.position = best
    wmap.place_character(player, *best)
    player.metadata.pop("drown_turns", None)
    player.metadata["fatigue"] = 100
    lost = ""
    droppable = [it for it in player.inventory
                 if hasattr(it, "id")]
    if droppable:
        item = engine.traversal.rng.choice(droppable) \
            if hasattr(engine.traversal.rng, "choice") \
            else droppable[0]
        player.inventory.remove(item)
        engine.world.add_item_to_ground(item, px, py)
        lost = f" The river keeps your {item.name}."
    engine.memory_manager.add_event(
        f"[!] You are washed ashore, battered and spent.{lost}")
    try:   # river water in an open wound (P12.12)
        from engine.infection import maybe_infect
        maybe_infect(engine, 0.30, "the river")
    except Exception:
        pass


def tumble(engine) -> Optional[str]:
    """A badly failed climb off a rock face: fall to flat ground."""
    player = engine.player
    wmap = engine.world.map
    x, y = player.position
    if wmap.terrain[y][x] != TerrainType.MOUNTAIN:
        return None
    for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            continue
        if wmap.terrain[ny][nx] in (TerrainType.WATER,
                                    TerrainType.MOUNTAIN,
                                    TerrainType.BUILDING):
            continue
        if wmap.get_character_at(nx, ny) is not None:
            continue
        wmap.remove_character(player)
        player.position = (nx, ny)
        wmap.place_character(player, nx, ny)
        msg = "[!] You tumble down the rock face to the ground below!"
        engine.memory_manager.add_event(msg)
        return msg
    return None
