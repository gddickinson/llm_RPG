"""Legends — history made findable (P4.6, the Caves of Qud pattern).

The pre-game history sim leaves a relic in the world for every event it
generated. Picking a relic up reveals its legend: a "[Legend] ..." entry
in the log (which also teaches journal topics via the event observer)
and a permanent entry in the Legends section of the Y-key journal.

Discovered ids live in `player.metadata["legends_known"]`;
the event list itself lives on `engine.world_history` (persisted).
"""

import logging
from typing import List, Optional

logger = logging.getLogger("llm_rpg.legends")


def known_ids(player) -> List[str]:
    return list(player.metadata.get("legends_known", []))


def _find_event(engine, legend_id: str) -> Optional[dict]:
    for ev in getattr(engine, "world_history", []):
        if ev.get("event_id") == legend_id:
            return ev
    return None


def on_item_picked_up(engine, item) -> Optional[str]:
    """Relic pickup → reveal its legend (once)."""
    legend_id = getattr(item, "metadata", {}).get("legend_id")
    if not legend_id:
        return None
    if legend_id in known_ids(engine.player):
        return None
    event = _find_event(engine, legend_id)
    if event is None:
        return None
    engine.player.metadata.setdefault(
        "legends_known", []).append(legend_id)
    note = f"[Legend] {event['legend']}"
    engine.memory_manager.add_event(note)
    return note


def overlay_lines(engine) -> List[str]:
    """The Legends section of the journal."""
    history = getattr(engine, "world_history", [])
    if not history:
        return []
    known = set(known_ids(engine.player))
    out = ["", f"Legends found: "
               f"{sum(1 for ev in history if ev['event_id'] in known)}"
               f"/{len(history)}",
           "(relics of the past lie where their stories happened)", ""]
    for ev in history:
        if ev["event_id"] in known:
            out.append(f"* Year {ev['year']}: {ev['description']}")
            out.append(f"    {ev['legend']}")
        else:
            out.append(f"* Year {ev['year']}: {ev['description']}")
            out.append("    (its relic is still out there...)")
    return out


def gossip_line(engine, rng) -> Optional[str]:
    """NPCs cite history by name (~low odds, called from gossip)."""
    history = getattr(engine, "world_history", [])
    if not history or rng.random() > 0.25:
        return None
    ev = rng.choice(history)
    return (f"They still tell of the year {ev['year']} — "
            f"{ev['description'].rstrip('.')}. Old folk say its relic "
            f"is still out there.")
