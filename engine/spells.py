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
    concentration: bool = False    # one sustained spell max (P12.7)
    classes: Tuple[str, ...] = ()   # who can learn it
    school: str = ""           # M1 evocation/restoration/nature/… (flavour+UI)
    tier: int = 1              # M1 1 (novice) … 5 (master); gates learning
    requires: Dict[str, Any] = field(default_factory=dict)   # M1 min_level/min_int/…
    world_effect: Dict[str, Any] = field(default_factory=dict)  # M2 tile/build/…


# M1 — a spell TIER unlocks at a caster level; higher tiers need more levels
_TIER_MIN_LEVEL = {1: 1, 2: 3, 3: 5, 4: 8, 5: 12}


def max_tier_for_level(level: int) -> int:
    """The highest spell tier a caster of `level` may learn."""
    best = 1
    for tier, req in _TIER_MIN_LEVEL.items():
        if level >= req:
            best = max(best, tier)
    return best


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
            concentration=entry.get("concentration", False),
            classes=tuple(entry.get("classes", ())),
            school=entry.get("school", ""),
            tier=int(entry.get("tier", 1)),
            requires=entry.get("requires", {}) or {},
            world_effect=entry.get("world_effect", {}) or {},
        )
    return out


SPELL_REGISTRY: Dict[str, Spell] = _build_spells()


def class_spells(class_value: str) -> List[Spell]:
    """Every spell on `class_value`'s list, any tier (the full learnable set)."""
    return [s for s in SPELL_REGISTRY.values() if class_value in s.classes]


def starting_spells_for(class_value: str) -> List[Spell]:
    """The NOVICE (tier-1) spells a fresh caster of this class begins with — no
    longer the whole list, so higher tiers are earned by levelling / study (M1)."""
    return [s for s in class_spells(class_value) if s.tier <= 1]


def _stat(character, name: str) -> int:
    try:
        from engine.effects import effective_stat
        return effective_stat(character, name)
    except Exception:
        return getattr(character, name, 10)


def can_learn(character, spell) -> Tuple[bool, str]:
    """Could `character` learn `spell` now? Checks the tier-by-level gate + the
    spell's `requires` block (min_level, min_int/wis/cha, a prereq spell). The
    single chokepoint for level-up grants AND tome study (M1)."""
    if isinstance(spell, str):
        spell = SPELL_REGISTRY.get(spell)
        if spell is None:
            return False, "unknown spell"
    lvl = getattr(character, "level", 1)
    req = spell.requires or {}
    if lvl < req.get("min_level", 0):
        return False, f"requires level {req['min_level']}"
    if spell.tier > max_tier_for_level(lvl):
        return False, f"a tier-{spell.tier} spell — too advanced yet"
    for stat in ("intelligence", "wisdom", "charisma"):
        need = req.get(f"min_{stat}")
        if need and _stat(character, stat) < need:
            return False, f"requires {stat} {need}"
    prereq = req.get("prereq")
    known = (getattr(character, "metadata", None) or {}).get("spells_known", [])
    if prereq and prereq not in known:
        pn = SPELL_REGISTRY.get(prereq)
        return False, f"master {pn.name if pn else prereq} first"
    return True, ""


def learn_new_spells(character) -> List[str]:
    """Grant every class spell the caster now qualifies for but doesn't know —
    the innate/trained route fired on level-up. Returns the newly-learnt names."""
    ensure_mana(character)
    klass = getattr(getattr(character, "character_class", None), "value", "")
    known = character.metadata.setdefault("spells_known", [])
    learnt = []
    for spell in class_spells(klass):
        if spell.id in known:
            continue
        ok, _ = can_learn(character, spell)
        if ok:
            known.append(spell.id)
            learnt.append(spell.name)
    return learnt


def teach_spell(character, spell_id: str, force: bool = False) -> Tuple[bool, str]:
    """Learn ONE spell (a tome/trainer). Honours `can_learn` unless `force` (a
    powerful artifact tome may bypass the gate). Returns (ok, message)."""
    spell = SPELL_REGISTRY.get(spell_id)
    if spell is None:
        return False, "unknown spell"
    ensure_mana(character)
    known = character.metadata.setdefault("spells_known", [])
    if spell_id in known:
        return False, f"already knows {spell.name}"
    if not force:
        ok, why = can_learn(character, spell)
        if not ok:
            return False, f"can't learn {spell.name} — {why}"
    known.append(spell_id)
    return True, f"learned {spell.name}"


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


