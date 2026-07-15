"""Boss set-pieces (P15.6) — fights with a shape.

A monster template with a `boss` behavior block gets two mechanics
on top of ordinary combat, both data-driven and heuristic:

TELEGRAPHED AoE — instead of an instant hit, the boss MARKS a tile
this turn ("the ground blackens where it aims") and blasts it the
NEXT, so a paying-attention player can step off it. `boss_tick`
(run from the conflict scan) resolves last turn's mark, then paints
a fresh one at the player.

PHASE CHANGES — crossing an HP fraction fires a once-only phase
action: the Tyrant FLOODS its den at 50%, the Wisp Queen
ELECTRIFIES her pool and calls her brood, a warlord ENRAGES.
`boss_on_damaged` (from combat _resolve) checks the thresholds.

Loot and the Legendarium record already fire on the kill through
the normal defeat path — a slain boss becomes a legend for free.
"""

import logging

logger = logging.getLogger("llm_rpg.bosses")

MARK_RADIUS = 1


def boss_spec(npc) -> dict:
    return npc.metadata.get("behavior", {}).get("boss") or {}


def is_boss(npc) -> bool:
    return bool(boss_spec(npc))


def boss_tick(engine, boss) -> bool:
    """Resolve last turn's telegraph, then aim a new one. Returns
    True if the boss acted (so the conflict scan counts it)."""
    spec = boss_spec(boss)
    tele = spec.get("telegraph")
    if not tele:
        return False
    meta = boss.metadata
    marked = meta.pop("boss_mark", None)
    acted = False
    if marked is not None:
        _detonate(engine, boss, marked, tele)
        acted = True
    # aim afresh at the player if in range and in sight
    px, py = engine.player.position
    gx, gy = boss.position
    dist = ((gx - px) ** 2 + (gy - py) ** 2) ** 0.5
    if dist <= tele.get("range", 8) and engine.active_zone() is None:
        try:
            from world.fov import overworld_los
            if not overworld_los(engine, (gx, gy), (px, py)):
                return acted
        except Exception:
            pass
        meta["boss_mark"] = [px, py]
        engine.memory_manager.add_event(
            f"[!] {boss.name} takes aim — the ground blackens "
            f"beneath you. MOVE!")
        acted = True
    return acted


def _detonate(engine, boss, pos, tele) -> None:
    x, y = int(pos[0]), int(pos[1])
    dmg = tele.get("damage", 12)
    radius = tele.get("radius", MARK_RADIUS)
    px, py = engine.player.position
    if abs(px - x) <= radius and abs(py - y) <= radius:
        engine.player.take_damage(dmg)
        if engine.player.hp <= 0:
            engine.player.hp = 1    # the blast maims; the story kills
        engine.memory_manager.add_event(
            f"[!] {boss.name}'s strike lands — you didn't clear it! "
            f"(-{dmg} HP)")
    else:
        engine.memory_manager.add_event(
            f"{boss.name}'s strike cracks the empty ground where "
            f"you stood.")
    try:   # the world takes the hit too (P10.2)
        if engine.active_zone() is None:
            engine.tile_damage.damage_radius(x, y, dmg, radius,
                                             "siege")
    except Exception:
        pass
    if tele.get("kind") == "breath":   # dragonfire leaves the ground ablaze
        try:
            if engine.active_zone() is None:
                lay = engine.surfaces_layer
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        lay.ignite(x + dx, y + dy)
        except Exception:
            pass


def boss_on_damaged(engine, boss) -> None:
    """A hit may push the boss across a phase threshold."""
    spec = boss_spec(boss)
    phases = spec.get("phases")
    if not phases or boss.max_hp <= 0:
        return
    frac = boss.hp / boss.max_hp
    fired = boss.metadata.setdefault("boss_phases_fired", [])
    for i, phase in enumerate(phases):
        if i in fired:
            continue
        if frac <= phase.get("at", 0.5):
            fired.append(i)
            _run_phase(engine, boss, phase)


def _run_phase(engine, boss, phase) -> None:
    action = phase.get("action")
    line = phase.get("line")
    if line:
        engine.memory_manager.add_event(f"[!] {line}")
    bx, by = boss.position
    if action == "flood":
        try:
            engine.flood_system.start_flood(
                bx, by, duration=phase.get("duration", 120),
                max_tiles=phase.get("max_tiles", 30))
        except Exception:
            pass
    elif action == "electrify":
        try:
            lay = engine.surfaces_layer
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    lay.pour(bx + dx, by + dy, "water")
            lay.electrify(bx, by)
        except Exception:
            pass
    elif action == "enrage":
        boss.metadata.setdefault("behavior", {})
        boss.strength = getattr(boss, "strength", 12) + \
            phase.get("strength", 4)
    elif action == "terror":   # a dragon's roar unmakes the brave (P19.1)
        try:
            from characters.status_effects import apply_effect
            apply_effect(engine.player, "frightened",
                         duration=phase.get("duration", 3),
                         value=phase.get("value", 2))
        except Exception:
            pass
    elif action == "summon":
        _summon(engine, boss, phase)


def _summon(engine, boss, phase) -> None:
    from world.monsters import build_monster
    from world.world_map import TerrainType
    wmap = engine.world.map
    bx, by = boss.position
    template = phase.get("template", "marsh_wisp")
    count = phase.get("count", 2)
    placed = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (1, 1), (-1, -1), (1, -1), (-1, 1)):
        if placed >= count:
            break
        nx, ny = bx + dx, by + dy
        if not (0 <= nx < wmap.width and 0 <= ny < wmap.height):
            continue
        if wmap.get_character_at(nx, ny) is not None:
            continue
        if wmap.terrain[ny][nx] in (TerrainType.BUILDING,
                                    TerrainType.MOUNTAIN):
            continue
        add = build_monster(template, (nx, ny))
        if boss.metadata.get("zone"):
            add.metadata["zone"] = boss.metadata["zone"]
        engine.npc_manager.add_npc(add)
        wmap.place_character(add, nx, ny)
        placed += 1
