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


def _caster_in_zone(engine, caster) -> bool:
    """Is the CASTER inside a separate coordinate space (dungeon/interior)? The
    overworld-only guard must follow the CASTER, not the player — else an NPC's
    open-air world spell is blocked whenever the PLAYER happens to be indoors."""
    if caster.id == getattr(engine.player, "id", None):
        try:
            return engine.active_zone() is not None
        except Exception:
            return False
    return bool((getattr(caster, "metadata", None) or {}).get("zone"))


def _is_world_spell(s) -> bool:
    return bool(getattr(s, "world_effect", None)) and not (
        s.damage or s.heal or s.status_effect)


def world_spells_for(caster) -> list:
    """The pure WORLD spells this caster can wield — those it KNOWS, else (for an
    NPC with none learned) its class's INNATE world spells (a druid grows forests
    whether or not it studied the spell)."""
    from engine.spells import SPELL_REGISTRY, class_spells
    known = (getattr(caster, "metadata", None) or {}).get("spells_known", [])
    owned = [SPELL_REGISTRY[s] for s in known
             if s in SPELL_REGISTRY and _is_world_spell(SPELL_REGISTRY[s])]
    if owned:
        return owned
    klass = getattr(getattr(caster, "character_class", None), "value", "")
    return [s for s in class_spells(klass) if _is_world_spell(s)]


def ambient_shape(engine, caster) -> Optional[str]:
    """Have ANY caster (an NPC druid, an away-hero) reshape a fitting nearby
    OVERWORLD tile with a world spell it can wield — the world visibly shaped by
    others, not just the player (George). Grants an NPC the spell innately + funds
    a cast if short; a real hero uses its own known spells + mana. Returns the cast
    message, or None if nothing fitting is nearby."""
    if _caster_in_zone(engine, caster):
        return None
    from engine.spells import ensure_mana
    from engine import worldcraft
    ensure_mana(caster)
    spells = world_spells_for(caster)
    if not spells:
        return None
    x, y = caster.position
    is_player = caster.id == getattr(engine.player, "id", None)
    for spell in spells:
        wc = (spell.world_effect or {}).get("worldcraft")
        if not wc or not wc.get("to"):
            continue
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0),
                       (1, 1), (-1, 1), (1, -1), (-1, -1)):
            tx, ty = x + dx, y + dy
            ok, _ = worldcraft.can_mutate(engine, tx, ty, wc["to"], "magic")
            if not ok:
                continue
            known = caster.metadata.setdefault("spells_known", [])
            if not is_player and spell.id not in known:
                known.append(spell.id)                       # innate for NPCs
            if not is_player and caster.metadata.get("mana", 0) < spell.mana_cost:
                caster.metadata["mana"] = spell.mana_cost    # fund one cast
                caster.metadata["max_mana"] = max(
                    caster.metadata.get("max_mana", 0), spell.mana_cost)
            caster.metadata.setdefault("_anim", {})["facing"] = (
                (1 if dx > 0 else -1 if dx < 0 else 0),
                (1 if dy > 0 else -1 if dy < 0 else 0))
            ss = getattr(engine, "spell_system", None)
            if ss is None:                       # the engine builds it lazily
                from engine.spells import SpellSystem
                ss = engine.spell_system = SpellSystem(engine)
            return ss.cast(caster, spell.id)
    return None


def cast_tile_spell(spell_system, caster, spell) -> str:
    """The PURE world-spell path (no character target): resolve a tile, range-
    check, pay mana, apply. Mana/known were already checked by `SpellSystem.cast`."""
    engine = spell_system.engine
    if _caster_in_zone(engine, caster):
        return f"{spell.name} needs the open sky."
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