def _apply_spellcraft(character) -> None:
    """Fold the SPELLCRAFT skill's mana bonus into max mana, reconciling only
    the DELTA (tracked in `spellcraft_mana`) so it's idempotent and a no-op at
    skill 0 — no change for anyone who hasn't studied spellcraft."""
    try:
        from engine.skill_combat import spellcraft_mana_bonus
        want = int(spellcraft_mana_bonus(character))
    except Exception:
        return
    meta = character.metadata
    have = int(meta.get("spellcraft_mana", 0))
    if want == have:
        return
    delta = want - have
    meta["max_mana"] = max(0, int(meta.get("max_mana", 0)) + delta)
    meta["mana"] = max(0, min(int(meta.get("mana", 0)) + delta,
                              meta["max_mana"]))
    meta["spellcraft_mana"] = want


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
    _apply_spellcraft(character)
    _apply_familiar_mana(character)


def _apply_familiar_mana(character) -> None:
    """Fold a familiar's `mana_max` gift into the pool, delta-reconciled
    (tracked in `familiar_mana`) so it's a no-op with no such familiar."""
    try:
        from engine.familiars import familiar_bonus
        want = int(familiar_bonus(character, "mana_max"))
    except Exception:
        return
    meta = character.metadata
    have = int(meta.get("familiar_mana", 0))
    if want == have:
        return
    delta = want - have
    meta["max_mana"] = max(0, int(meta.get("max_mana", 0)) + delta)
    meta["mana"] = max(0, min(int(meta.get("mana", 0)) + delta,
                              meta["max_mana"]))
    meta["familiar_mana"] = want


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

        # M2 — a PURE world spell shapes a tile, not a character
        if spell.world_effect and not (spell.damage or spell.heal
                                       or spell.status_effect):
            from engine import spell_world
            return spell_world.cast_tile_spell(self, caster, spell)

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
        try:   # working magic trains Spellcraft (pet-roll-free — no RNG churn)
            if caster.id == getattr(self.engine.player, "id", None):
                from engine.skill_progression import add_skill_xp
                add_skill_xp(caster, "spellcraft", 5)
        except Exception:
            pass

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
            # The world burns too (P10.2) — overworld blasts only
            try:
                if self.engine.active_zone() is None:
                    tx, ty = target.position
                    razed = self.engine.tile_damage.damage_radius(
                        tx, ty, spell.damage, spell.area, "fire")
                    if razed:
                        results.append(
                            f"The blast razes {razed} of the "
                            f"surroundings!")
                    # flame lingers at the impact (P10.3)
                    if spell.id == "fireball":
                        lay = self.engine.surfaces_layer
                        lay.ignite(tx, ty, intensity=2)
                        for ddx, ddy in ((1, 0), (-1, 0),
                                         (0, 1), (0, -1)):
                            lay.ignite(tx + ddx, ty + ddy,
                                       intensity=1)
            except Exception:
                pass
        elif spell.damage:
            target.take_damage(spell.damage)
            results.append(
                f"{caster.name} hits {target.name} with {spell.name} "
                f"for {spell.damage} damage.")
            if spell.id == "shock":   # lightning + water (P14.2a)
                try:
                    if self.engine.active_zone() is None:
                        tx, ty = target.position
                        self.engine.surfaces_layer.electrify(tx, ty)
                except Exception:
                    pass
            # Death from spell
            if not target.is_alive():
                results.append(f"{target.name} is slain by the {spell.name}!")
                self._on_kill(caster, target, spell.damage)
        # M2 — a damage spell may ALSO carry a world_effect (a firestorm razes +
        # ignites the struck ground); applied at the impact tile, overworld only
        if spell.world_effect:
            try:
                if self.engine.active_zone() is None:
                    from engine import spell_world
                    tx, ty = target.position
                    results += spell_world.apply(self.engine, caster,
                                                 spell, tx, ty)
            except Exception:
                pass

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
                if spell.concentration:   # one sustained max (P12.7)
                    from engine.combat_depth import begin_concentration
                    dropped = begin_concentration(
                        self.engine, caster, spell, target)
                    if dropped:
                        results.append(dropped)
            except Exception as e:
                logger.warning(f"Status apply failed: {e}")

        if spell.id == "farsight" and \
                caster.id == self.engine.player.id:   # P15.11
            try:
                from engine.discovery import reveal_around
                n = reveal_around(self.engine, *caster.position,
                                  radius=18)
                results.append(f"The land unrolls in your mind "
                               f"({n} tiles charted).")
            except Exception:
                pass

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
        # Self-cast for buffs / heals / self-utility (P15.11 farsight)
        if spell.heal or spell.id in ("farsight",) or \
                spell.status_effect in (
                "blessed", "cursed", "water_walking",
                "swimmers_grace", "flying", "hasted", "keen_sight"):
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
