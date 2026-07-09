"""Heart events — affinity-threshold scenes (P3.5, the Stardew pattern).

Crossing a relationship threshold with a named NPC triggers a one-off
scene: the skeleton is hand-authored in `data/heart_events.json`
(authored truth), and when an LLM provider is active the outline is
re-rendered as fresh prose in the NPC's voice (generated flesh). Each
scene grants a small perk — an item, gold — and is remembered by the NPC.

Triggered ids live in `player.metadata["heart_events"]`.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.heart_events")


def _load() -> Dict[str, list]:
    from items.data_loader import load_data_file
    return load_data_file("heart_events.json")


HEART_EVENTS: Dict[str, list] = _load()


class HeartEventManager:
    def __init__(self, engine):
        self.engine = engine

    def seen(self) -> List[str]:
        return self.engine.player.metadata.setdefault("heart_events", [])

    def pending_event(self, npc) -> Optional[dict]:
        """Lowest-threshold uncrossed event this NPC is ready to fire."""
        rel = npc.get_relationship(self.engine.player.id)
        candidates = [e for e in HEART_EVENTS.get(npc.id, [])
                      if e["id"] not in self.seen()
                      and rel >= e["threshold"]]
        if not candidates:
            return None
        return min(candidates, key=lambda e: e["threshold"])

    def maybe_trigger(self, npc) -> Optional[str]:
        """Fire at most one scene; returns the scene text or None."""
        event = self.pending_event(npc)
        if event is None:
            return None
        self.seen().append(event["id"])

        prose = self._render(npc, event["outline"])
        mm = self.engine.memory_manager
        mm.add_event(f"— A moment with {npc.name} —")
        mm.add_event(prose)

        perk_note = self._grant_perk(event.get("perk", {}))
        if perk_note:
            mm.add_event(perk_note)

        from engine.npc_memory import remember
        remember(npc, f"I shared a meaningful moment with "
                      f"{self.engine.player.name}.", 7,
                 self.engine.world.time)
        return prose

    # ---- rendering -----------------------------------------------------

    def _render(self, npc, outline: str) -> str:
        iface = getattr(self.engine, "llm_interface", None)
        if iface is None or getattr(iface, "provider_name",
                                    "heuristic") == "heuristic":
            return outline
        try:
            raw = iface.generate_response(
                f"Rewrite this scene beat as 3-4 sentences of warm, "
                f"present-tense prose from the player's point of view. "
                f"Keep every stated fact; invent nothing new.\n\n"
                f"NPC: {npc.name} ({npc.description})\n"
                f"SCENE: {outline}",
                "You render authored RPG scene outlines as short prose. "
                "Reply with the prose only.",
                max_tokens=220, temperature=0.8)
            text = (raw or "").strip()
            return text if len(text) > 40 else outline
        except Exception as e:
            logger.debug(f"Heart-event render failed: {e}")
            return outline

    # ---- perks -----------------------------------------------------------

    def _grant_perk(self, perk: dict) -> Optional[str]:
        player = self.engine.player
        note = perk.get("note", "")
        if "item" in perk:
            from items.item_registry import create_item
            item = create_item(perk["item"])
            if item:
                player.inventory.append(item)
                return note or f"You receive {item.name}."
        if "gold" in perk:
            player.gold += int(perk["gold"])
            return note or f"You receive {perk['gold']}g."
        return note or None
