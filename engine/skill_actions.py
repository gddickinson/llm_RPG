"""Skill actions (P12.8) — skills become fighting styles.

PF2e's codified combat verbs, each riding a skill we already roll
through the P12.1 graded core, with degree-sensitive outcomes:

- TRIP (Athletics, SHIFT+T): vs 12 + their STR mod. Crit: prone +
  2 damage. Success: prone. Crit fail: YOU go down.
- DEMORALIZE (Intimidation, SHIFT+I, 3-tile voice range): vs 12 +
  their WIS mod. Crit: Frightened 2; success: Frightened 1. Every
  ATTEMPT sets a 10-minute per-target immunity — the anti-spam
  pattern: they've heard your threats already.
- FEINT (Deception, SHIFT+B): vs 12 + their WIS mod. Crit:
  off-guard 4 turns; success: 2 (one survives this action's own
  tick — enough for your next strike). Crit fail: you overextend —
  YOU are off-guard.
- BATTLE MEDICINE (Medicine, SHIFT+H): burns a bandage, heals a
  living target once per day each (immunity on the patient). Crit:
  15 HP; success: 8; crit fail: you make it worse (-2).

All four cost the turn.
"""

import logging

logger = logging.getLogger("llm_rpg.skill_actions")

DEMORALIZE_RANGE = 3
DEMORALIZE_IMMUNITY_MIN = 10
BM_HEAL = {"crit": 15, "success": 8}


def _foe(engine, reach=1):
    from engine.tactics import adjacent_hostiles
    foes = adjacent_hostiles(engine, engine.player.position)
    if foes or reach <= 1:
        return foes[0] if foes else None
    px, py = engine.player.position
    best, best_d = None, reach + 1
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        if getattr(npc.character_class, "value", "") not in (
                "brigand", "monster", "troll"):
            continue
        d = max(abs(npc.position[0] - px), abs(npc.position[1] - py))
        if d < best_d:
            best, best_d = npc, d
    return best


def _check(engine, skill, dc):
    from engine.skills import Skill, check
    return check(engine.player, getattr(Skill, skill), dc=dc,
                 rng=engine.combat_system.rng)


def trip(engine) -> str:
    from engine.skills import Degree, ability_modifier
    target = _foe(engine)
    if target is None:
        return "Trip: no enemy in reach."
    dc = 12 + ability_modifier(getattr(target, "strength", 10))
    result = _check(engine, "ATHLETICS", dc)
    from characters.status_effects import apply_effect
    if result.degree is Degree.CRIT_FAIL:
        apply_effect(engine.player, "prone", duration=3)
        msg = (f"You lunge at {target.name}'s legs, miss, and land "
               f"face-first — YOU are prone!")
    elif result.success:
        apply_effect(target, "prone", duration=3)
        if result.degree is Degree.CRIT_SUCCESS:
            target.take_damage(2)
            if not target.is_alive():
                engine.combat_system._handle_defeat(
                    engine.player, target, 2)
            msg = (f"You sweep {target.name} down HARD — they hit "
                   f"the ground (-2 HP), prone!")
        else:
            msg = f"You hook {target.name}'s legs — they go down!"
    else:
        msg = f"{target.name} keeps their footing."
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


def demoralize(engine) -> str:
    from engine.skills import Degree, ability_modifier
    target = _foe(engine, reach=DEMORALIZE_RANGE)
    if target is None:
        return "Demoralize: nobody in shouting range."
    now = engine.world.time
    if target.metadata.get("demoralize_immune_until", 0) > now:
        return (f"{target.name} has heard your threats already — "
                f"words are spent here.")
    target.metadata["demoralize_immune_until"] = \
        now + DEMORALIZE_IMMUNITY_MIN
    dc = 12 + ability_modifier(getattr(target, "wisdom", 10))
    result = _check(engine, "INTIMIDATION", dc)
    from characters.status_effects import apply_effect
    if result.success:
        value = 2 if result.degree is Degree.CRIT_SUCCESS else 1
        apply_effect(target, "frightened", duration=99, value=value)
        msg = (f"Your roar shakes {target.name} — "
               f"Frightened {value}!")
    else:
        msg = f"{target.name} doesn't flinch."
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


def feint(engine) -> str:
    from engine.skills import Degree, ability_modifier
    target = _foe(engine)
    if target is None:
        return "Feint: no enemy in reach."
    dc = 12 + ability_modifier(getattr(target, "wisdom", 10))
    result = _check(engine, "DECEPTION", dc)
    from characters.status_effects import apply_effect
    if result.degree is Degree.CRIT_FAIL:
        apply_effect(engine.player, "off_guard", duration=2)
        msg = ("Your feint fools nobody — you overextend and "
               "leave yourself open!")
    elif result.success:
        # +1 because this action's own turn tick consumes one
        turns = 4 if result.degree is Degree.CRIT_SUCCESS else 2
        apply_effect(target, "off_guard", duration=turns)
        msg = (f"Your blade goes one way, your eyes another — "
               f"{target.name} is off-guard!")
    else:
        msg = f"{target.name} reads the feint."
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


def battle_medicine(engine, target=None) -> str:
    from engine.skills import Degree
    player = engine.player
    patient = target or player
    day = engine.world.time // (24 * 60)
    if patient.metadata.get("battle_med_day") == day:
        who = "You've" if patient is player else \
            f"{patient.name} has"
        return f"{who} been patched once today — flesh needs time."
    bandage = next((i for i in player.inventory
                    if getattr(i, "id", "") == "bandage"), None)
    if bandage is None:
        return "Battle Medicine needs a bandage."
    # PT4 finding: don't burn the bandage (and the daily immunity)
    # when there's nothing to treat
    try:
        from engine.infection import infected
        clean = not infected(patient) if patient is player else True
    except Exception:
        clean = True
    if patient.hp >= patient.max_hp and clean:
        return ("No wounds worth a dressing — save the bandage.")
    from engine.item_use import _remove_one
    _remove_one(player, bandage)
    patient.metadata["battle_med_day"] = day
    result = _check(engine, "MEDICINE", 13)
    if result.degree is Degree.CRIT_FAIL:
        patient.take_damage(2)
        if patient.hp <= 0:
            patient.hp = 1
        msg = "Your hands slip — you make the wound worse. (-2 HP)"
    elif result.success:
        amount = BM_HEAL["crit"] if \
            result.degree is Degree.CRIT_SUCCESS else \
            BM_HEAL["success"]
        before = patient.hp
        patient.heal(amount)
        msg = (f"Field dressing, quick and sure "
               f"(+{patient.hp - before} HP).")
    else:
        msg = "The dressing holds nothing — the bandage is wasted."
    if patient is player:
        try:   # tending races the infection (P12.12)
            from engine.infection import treat
            if result.degree is not Degree.CRIT_FAIL:
                msg += treat(engine, result.degree)
        except Exception:
            pass
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg
