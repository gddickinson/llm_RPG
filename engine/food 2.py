"""Food economy (P12.5) — eating is a combat decision.

OSRS's tempo rule: eating sets a shared CHEW DELAY — for the next
EAT_DELAY turns you cannot attack (melee or ranged). One COMBO food
(the Meat Pie) ignores and bypasses the delay: burst healing for a
price. One BREW (Hearty Brew) heals past your maximum HP but dulls
your offense (cursed) while it works.

KCD's freshness: perishable food carries freshness 0-100, decaying
each night in your pack. Under 50 it heals half and risks poison
(chance grows as it rots); at 0 it's a poisoner's tool. A hearth
re-bakes everything you carry back to 100 — cooking finally has a
combat reason to exist. (Stolen-flag laundering waits on a theft
marking system — noted in the plan.)
"""

import logging

logger = logging.getLogger("llm_rpg.food")

EAT_DELAY = 2            # turns you cannot attack after eating
FRESH_START = 100
DECAY_PER_NIGHT = 15
STALE_AT = 50            # below this: half heal + poison risk
BREW_OVERHEAL = 1.15     # brews heal to 115% of max
BREW_CURSE_TURNS = 10


def is_food(item) -> bool:
    return bool((getattr(item, "use_effect", None) or {}).get("food"))


def freshness_of(item) -> int:
    eff = getattr(item, "use_effect", None) or {}
    if not eff.get("perishable"):
        return FRESH_START
    return int(eff.get("freshness", FRESH_START))


def chewing(engine) -> int:
    """Turns of chew delay remaining (0 = free to swing)."""
    ate = engine.player.metadata.get("ate_turn")
    if ate is None:
        return 0
    left = EAT_DELAY - (engine.turn_counter - ate)
    return max(0, left)


def attack_gate(engine) -> str:
    """Non-empty message while the chew delay holds."""
    left = chewing(engine)
    if left <= 0:
        return ""
    return ("You're still swallowing — no opening to strike. "
            f"({left} more turn{'s' if left > 1 else ''})")


def eat_food(engine, item):
    """The food path of item use: tempo, freshness, brews, combos.
    Returns None (refusal, nothing consumed) when there's no point."""
    player = engine.player
    eff = getattr(item, "use_effect", None) or {}
    heal = getattr(item, "heal_amount", 0)
    fresh = freshness_of(item)
    from characters.needs import get_hunger
    if not eff.get("brew") and player.hp >= player.max_hp and \
            get_hunger(player) <= 10:
        return None
    notes = []

    if eff.get("brew"):
        cap = int(player.max_hp * BREW_OVERHEAL)
        player.hp = min(cap, player.hp + heal)
        from characters.status_effects import apply_effect
        apply_effect(player, "cursed", duration=BREW_CURSE_TURNS)
        notes.append(f"Warmth floods you past your limits "
                     f"({player.hp}/{player.max_hp} HP) — but your "
                     f"sword arm feels heavy.")
    else:
        if fresh < STALE_AT:
            heal = max(1, heal // 2)
            risk = (STALE_AT - fresh) / 100.0
            if engine.combat_system.rng.random() < risk:
                from characters.status_effects import apply_effect
                apply_effect(player, "poisoned", duration=4)
                notes.append("It tastes WRONG — your stomach knots.")
            else:
                notes.append("Stale, but it goes down.")
        player.heal(heal)
        notes.insert(0, f"(+{heal} HP)")

    from characters.needs import feed
    feed(player, amount=max(10, heal * 6))
    if eff.get("thirst"):
        from characters.needs import drink
        drink(player, int(eff["thirst"]))

    if not eff.get("combo"):
        player.metadata["ate_turn"] = engine.turn_counter
        tempo = ""
    else:
        tempo = " You barely break stride."
    msg = f"You eat the {item.name}. " + " ".join(notes) + tempo
    engine.memory_manager.add_event(msg)
    return msg


def decay_inventory(engine) -> int:
    """Nightly: everything perishable in the pack ages."""
    aged = 0
    for item in getattr(engine.player, "inventory", []):
        eff = getattr(item, "use_effect", None) or {}
        if not eff.get("perishable"):
            continue
        eff["freshness"] = max(
            0, int(eff.get("freshness", FRESH_START)) - DECAY_PER_NIGHT)
        aged += 1
    return aged


def refresh_rations(engine) -> int:
    """A hearth re-bakes carried perishables back to fresh — and
    nobody recognizes a re-baked loaf (P12.9b laundering)."""
    refreshed = 0
    for item in getattr(engine.player, "inventory", []):
        eff = getattr(item, "use_effect", None) or {}
        if not eff.get("food"):
            continue
        if eff.pop("stolen", None):
            refreshed += 1
        if eff.get("perishable") and \
                int(eff.get("freshness", FRESH_START)) < FRESH_START:
            eff["freshness"] = FRESH_START
            refreshed += 1
    return refreshed
