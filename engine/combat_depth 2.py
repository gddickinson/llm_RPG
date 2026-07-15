"""Combat depth (P12.7): concentration, cover, weapon actions.

CONCENTRATION (5e): one sustained spell at a time. Casting a second
concentration spell drops the first (its status ends wherever it
sat). Taking damage forces the keep-it check: d20 + CON modifier
vs max(10, damage dealt) — fail and the sustained effect breaks.

COVER (vs ranged): forest and rubble strictly between shooter and
target soak shots — one covering tile is half cover (-10% hit),
two or more is three-quarters (-25%). Computed at loose-time and
carried on the projectile.

WEAPON ACTIONS (BG3): each weapon type carries one special move as
data (use_effect.weapon_action), ONCE PER REST: Cleave (axe: the
strike carries into a second adjacent enemy), Topple (hammer:
prone), Pommel Strike (sword: stunned), Lacerate (dagger: bleed).
SHIFT+V spends it; any real night's sleep restores it.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.combat_depth")

HALF_COVER_PENALTY = 0.10
THREE_QTR_COVER_PENALTY = 0.25

ACTIONS = {
    "cleave": {"name": "Cleave",
               "line": "You cleave through {t} and into {u}!"},
    "topple": {"name": "Topple",
               "line": "You hook {t}'s legs — they crash down!"},
    "pommel_strike": {"name": "Pommel Strike",
                      "line": "You crack the pommel across "
                              "{t}'s skull!"},
    "lacerate": {"name": "Lacerate",
                 "line": "You open a long red line across {t}!"},
}


# ------------------------------------------------- concentration

def begin_concentration(engine, caster, spell, target) -> Optional[str]:
    """One sustained spell max: a new one drops the old."""
    if caster.id != engine.player.id:
        return None
    meta = caster.metadata
    note = None
    old = meta.get("concentrating")
    if old:
        note = _drop_concentration(engine, quiet=False)
    meta["concentrating"] = {"spell": spell.id,
                             "status": spell.status_effect,
                             "target_id": target.id}
    return note


def _drop_concentration(engine, quiet: bool = True) -> Optional[str]:
    meta = engine.player.metadata
    conc = meta.pop("concentrating", None)
    if not conc:
        return None
    target = engine.player if \
        conc["target_id"] == engine.player.id else \
        engine.npc_manager.npcs.get(conc["target_id"])
    if target is not None and conc.get("status"):
        from characters.status_effects import remove_effect
        remove_effect(target, conc["status"])
    msg = f"Your {conc['spell'].replace('_', ' ')} unravels."
    if not quiet:
        engine.memory_manager.add_event(msg)
    return msg


def concentration_check(engine, character, damage: int) -> None:
    """Damage forces the keep-it check (player only for now)."""
    if character.id != engine.player.id:
        return
    if not character.metadata.get("concentrating"):
        return
    from engine.skills import ability_modifier
    dc = max(10, damage)
    d20 = engine.combat_system.rng.randint(1, 20)
    total = d20 + ability_modifier(
        getattr(character, "constitution", 10))
    if total < dc:
        _drop_concentration(engine, quiet=True)
        engine.memory_manager.add_event(
            "[!] The pain scatters your focus — your spell "
            "unravels!")


# --------------------------------------------------------- cover

def cover_penalty(engine, sx: int, sy: int,
                  tx: int, ty: int) -> float:
    """Hit-chance penalty from soft cover on the shot line."""
    from world.world_map import TerrainType
    wmap = engine.world.map
    covering = 0
    dx, dy = abs(tx - sx), abs(ty - sy)
    x, y = sx, sy
    step_x = 1 if tx > sx else -1
    step_y = 1 if ty > sy else -1
    err = dx - dy
    while (x, y) != (tx, ty):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += step_x
        if e2 < dx:
            err += dx
            y += step_y
        if (x, y) == (tx, ty):
            break
        if 0 <= x < wmap.width and 0 <= y < wmap.height and \
                wmap.terrain[y][x] in (TerrainType.FOREST,
                                       TerrainType.RUBBLE):
            covering += 1
    if covering >= 2:
        return THREE_QTR_COVER_PENALTY
    if covering == 1:
        return HALF_COVER_PENALTY
    return 0.0


# ------------------------------------------------ weapon actions

def weapon_action(engine) -> str:
    """SHIFT+V: the equipped weapon's special move, once per rest."""
    player = engine.player
    if player.metadata.get("weapon_action_used"):
        return ("Your special move is spent — a night's rest "
                "restores it.")
    try:
        from characters.equipment import equipped_weapon
        weapon = equipped_weapon(player)
    except Exception:
        weapon = None
    action_id = ((getattr(weapon, "use_effect", None) or {})
                 .get("weapon_action")) if weapon else None
    spec = ACTIONS.get(action_id or "")
    if spec is None:
        return "Your weapon has no special move."
    target = _adjacent_hostile(engine)
    if target is None:
        return f"{spec['name']}: no enemy in reach."

    player.metadata["weapon_action_used"] = True
    from engine.effects import effective_ac
    from engine.skills import ability_modifier
    rng = engine.combat_system.rng
    total = rng.randint(1, 20) + \
        ability_modifier(getattr(player, "strength", 10))
    if total < effective_ac(target):
        msg = f"{spec['name']} — but {target.name} twists away!"
        engine.memory_manager.add_event(msg)
        engine.advance_turn()
        return msg

    dmg = max(1, int(weapon.damage))
    target.take_damage(dmg)
    second = ""
    from characters.status_effects import apply_effect
    if action_id == "cleave":
        other = _adjacent_hostile(engine, exclude=target.id)
        if other is not None:
            other.take_damage(max(1, dmg // 2))
            second = other.name
            if not other.is_alive():
                engine.combat_system._handle_defeat(
                    player, other, max(1, dmg // 2))
    elif action_id == "topple":
        apply_effect(target, "prone", duration=3)
    elif action_id == "pommel_strike":
        apply_effect(target, "stunned", duration=2)
    elif action_id == "lacerate":
        apply_effect(target, "persistent_damage", duration=99,
                     data={"amount": 2, "kind": "bleeding"})
    msg = spec["line"].format(t=target.name, u=second or "the air") \
        + f" (-{dmg} HP)"
    engine.memory_manager.add_event(msg)
    if not target.is_alive():
        engine.combat_system._handle_defeat(player, target, dmg)
    engine.advance_turn()
    return msg


def action_name(engine) -> Optional[str]:
    """The equipped weapon's move, if any and unspent (hint bar)."""
    player = engine.player
    if player.metadata.get("weapon_action_used"):
        return None
    try:
        from characters.equipment import equipped_weapon
        weapon = equipped_weapon(player)
        aid = (weapon.use_effect or {}).get("weapon_action")
        return ACTIONS[aid]["name"] if aid in ACTIONS else None
    except Exception:
        return None


def _adjacent_hostile(engine, exclude: str = ""):
    from engine.tactics import adjacent_hostiles
    foes = [f for f in
            adjacent_hostiles(engine, engine.player.position)
            if f.id != exclude]
    return foes[0] if foes else None
