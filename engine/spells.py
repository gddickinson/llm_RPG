"""Spell system — mana-powered abilities castable in combat.

Each spell has a name, mana cost, optional damage, optional heal, optional
status effect to apply, and a range. Spell casting is invoked through
`SpellSystem.cast(caster, spell_id, target)`.

The character's `mana` and `max_mana` live on the dataclass; if absent we
synthesize defaults from class and INT/WIS.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.spells")


@dataclass
class Spell:
    id: str
    name: str
    mana_cost: int
    damage: int = 0
    heal: int = 0
    range: float = 5.0
    description: str = ""
    status_effect: str = ""    # name of status to apply on hit
    duration: int = 0          # turns the status persists
    classes: Tuple[str, ...] = ()   # who can learn it


# Spell registry --------------------------------------------------------

SPELL_REGISTRY: Dict[str, Spell] = {
    "magic_missile": Spell(
        id="magic_missile", name="Magic Missile",
        mana_cost=2, damage=6, range=8.0,
        description="An arrow of arcane force, never misses.",
        classes=("wizard", "sorcerer", "warlock"),
    ),
    "fireball": Spell(
        id="fireball", name="Fireball",
        mana_cost=5, damage=12, range=6.0,
        description="A roaring blast of flame.",
        classes=("wizard", "sorcerer"),
    ),
    "frost_ray": Spell(
        id="frost_ray", name="Frost Ray",
        mana_cost=3, damage=5, range=6.0,
        status_effect="paralyzed", duration=2,
        description="Icy beam that may freeze the target.",
        classes=("wizard", "sorcerer", "warlock"),
    ),
    "heal": Spell(
        id="heal", name="Heal",
        mana_cost=3, heal=12, range=1.0,
        description="Restore health to yourself or an ally.",
        classes=("cleric", "paladin", "druid"),
    ),
    "bless": Spell(
        id="bless", name="Bless",
        mana_cost=2, range=1.0,
        status_effect="blessed", duration=4,
        description="Grant a divine boon.",
        classes=("cleric", "paladin"),
    ),
    "shock": Spell(
        id="shock", name="Shock",
        mana_cost=2, damage=4, range=2.0,
        description="A jolt of lightning.",
        classes=("druid", "wizard"),
    ),
    "poison_dart": Spell(
        id="poison_dart", name="Poison Dart",
        mana_cost=2, damage=2, range=4.0,
        status_effect="poisoned", duration=3,
        description="A toxic dart that lingers.",
        classes=("druid", "warlock"),
    ),
}


def starting_spells_for(class_value: str) -> List[Spell]:
    return [s for s in SPELL_REGISTRY.values()
            if class_value in s.classes]


def starting_mana(character) -> int:
    klass = getattr(getattr(character, "character_class", None),
                    "value", "")
    if klass in ("wizard", "sorcerer", "warlock"):
        base = 12
    elif klass in ("cleric", "paladin", "druid"):
        base = 10
    else:
        base = 0
    bonus = ((getattr(character, "intelligence", 10) +
              getattr(character, "wisdom", 10)) // 2 - 10)
    return max(0, base + bonus)


def ensure_mana(character) -> None:
    """Ensure character has mana/max_mana initialized on metadata."""
    meta = getattr(character, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    if "max_mana" not in meta:
        meta["max_mana"] = starting_mana(character)
        meta["mana"] = meta["max_mana"]
    if "spells_known" not in meta:
        klass = getattr(getattr(character, "character_class", None),
                        "value", "")
        meta["spells_known"] = [s.id for s in starting_spells_for(klass)]


def get_mana(character) -> Tuple[int, int]:
    ensure_mana(character)
    meta = character.metadata
    return (meta.get("mana", 0), meta.get("max_mana", 0))


def get_known_spells(character) -> List[Spell]:
    ensure_mana(character)
    ids = character.metadata.get("spells_known", [])
    return [SPELL_REGISTRY[s] for s in ids if s in SPELL_REGISTRY]


class SpellSystem:
    """Spell-casting logic invoked by the engine."""

    def __init__(self, engine):
        self.engine = engine

    # ---- player API --------------------------------------------------

    def cast(self, caster, spell_id: str, target_name: str = None) -> str:
        if spell_id not in SPELL_REGISTRY:
            return f"Unknown spell: {spell_id}"
        spell = SPELL_REGISTRY[spell_id]
        ensure_mana(caster)
        mana, max_mana = get_mana(caster)
        if mana < spell.mana_cost:
            return f"Not enough mana ({mana}/{spell.mana_cost})."
        if spell_id not in caster.metadata.get("spells_known", []):
            return f"You don't know {spell.name}."

        # Resolve target
        target = self._resolve_target(caster, target_name, spell)
        if target is None:
            return f"No valid target for {spell.name}."

        # Range check
        d = self._distance(caster, target)
        if d > spell.range:
            return f"{spell.name}: target out of range."

        # Pay mana
        caster.metadata["mana"] = mana - spell.mana_cost

        # Apply effects
        results = []
        if spell.damage:
            target.take_damage(spell.damage)
            results.append(
                f"{caster.name} hits {target.name} with {spell.name} "
                f"for {spell.damage} damage.")
            # Death from spell
            if not target.is_alive():
                results.append(f"{target.name} is slain by the {spell.name}!")
                self._on_kill(caster, target)
        if spell.heal:
            healed = min(spell.heal, target.max_hp - target.hp)
            target.heal(spell.heal)
            results.append(
                f"{caster.name}'s {spell.name} heals "
                f"{target.name} for {healed} HP.")
        if spell.status_effect:
            try:
                from characters.status_effects import apply_effect
                apply_effect(target, spell.status_effect, spell.duration)
                results.append(
                    f"{target.name} is {spell.status_effect} "
                    f"({spell.duration} turns).")
            except Exception as e:
                logger.warning(f"Status apply failed: {e}")

        msg = " ".join(results) if results else f"{caster.name} casts {spell.name}."
        self.engine.memory_manager.add_event(msg)
        return msg

    # ---- helpers -----------------------------------------------------

    def _resolve_target(self, caster, name: str, spell: Spell):
        # Self-cast for buffs / heals
        if spell.heal or spell.status_effect in ("blessed", "cursed"):
            if not name or name.lower() in ("me", "self", caster.name.lower()):
                return caster
        if not name:
            # Nearest visible hostile, fallback to nearest character
            return self._nearest_visible_hostile(caster, spell.range)
        return self.engine.find_character(name)

    def _nearest_visible_hostile(self, caster, max_range: float):
        nearest, best = None, max_range + 0.1
        for npc in self.engine.npc_manager.npcs.values():
            if npc.id == caster.id or not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            if klass not in ("brigand", "troll", "monster"):
                continue
            d = self._distance(caster, npc)
            if d < best:
                best, nearest = d, npc
        return nearest

    def _distance(self, a, b) -> float:
        return ((a.position[0] - b.position[0]) ** 2 +
                (a.position[1] - b.position[1]) ** 2) ** 0.5

    def _on_kill(self, killer, victim) -> None:
        # Defer to combat system's kill handling
        try:
            self.engine.world.map.remove_character(victim)
            from items.loot_tables import generate_loot
            drops = generate_loot(victim)
            for item in drops:
                self.engine.world.add_item_to_ground(
                    item, victim.position[0], victim.position[1])
        except Exception as e:
            logger.warning(f"Spell-kill cleanup error: {e}")


def rest_recover_mana(character, amount: int = None) -> int:
    """Restore mana while resting; returns the new value."""
    ensure_mana(character)
    meta = character.metadata
    if amount is None:
        amount = max(1, meta.get("max_mana", 0) // 4)
    meta["mana"] = min(meta.get("max_mana", 0),
                       meta.get("mana", 0) + amount)
    return meta["mana"]
