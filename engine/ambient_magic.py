"""World spells cast by NPCs + away-heroes — the wilderness shaped by OTHERS, not
only the player (George: "NPCs and away-heroes should be able to cast world-
altering spells").

A caster NPC (druid/wizard/warlock/sorcerer) or a driven away-hero near the
player occasionally reshapes a fitting nearby overworld tile through the same
`spell_world.ambient_shape` → `worldcraft` path the player uses — so a druid
grows a woodland, a warlock blights the ground, a mage raises a wall. Rare +
throttled + protected-ground-safe (worldcraft refuses typed-POI tiles), so it's
living-world flavour, not chaos. Run once per turn from `turn_pipeline`.
"""

_CASTERS = ("druid", "wizard", "warlock", "sorcerer")
INTERVAL = 11          # game-minutes between checks (deterministic throttle)
RADIUS = 12
CHANCE = 0.2           # of an eligible caster acting, when the throttle fires


def _eligible(engine):
    px, py = engine.player.position
    out = []
    for npc in engine.npc_manager.npcs.values():
        if not (hasattr(npc, "is_alive") and npc.is_alive()):
            continue
        klass = getattr(getattr(npc, "character_class", None), "value", "")
        if klass not in _CASTERS:
            continue
        meta = getattr(npc, "metadata", None) or {}
        if meta.get("zone") or meta.get("fleeing") or meta.get("_aggro_turn"):
            continue                                  # indoors / mid-fight
        if abs(npc.position[0] - px) > RADIUS or \
                abs(npc.position[1] - py) > RADIUS:
            continue
        out.append(npc)
    return out


def run(engine) -> None:
    """Occasionally let a nearby caster reshape the world. Cheap: a deterministic
    time throttle early-returns almost every turn, and the RNG roll only happens
    when an eligible caster is actually near."""
    try:
        if engine.world.time % INTERVAL != 0:
            return
    except Exception:
        return
    casters = _eligible(engine)
    if not casters:
        return
    import random
    if random.random() > CHANCE:
        return
    try:
        from engine import spell_world
        spell_world.ambient_shape(engine, random.choice(casters))
    except Exception:
        pass
