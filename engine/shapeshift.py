"""Shapeshifting (George): any character — player, NPC, or monster — can
take the shape of another creature, WILLINGLY (a druid's wild shape, a
totem, a polymorph spell) or AGAINST THEIR WILL (a baleful polymorph, a
witch's curse, a cursed item that leaves you a frog until the curse is
lifted).

A form (`data/forms.json`) OVERRIDES how a character renders (the existing
`creature_pose.body_plan`/`model` path — a shifted human draws as the
beast for free), fights (`natural_damage`, no hands to wield), and endures
(`hp_mult` scales the pool by fraction), and what it can DO (fly, or the
no_cast / no_wield / no_speak restrictions). State on
`character.metadata["shapeshift"]` (the original overridden fields stashed
for the return), so it rides the save. A VOLUNTARY shape reverts at will
or when its duration runs out; an INVOLUNTARY one holds until a Remove
Curse, a shrine's blessing, or the curse's own clock frees you.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.shapeshift")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "forms.json")
_FORMS = None


def forms() -> dict:
    global _FORMS
    if _FORMS is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _FORMS = json.load(fh).get("forms", {})
        except Exception as e:                       # pragma: no cover
            logger.info(f"Form data unavailable: {e}")
            _FORMS = {}
    return _FORMS


# ---- queries -----------------------------------------------------------

def _ss(character):
    return (getattr(character, "metadata", None) or {}).get("shapeshift")


def is_shifted(character) -> bool:
    return _ss(character) is not None


def current_form(character):
    s = _ss(character)
    return s.get("form") if s else None


def _involuntary(character) -> bool:
    s = _ss(character)
    return bool(s and s.get("involuntary"))


def is_involuntary(character) -> bool:
    return _involuntary(character)


def restricted(character, key) -> bool:
    s = _ss(character)
    return bool(s and key in s.get("restrict", []))


def form_flag(character, flag) -> bool:
    s = _ss(character)
    return bool(s and flag in s.get("flags", []))


def form_natural_damage(character) -> int:
    s = _ss(character)
    if not s:
        return 0
    fm = forms().get(s.get("form"), {})
    return int(fm.get("natural_damage", 1))


def form_speed(character) -> float:
    s = _ss(character)
    if not s:
        return 1.0
    return float(forms().get(s.get("form"), {}).get("speed", 1.0))


# ---- shift / revert ----------------------------------------------------

def shift(engine, character, form_id, *, duration=None, involuntary=False,
          source="") -> str:
    fm = forms().get(form_id)
    if fm is None:
        return "There is no such shape to take."
    if is_shifted(character):                    # stash the TRUE original
        revert(engine, character, force=True, quiet=True)
    meta = character.metadata
    orig = {
        "body_plan": meta.get("body_plan"),
        "model": meta.get("model"),
        "natural_damage": meta.get("natural_damage"),
        "flying": (meta.get("behavior", {}) or {}).get("flying"),
        "max_hp": int(getattr(character, "max_hp", 1)),
    }
    frac = character.hp / max(1, character.max_hp)
    character.max_hp = max(1, round(orig["max_hp"] * fm.get("hp_mult", 1.0)))
    character.hp = max(1, round(character.max_hp * frac))
    meta["body_plan"] = fm.get("body_plan", "quadruped")
    if fm.get("model"):
        meta["model"] = fm["model"]
    else:
        meta.pop("model", None)                  # a modelless form → procedural
    meta["natural_damage"] = int(fm.get("natural_damage", 1))
    if "flying" in fm.get("flags", []):
        meta.setdefault("behavior", {})["flying"] = True
    meta["shapeshift"] = {
        "form": form_id, "orig": orig, "involuntary": bool(involuntary),
        "source": source, "restrict": list(fm.get("restrict", [])),
        "flags": list(fm.get("flags", [])), "kind": fm.get("kind", "beast"),
        "turns_left": int(duration) if duration else 0,   # 0 = until dispelled
    }
    _announce(engine, f"[Shift] {character.name} "
              + ("is twisted into the shape of " if involuntary
                 else "takes the shape of ")
              + f"{fm['name']}"
              + (" — a curse to be broken!" if involuntary else "."))
    return f"{character.name} becomes {fm['name']}."


def revert(engine, character, *, force=False, quiet=False) -> str:
    s = _ss(character)
    if not s:
        return "There is no shape to shed."
    if s.get("involuntary") and not force:
        return ("You strain against the change, but the shape holds fast — "
                "this was forced upon you. Seek to break the curse.")
    orig = s.get("orig", {})
    frac = character.hp / max(1, character.max_hp)
    character.max_hp = max(1, int(orig.get("max_hp", character.max_hp)))
    character.hp = max(1, round(character.max_hp * frac))
    meta = character.metadata
    _restore(meta, "body_plan", orig.get("body_plan"))
    _restore(meta, "model", orig.get("model"))
    _restore(meta, "natural_damage", orig.get("natural_damage"))
    beh = meta.get("behavior")
    if isinstance(beh, dict):
        if orig.get("flying"):
            beh["flying"] = True
        else:
            beh.pop("flying", None)
    meta.pop("shapeshift", None)
    if not quiet:
        _announce(engine, f"[Shift] {character.name} returns to their "
                  f"true shape.")
    return f"{character.name} returns to their true shape."


def remove_curse(engine, character) -> str:
    """Break an INVOLUNTARY shape (a Remove Curse spell, a shrine, a cure
    item). A voluntary shape is simply released."""
    if not is_shifted(character):
        return f"{character.name} bears no shape-curse to lift."
    return revert(engine, character, force=True)


def tick(engine) -> None:
    """Run down timed shapes; auto-revert when the clock runs out."""
    try:
        chars = [engine.player] + list(engine.npc_manager.npcs.values())
    except Exception:
        return
    for ch in chars:
        s = _ss(ch)
        if not s:
            continue
        left = int(s.get("turns_left", 0))
        if left <= 0:
            continue
        left -= 1
        s["turns_left"] = left
        if left <= 0:
            revert(engine, ch, force=True)


def _restore(meta, key, val):
    if val is None:
        meta.pop(key, None)
    else:
        meta[key] = val


def _announce(engine, text):
    try:
        engine.memory_manager.add_event(text)
    except Exception:
        pass


# ---- the spell hook ----------------------------------------------------

def cast_shapeshift(engine, caster, spell, target) -> str:
    """Apply a spell's `shapeshift` block: cure / self wild-shape (toggle) /
    a forced polymorph on a target."""
    ss = spell.shapeshift or {}
    if ss.get("cure"):
        return remove_curse(engine, target or caster)
    who = caster if ss.get("self") else (target or caster)
    if who is caster and is_shifted(caster) and not _involuntary(caster):
        return revert(engine, caster)            # toggle wild shape off
    return shift(engine, who, ss.get("form", "wolf"),
                 duration=ss.get("duration"),
                 involuntary=bool(ss.get("involuntary")),
                 source=getattr(spell, "name", ""))
