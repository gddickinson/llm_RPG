"""While-you-were-away digest (M.9a) — when the human takes the reins back
from the autoplay agent, surface what the hero got up to in their absence
as a readable screen, instead of leaving the `[Away]` deed beats buried in
the scrolling event log.

`set_away(True)` (in player_roster) stamps a snapshot on
`player.metadata["away_snapshot"]`; `build_digest` reads it back, gathers
the `[Away]` deeds logged since, tallies what CHANGED (days, level, purse,
party), and returns a `(title, lines)` overlay — or None if nothing
happened. It CONSUMES the snapshot, so the summary shows once.
"""

from typing import List, Optional, Tuple


def snapshot(engine, character) -> None:
    """Stamp the away-start state so a later digest can show the deltas."""
    try:
        character.metadata["away_snapshot"] = {
            "mem_len": len(engine.memory_manager.game_history),
            "day": engine.world.time // (24 * 60),
            "level": getattr(character, "level", 1),
            "gold": getattr(character, "gold", 0),
            "party": list(getattr(engine.companion_manager, "party", []) or []),
        }
    except Exception:
        pass


def _away_deeds(engine, start: int) -> List[str]:
    out = []
    for e in engine.memory_manager.game_history[start:]:
        text = e.get("event", "") if isinstance(e, dict) else str(e)
        if "[Away]" in text:
            out.append(text.split("]", 1)[1].strip() if "]" in text else text)
    return out


def build_digest(engine, character) -> Optional[Tuple[str, List[str]]]:
    """A `(title, lines)` 'While You Were Away' summary, or None if the hero
    did nothing worth reporting. Consumes the snapshot."""
    meta = getattr(character, "metadata", {}) or {}
    snap = meta.pop("away_snapshot", None)
    if snap is None:            # no away period to report — one-shot
        return None
    deeds = _away_deeds(engine, snap.get("mem_len", 0))

    lines: List[str] = []
    try:
        days = engine.world.time // (24 * 60) - snap.get("day", 0)
        if days > 0:
            lines.append(f"You were away about {days} day(s).")
        dl = getattr(character, "level", 1) - snap.get("level", 1)
        if dl > 0:
            lines.append(f"{character.name} grew {dl} level(s) stronger "
                         f"— now level {character.level}.")
        dg = getattr(character, "gold", 0) - snap.get("gold", 0)
        if dg:
            lines.append(f"Purse: {'+' if dg > 0 else ''}{dg} gold.")
        before = set(snap.get("party", []))
        now = set(getattr(engine.companion_manager, "party", []) or [])
        gained = [engine.npc_manager.npcs[n].name for n in (now - before)
                  if n in engine.npc_manager.npcs]
        if gained:
            lines.append("Took up with: " + ", ".join(gained) + ".")
    except Exception:
        pass

    if deeds:
        if lines:
            lines.append("")
        lines.append("Deeds along the way:")
        # newest last; cap so the screen never overflows
        lines.extend(f"  • {d}" for d in deeds[-18:])

    if not lines:
        return None
    return ("While You Were Away", lines)
