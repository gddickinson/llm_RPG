"""M2 — world-altering spells: the `world_effect` dispatcher.

A spell's optional `world_effect` block (M1 schema) turns magic into terrain
change — the same VERBS a mason or the player's build tool use, routed through
the M0 `worldcraft` ruleset so magical and non-magical world change stay
consistent. Blocks (any combination):

    "worldcraft": {"to": "<terrain>"}   -> worldcraft.mutate(means="magic")
    "tile_damage": {"type","radius","amount"}  -> raze terrain + structures
    "surface": {"kind": fire|shock|water|oil, "radius", "intensity"}

A PURE world spell (no damage/heal/status) targets a TILE (the ranged lock, else
the tile the caster faces); a damage spell that ALSO carries a `world_effect`
applies it at the struck tile. Overworld only for now (interiors keep their own
coordinate space). Kept out of `spells.py` to hold the 500-line line.
"""

from typing import List, Optional, Tuple


def resolve_tile(engine, caster) -> Optional[Tuple[int, int]]:
    """The tile a world spell shapes — the one the caster is FACING (you build /
    terraform where you look). A locked ENEMY isn't a build target, so we use the
    facing heading, not the ranged lock. Default one step south."""
    fx, fy = 0, 1
    anim = (getattr(caster, "metadata", None) or {}).get("_anim") or {}
    f = anim.get("facing")
    if isinstance(f, (tuple, list)) and (f[0] or f[1]):
        fx = (1 if f[0] > 0 else -1) if f[0] else 0
        fy = (1 if f[1] > 0 else -1) if f[1] else 0
    x, y = caster.position
    return (x + fx, y + fy)


def apply(engine, caster, spell, tx: int, ty: int) -> List[str]:
    """Apply a spell's `world_effect` at tile (tx, ty). Returns beat lines."""
    eff = getattr(spell, "world_effect", None) or {}
    out: List[str] = []

    wc = eff.get("worldcraft")
    if wc and wc.get("to"):
        try:
            from engine import worldcraft
            ok, msg = worldcraft.mutate(engine, tx, ty, wc["to"], "magic",
                                        caster, quiet=True)
            out.append(f"{caster.name}'s {spell.name} reshapes the land."
                       if ok else f"The {spell.name} can't reshape that — {msg}.")
        except Exception:
            pass

    td = eff.get("tile_damage")
    if td:
        try:
            razed = engine.tile_damage.damage_radius(
                tx, ty, int(td.get("amount", spell.damage or 12)),
                float(td.get("radius", spell.area or 1)),
                td.get("type", "siege"))
            if razed:
                out.append(f"The {spell.name} razes {razed} of the land.")
        except Exception:
            pass

    surf = eff.get("surface")
    if surf:
        try:
            lay = engine.surfaces_layer
            kind = surf.get("kind", "fire")
            centre = (tx, ty)
            tiles = [centre]
            if surf.get("radius", 0):
                tiles += [(tx + dx, ty + dy)
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            for (x, y) in tiles:
                if kind == "fire":
                    lay.ignite(x, y, intensity=(surf.get("intensity", 2)
                                                if (x, y) == centre else 1))
                elif kind == "shock":
                    lay.electrify(x, y)
                elif kind in ("water", "oil"):
                    lay.pour(x, y, kind)
            out.append(f"The ground runs with {kind}.")
        except Exception:
            pass
    return out


def cast_tile_spell(spell_system, caster, spell) -> str:
    """The PURE world-spell path (no character target): resolve a tile, range-
    check, pay mana, apply. Mana/known were already checked by `SpellSystem.cast`."""
    engine = spell_system.engine
    try:
        if engine.active_zone() is not None:
            return f"{spell.name} needs the open sky."
    except Exception:
        pass
    tile = resolve_tile(engine, caster)
    if tile is None:
        return f"No ground to shape for {spell.name}."
    d = ((caster.position[0] - tile[0]) ** 2 +
         (caster.position[1] - tile[1]) ** 2) ** 0.5
    if d > spell.range:
        return f"{spell.name}: that ground is too far."
    caster.metadata["mana"] = caster.metadata.get("mana", 0) - spell.mana_cost
    lines = apply(engine, caster, spell, *tile)
    msg = " ".join(lines) if lines else f"{caster.name} shapes the land."
    try:
        engine.memory_manager.add_event(msg)
        if hasattr(engine, "trigger_spell_visual"):
            engine.trigger_spell_visual(spell.id, *tile)
    except Exception:
        pass
    return msg
