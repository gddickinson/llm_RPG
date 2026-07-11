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
    area: float = 0.0          # blast radius in tiles (P10.1)
    classes: Tuple[str, ...] = ()   # who can learn it


# Spell registry — loaded from data/spells.json --------------------------

def _build_spells() -> Dict[str, Spell]:
    from items.data_loader import load_data_file
    out: Dict[str, Spell] = {}
    for sid, entry in load_data_file("spells.json").items():
        out[sid] = Spell(
            id=entry.get("id", sid),
            name=entry["name"],
            mana_cost=entry["mana_cost"],
            damage=entry.get("damage", 0),
            heal=entry.get("heal", 0),
            range=entry.get("range", 5.0),
            description=entry.get("description", ""),
            status_effect=entry.get("status_effect", ""),
            duration=entry.get("duration", 0),
            area=entry.get("area", 0.0),
            classes=tuple(entry.get("classes", ())),
        )
    return out


SPELL_REGISTRY: Dict[str, Spell] = _build_spells()


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
        # Player attack spells need true line of sight (P8.7)
        if spell.damage and target.id != caster.id and \
                caster.id == getattr(self.engine.player, "id", None):
            try:
                ok, why = self.engine.targeting.can_hit(target)
                if not ok:
                    return why
            except Exception:
                pass

        # Pay mana
        caster.metadata["mana"] = mana - spell.mana_cost

        # Apply effects
        results = []
        if spell.damage and spell.area > 0:
            # Area damage (P10.1): everyone near the impact except
            # the caster — friendly fire is REAL, companions included
            victims = self._blast_victims(caster, target, spell.area)
            names = []
            for victim in victims:
                victim.take_damage(spell.damage)
                names.append(victim.name)
                if not victim.is_alive():
                    self._on_kill(caster, victim, spell.damage)
            results.append(
                f"{caster.name}'s {spell.name} engulfs "
                f"{', '.join(names)} for {spell.damage} damage each!")
            fallen = [v.name for v in victims if not v.is_alive()]
            if fallen:
                results.append(
                    f"Slain in the blast: {', '.join(fallen)}.")
        elif spell.damage:
            target.take_damage(spell.damage)
            results.append(
                f"{caster.name} hits {target.name} with {spell.name} "
                f"for {spell.damage} damage.")
            # Death from spell
            if not target.is_alive():
                results.append(f"{target.name} is slain by the {spell.name}!")
                self._on_kill(caster, target, spell.damage)
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

        # Visual particle burst at target position
        try:
            tx, ty = target.position
            if hasattr(self.engine, "trigger_spell_visual"):
                self.engine.trigger_spell_visual(spell_id, tx, ty)
        except Exception:
            pass
        return msg

    # ---- helpers -----------------------------------------------------

    def _resolve_target(self, caster, name: str, spell: Spell):
        # Self-cast for buffs / heals
        if spell.heal or spell.status_effect in ("blessed", "cursed"):
            if not name or name.lower() in ("me", "self", caster.name.lower()):
                return caster
        if not name:
            # The player's ranged lock aims spells too (P8.7)
            if caster.id == getattr(self.engine.player, "id", None):
                try:
                    locked = self.engine.targeting.current()
                    if locked is not None and \
                            self._distance(caster, locked) <= \
                            spell.range:
                        return locked
                except Exception:
                    pass
            return self._nearest_visible_hostile(caster, spell.range)
        return self.engine.find_character(name)

    def _blast_victims(self, caster, target, radius: float) -> list:
        """Everyone within the blast radius of the target's tile,
        excluding the caster — same-space rules apply (a blast in the
        crypt doesn't scorch the street)."""
        engine = self.engine
        cx, cy = target.position
        zone = None
        try:
            zone = engine.active_zone()
        except Exception:
            pass
        zname = getattr(zone, "name", None)
        out = [target]
        candidates = list(engine.npc_manager.npcs.values())
        candidates.append(engine.player)
        for ch in candidates:
            if ch.id in (caster.id, target.id) or not ch.is_active():
                continue
            if ch.id != engine.player.id:
                chz = getattr(ch, "metadata", {}).get("zone")
                if zone is not None and chz != zname:
                    continue                # a floor away is safe
                if zone is None:
                    if chz is not None:
                        continue
                    try:
                        from engine.presence import is_indoors
                        if is_indoors(engine, ch):
                            continue        # walls shield them
                    except Exception:
                        pass
            nx, ny = ch.position
            if ((nx - cx) ** 2 + (ny - cy) ** 2) ** 0.5 <= radius:
                out.append(ch)
        return out

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

    def _on_kill(self, killer, victim, damage: int = 0) -> None:
        """Route through the ONE defeat handler (PT3.3 finding: spell
        kills left 0-HP 'alive' zombies — no defeat(), no XP, no
        quest credit, still targetable)."""
        try:
            self.engine.combat_system._handle_defeat(killer, victim,
                                                     damage)
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
