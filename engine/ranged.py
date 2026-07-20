"""Ranged fire (split from game_api_mixin, P12.7 round).

`shoot_ranged(engine, ...)` — bow/crossbow/thrown fire at the lock
or nearest hostile, with ammo, aim, chew-gate, and true LOS.
"""

import logging

logger = logging.getLogger("llm_rpg.ranged")


def shoot_ranged(engine, target_name=None, aimed=False) -> str:
    """Fire a ranged attack at the named target (or nearest enemy).

    Requires an equipped ranged weapon. Consumes ammo of the matching
    ammo_type. Thrown weapons fire without ammo. `aimed` (SHIFT+R):
    +2 damage for an extra minute spent lining up the shot.
    """
    from items.item import Item

    try:   # the chew delay costs tempo (P12.5)
        from engine.food import attack_gate
        gate = attack_gate(self)
        if gate:
            return gate
    except Exception:
        pass
    try:
        from characters.equipment import equipped_weapon
        weapon = equipped_weapon(engine.player)
    except Exception:
        weapon = None
    if weapon is None or not weapon.is_ranged_weapon():
        msg = "You have no ranged weapon equipped."
        engine.memory_manager.add_event(msg)
        return msg

    weapon_type = _weapon_type_str(engine, weapon)

    # Ammo check (thrown weapons skip)
    ammo_item = None
    if weapon.weapon_kind == "ranged" and weapon.ammo_type:
        ammo_item = _find_ammo(engine, weapon.ammo_type)
        if ammo_item is None:
            msg = f"You're out of {weapon.ammo_type}s!"
            engine.memory_manager.add_event(msg)
            return msg

    # Resolve target
    target = None
    if target_name:
        target = engine.find_character(target_name)
    if target is None:
        target = engine.targeting.current()   # the lock (P8.7)
    if target is None:
        target = _nearest_hostile(engine)
    if target is None:
        return "No target in sight."

    # Range + true line of sight (P8.6/P8.7)
    ok, why = engine.targeting.can_hit(target)
    if not ok:
        engine.memory_manager.add_event(why)
        return why

    from engine.effects import effective_weapon_damage_bonus
    from engine.skill_combat import ranged_damage_bonus
    dex_bonus = max(0, (engine.player.dexterity - 10) // 2)
    damage = max(1, int(weapon.damage) + dex_bonus
                 + effective_weapon_damage_bonus(engine.player)
                 + ranged_damage_bonus(engine.player))   # marksmanship
    if aimed:
        damage += 2
        engine.world.advance_time(1)
        engine.memory_manager.add_event("You take careful aim...")

    if ammo_item is not None:
        _consume_one_ammo(engine, ammo_item)
    try:   # a loosed shot trains Marksmanship (pet-roll-free — no RNG churn)
        from engine.skill_progression import add_skill_xp
        add_skill_xp(engine.player, "marksmanship", 4)
    except Exception:
        pass

    proj = engine.projectile_manager.spawn(
        engine.player, target, damage, weapon_type=weapon_type)
    # face the target + play the loose (bow-arm) animation — the shooter is SEEN
    # firing the weapon it holds (George: characters holding the correct weapon)
    try:
        from engine import anim
        anim.face(engine.player, target.position)
        engine.player.metadata["_atk_seq"] = \
            engine.player.metadata.get("_atk_seq", 0) + 1
    except Exception:
        pass
    ammo_label = f" ({weapon.ammo_type} -1)" if ammo_item is not None else ""
    msg = f"You loose a {proj.weapon_type} at {target.name}{ammo_label}."
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg

def _weapon_type_str(engine, weapon) -> str:
    name = (weapon.name or "").lower()
    for key in ("longbow", "crossbow", "thrown knife", "javelin",
                "sling", "bow"):
        if key in name or key.replace(" ", "_") in (weapon.id or ""):
            return key.replace(" ", "_")
    return "bow"

def _find_ammo(engine, ammo_type: str):
    from items.item import Item
    for it in engine.player.inventory:
        if isinstance(it, Item) and it.is_ammo() and \
                it.ammo_type == ammo_type and it.quantity > 0:
            return it
    return None

def _consume_one_ammo(engine, ammo_item) -> None:
    ammo_item.quantity -= 1
    if ammo_item.quantity <= 0:
        try:
            engine.player.inventory.remove(ammo_item)
        except ValueError:
            pass

def _nearest_hostile(engine):
    px, py = engine.player.position
    best = None
    best_d = 999
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        klass = getattr(npc.character_class, "value", "")
        if klass not in ("brigand", "troll", "monster"):
            continue
        d = ((npc.position[0] - px) ** 2 +
             (npc.position[1] - py) ** 2) ** 0.5
        if d < best_d:
            best_d, best = d, npc
    return best

