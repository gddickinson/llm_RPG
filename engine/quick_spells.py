"""P22.6 — non-blocking quick-cast.

Cast a favourited spell straight from PLAY mode (number keys 1-5) at the current
target, WITHOUT the blocking spellbook overlay that hides the battlefield mid-
fight. Quick-slots live on `player.metadata["quick_spells"]`; they auto-populate
from the caster's known spells (offensive first, then heal, then buff) so a mage
can cast from the field with zero setup, and can be re-bound from the spellbook
(SHIFT+N). Targeting reuses the spell system's own resolver — the P8.7 lock or
the nearest hostile for a damage spell, self for a heal/buff.
"""

MAX_SLOTS = 5


def get_slots(player):
    meta = getattr(player, "metadata", None) or {}
    return list(meta.get("quick_spells", []))[:MAX_SLOTS]


def slot_spell(player, idx):
    slots = get_slots(player)
    return slots[idx] if 0 <= idx < len(slots) else None


def set_slot(player, idx, spell_id):
    """Bind `spell_id` to quick-slot `idx` (0-based)."""
    if not (0 <= idx < MAX_SLOTS):
        return
    meta = getattr(player, "metadata", None)
    if not isinstance(meta, dict):
        return
    slots = get_slots(player)
    while len(slots) <= idx:
        slots.append(None)
    slots[idx] = spell_id
    meta["quick_spells"] = slots


def _rank(sid):
    from engine.spells import SPELL_REGISTRY
    s = SPELL_REGISTRY.get(sid)
    if s is None:
        return 4
    if s.damage:
        return 0
    if s.heal:
        return 1
    return 2


def ensure_defaults(player):
    """Fill the quick slots from known spells when empty (offensive → heal →
    buff), so a caster can quick-cast immediately."""
    meta = getattr(player, "metadata", None)
    if not isinstance(meta, dict) or meta.get("quick_spells"):
        return
    known = list(meta.get("spells_known", []))
    if known:
        meta["quick_spells"] = sorted(known, key=_rank)[:MAX_SLOTS]


def quick_cast(engine, idx) -> str:
    """Cast the spell in quick-slot `idx` (0-based) at the current target —
    non-blocking; returns the cast message. The spell system checks mana / known
    / range and picks the target (lock or nearest hostile, self for a heal)."""
    player = engine.player
    ensure_defaults(player)
    sid = slot_spell(player, idx)
    if not sid:
        return f"[Cast] Quick-slot {idx + 1} is empty."
    from engine.spells import SPELL_REGISTRY
    spell = SPELL_REGISTRY.get(sid)
    if spell is None:
        return f"[Cast] Unknown spell in slot {idx + 1}."
    target = "me" if (spell.heal and not spell.damage) else None
    try:
        msg = engine.cast_spell(sid, target)
    except Exception as e:
        return f"[Cast] {spell.name} fizzles ({e})."
    try:
        engine.memory_manager.add_event(msg)
    except Exception:
        pass
    return msg
