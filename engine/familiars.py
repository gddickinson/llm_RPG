"""Familiars (George: wizards & witches). A caster binds ONE familiar — a
cat, an owl, a raven, a toad, a serpent, a warlock's imp — that trails a
step behind and grants a passive magical benefit: faster mana regen, a
deeper mana well, or keener sight. Bound at a place of magical study (an
arcane/divine trainer), one at a time; rebinding replaces it.

Pure over the character (state on `player.metadata["familiar"]`, so it
rides the save); the effects are read by the mana-regen tick, the mana
pool (`spells.ensure_mana`), and `effective_visibility`. The follower is
drawn by `renderer_overlays.draw_familiar`.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.familiars")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "familiars.json")
_SPECIES = None
CASTER_CLASSES = {"wizard", "sorcerer", "warlock", "bard", "druid",
                  "cleric", "paladin"}


def species() -> dict:
    global _SPECIES
    if _SPECIES is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _SPECIES = json.load(fh).get("species", {})
        except Exception as e:                       # pragma: no cover
            logger.info(f"Familiar data unavailable: {e}")
            _SPECIES = {}
    return _SPECIES


def _class(character) -> str:
    return getattr(getattr(character, "character_class", None), "value", "")


def can_bind(character) -> bool:
    return _class(character) in CASTER_CLASSES


def _allowed(spec, cls) -> bool:
    classes = spec.get("classes", ["*"])
    return "*" in classes or cls in classes


def available(character):
    """[(species_id, spec)] the character may bind."""
    if not can_bind(character):
        return []
    cls = _class(character)
    return [(sid, sp) for sid, sp in species().items()
            if _allowed(sp, cls)]


def active(character):
    return (getattr(character, "metadata", None) or {}).get("familiar")


def familiar_bonus(character, key) -> int:
    fam = active(character)
    if not fam:
        return 0
    sp = species().get(fam.get("species"), {})
    try:
        return int((sp.get("effect", {}) or {}).get(key, 0))
    except (TypeError, ValueError):
        return 0


def bind(engine, species_id: str) -> str:
    p = engine.player
    if not can_bind(p):
        return "Only those versed in magic may bind a familiar."
    sp = species().get(species_id)
    if sp is None:
        return "No such familiar answers."
    if not _allowed(sp, _class(p)):
        return f"{sp['name'].capitalize()} will not answer your calling."
    old = active(p)
    p.metadata["familiar"] = {"species": species_id, "name": sp["name"],
                              "loyalty": 12,
                              "pos": list(getattr(p, "position", (0, 0)))}
    try:
        from engine.spells import ensure_mana
        ensure_mana(p)                               # fold in a mana_max bonus
    except Exception:
        pass
    verb = "rebind" if old else "bind"
    try:
        engine.memory_manager.add_event(
            f"[Familiar] You {verb} {sp['name']} as your familiar — "
            f"{sp['desc']}")
    except Exception:
        pass
    return f"You {verb} {sp['name']} as your familiar."


def dismiss(engine) -> str:
    p = engine.player
    fam = active(p)
    if not fam:
        return "You have no familiar."
    name = fam.get("name", "your familiar")
    p.metadata.pop("familiar", None)
    try:
        from engine.spells import ensure_mana
        ensure_mana(p)
    except Exception:
        pass
    return f"You release {name}."


def follow(character, old_pos) -> None:
    """Trail a step behind the caster (like a pet)."""
    fam = active(character)
    if fam is not None:
        fam["pos"] = list(old_pos)


# ---- the E-menu (bind at a place of power) -----------------------------

def overlay_lines(engine):
    p = engine.player
    lines = ["Bind a familiar to trail you and lend its gift.", ""]
    cur = active(p)
    if cur:
        lines.append(f"Bound now: {cur['name']} "
                     f"({_effect_text(cur['species'])}).")
        lines.append("")
    opts = available(p)
    if not opts:
        lines.append("Your calling knows no familiars.")
        return lines
    for i, (sid, sp) in enumerate(opts, 1):
        lines.append(f"  {i}. {sp['name']} — {_effect_text(sid)}")
    lines.append("")
    lines.append("Press a number to bind (rebinding replaces your familiar).")
    return lines


def _effect_text(species_id) -> str:
    sp = species().get(species_id, {})
    eff = sp.get("effect", {}) or {}
    bits = []
    if eff.get("mana_regen"):
        bits.append(f"+{eff['mana_regen']} mana regen")
    if eff.get("mana_max"):
        bits.append(f"+{eff['mana_max']} max mana")
    if eff.get("sight"):
        bits.append(f"+{eff['sight']} sight")
    return ", ".join(bits) or "a quiet companion"


def bind_index(engine, idx: int) -> str:
    opts = available(engine.player)
    if 0 <= idx < len(opts):
        return bind(engine, opts[idx][0])
    return ""
