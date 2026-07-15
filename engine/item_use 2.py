"""Item use (P12.4 split from player_actions).

Every on-use payload lives here: scrolls cast, tomes teach, manuals
train, potions buff, remedies cure, drinks quench (P12.3), food
heals and feeds. `use_item(engine, name)` is the single entry.
"""

import logging

logger = logging.getLogger("llm_rpg.item_use")


def use_item(engine, item_name: str) -> str:
    if not item_name:
        return "Specify which item to use."
    player = engine.player
    for it in player.inventory:
        it_name = it.name if hasattr(it, "name") else str(it)
        if item_name.lower() not in it_name.lower():
            continue

        # Scroll: cast embedded spell
        use_eff = getattr(it, "use_effect", None) or {}
        if "spell" in use_eff:
            spell_id = use_eff["spell"]
            try:
                msg = engine.cast_spell(spell_id)
            except Exception:
                msg = f"You read the {it_name}."
            _remove_one(player, it)
            engine.memory_manager.add_event(
                f"You read the {it_name}.")
            engine.advance_turn()
            return msg

        # Spell-teaching tome
        if "teach_spell" in use_eff:
            spell_id = use_eff["teach_spell"]
            from engine.spells import SPELL_REGISTRY, ensure_mana
            spell = SPELL_REGISTRY.get(spell_id)
            if spell is None:
                return f"The {it_name} is gibberish."
            ensure_mana(player)
            known = player.metadata.setdefault("spells_known", [])
            if spell_id in known:
                return f"You already know {spell.name}."
            known.append(spell_id)
            player.inventory.remove(it)
            msg = (f"You study the {it_name} and learn "
                   f"{spell.name}!")
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg

        # Permanent stat increase (training manual)
        if "permanent_stat" in use_eff:
            stat = use_eff["permanent_stat"]
            amount = int(use_eff.get("amount", 1))
            old = getattr(player, stat, 10)
            setattr(player, stat, old + amount)
            player.inventory.remove(it)
            msg = (f"You study the {it_name}. "
                   f"{stat.upper()[:3]} {old} -> {old + amount}.")
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg

        # Temporary buff (potion of might / speed)
        if "effect" in use_eff:
            try:
                from characters.status_effects import apply_effect
                apply_effect(player, use_eff["effect"],
                             int(use_eff.get("duration", 5)))
            except Exception:
                pass
            _remove_one(player, it)
            msg = f"You drink the {it_name}."
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg

        if "cure" in use_eff:
            try:
                from characters.status_effects import remove_effect
                remove_effect(player, use_eff["cure"])
            except Exception:
                pass
            _remove_one(player, it)
            msg = f"You drink the {it_name}."
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg

        # The right remedy clears a disease (P8.2)
        try:
            from engine.disease import try_cure_with_item
            cured = try_cure_with_item(engine, player, it)
            if cured:
                _remove_one(player, it)
                engine.advance_turn()
                return cured
        except Exception:
            pass

        if "reveal" in use_eff:            # P15.11 map items
            from engine.discovery import use_map_item
            msg = use_map_item(engine, it)
            _remove_one(player, it)
            engine.advance_turn()
            return msg or f"You study the {it_name}."

        # Food: tempo + freshness + brews + combos (P12.5)
        try:
            from engine.food import eat_food, is_food
            if is_food(it):
                msg = eat_food(engine, it)
                if msg is None:
                    return "You're already at full health."
                from engine import anim
                anim.emote(player, "eat")          # bring it to the mouth (P34.10)
                _remove_one(player, it)
                engine.advance_turn()
                return msg
        except Exception as e:
            logger.debug(f"Food path error: {e}")

        if "thirst" in use_eff:            # P12.3 drinks
            from characters.needs import drink
            drink(player, int(use_eff["thirst"]))
            from engine import anim
            anim.emote(player, "drink")            # tilt back and sip (P34.10)
            if getattr(it, "heal_amount", 0):
                player.heal(it.heal_amount)
            _remove_one(player, it)
            msg = f"You drink the {it_name}. Your thirst eases."
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg

        heal = getattr(it, "heal_amount", 0)
        if heal:
            from characters.needs import get_hunger, feed
            hungry = get_hunger(player) > 10
            if player.hp >= player.max_hp and not hungry:
                return "You're already at full health."
            player.heal(heal)
            # Eating also satisfies hunger (bread -32, jerky -24, ...)
            feed(player, amount=heal * 8)
            _remove_one(player, it)
            msg = f"You consume {it_name}" + (
                f" and heal {heal} HP." if player.hp <= player.max_hp
                else ".")
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg
        else:
            # Generic use — e.g. for quest items / keys
            msg = f"You use {it_name}."
            engine.memory_manager.add_event(msg)
            engine.advance_turn()
            return msg
    return f"You don't have {item_name}."

TRANSMUTE_RATE = 0.4
TRANSMUTE_MANA = 4


def transmute_item(engine, item) -> str:
    """P13.1 (OSRS High Alchemy): any carried item runs to coin at
    40% of value — the universal value floor. Costs mana; wizards
    and sorcerers know the working."""
    player = engine.player
    from engine.spells import ensure_mana
    ensure_mana(player)
    if "transmute" not in player.metadata.get("spells_known", []):
        return "You don't know the transmutation working."
    if player.metadata.get("mana", 0) < TRANSMUTE_MANA:
        return (f"Transmute needs {TRANSMUTE_MANA} mana "
                f"({player.metadata.get('mana', 0)} left).")
    if item not in player.inventory:
        return "You can only transmute what you carry."
    player.metadata["mana"] -= TRANSMUTE_MANA
    gold = max(1, int(getattr(item, "value", 1) * TRANSMUTE_RATE))
    name = getattr(item, "name", str(item))
    _remove_one(player, item)
    player.gold += gold
    msg = (f"The {name} runs like wax between your fingers and "
           f"hardens into {gold}g.")
    engine.memory_manager.add_event(msg)
    engine.advance_turn()
    return msg


def _remove_one(char, item) -> None:
    """Decrement stack by 1, removing if depleted. Removal is by
    IDENTITY: dataclass items compare equal, and list.remove would
    take the first equal twin instead of the item in hand."""
    if getattr(item, "stackable", False) and item.quantity > 1:
        item.quantity -= 1
        return
    for i, it in enumerate(char.inventory):
        if it is item:
            del char.inventory[i]
            return
    try:
        char.inventory.remove(item)
    except ValueError:
        pass
