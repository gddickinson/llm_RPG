"""Topic journal — knowledge as a collectible (P3.6, the Moonring pattern).

Hearing a topic's keyword ANYWHERE (NPC dialog, secrets, lore lines,
heart events — everything flows through the event log) unlocks it as an
askable topic EVERYWHERE. Mentioning a known topic to an NPC:

- heuristic mode: appends that NPC's authored response (or the topic's
  default line) to their reply;
- LLM mode: injects the NPC's authored knowledge into the prompt as
  grounding, so the model elaborates facts instead of inventing them.

Known topic ids live in `player.metadata["topics_known"]`. The Y key
opens the journal.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.topics")


def _load() -> Dict[str, dict]:
    from items.data_loader import load_data_file
    return load_data_file("topics.json")


TOPICS: Dict[str, dict] = _load()


class TopicJournal:
    def __init__(self, engine):
        self.engine = engine

    # ---- state -----------------------------------------------------------

    def known(self) -> List[str]:
        return self.engine.player.metadata.setdefault("topics_known", [])

    def _match(self, text: str) -> List[str]:
        low = text.lower()
        hits = []
        for tid, spec in TOPICS.items():
            for kw in spec.get("keywords", []):
                if kw in low:
                    hits.append(tid)
                    break
        return hits

    # ---- learning -----------------------------------------------------------

    def scan(self, text: str) -> List[str]:
        """Learn topics mentioned in any player-visible text."""
        # You can't teach yourself a topic by saying its name —
        # knowledge must be HEARD (Moonring's rule)
        if text.startswith(("You say to", "You try to")):
            return []
        new = []
        for tid in self._match(text):
            if tid not in self.known():
                self.known().append(tid)
                new.append(tid)
        for tid in new:
            # Direct append — going through add_event would recurse
            self.engine.memory_manager.game_history.append({
                "timestamp": 0, "game_time": None,
                "event": f"[Topic] New topic in your journal: "
                         f"{TOPICS[tid]['name']} (press Y)",
            })
        return new

    # ---- asking ---------------------------------------------------------------

    def topics_in_message(self, message: str) -> List[str]:
        """KNOWN topics the player just raised."""
        return [tid for tid in self._match(message)
                if tid in self.known()]

    def npc_response(self, npc, topic_id: str) -> Optional[str]:
        spec = TOPICS.get(topic_id)
        if spec is None:
            return None
        return spec.get("responses", {}).get(
            npc.id, spec.get("default_response"))

    def heuristic_lines(self, npc, message: str) -> List[str]:
        """Authored answers for known topics raised in `message`."""
        out = []
        for tid in self.topics_in_message(message):
            line = self.npc_response(npc, tid)
            if line:
                out.append(line)
        return out

    def prompt_block(self, npc, message: str) -> str:
        """Grounding block for the LLM prompt (known+raised topics only)."""
        lines = []
        for tid in self.topics_in_message(message):
            line = self.npc_response(npc, tid)
            name = TOPICS[tid]["name"]
            if line:
                lines.append(f"- About \"{name}\" you know: {line}")
        if not lines:
            return ""
        return ("TOPICS THE PLAYER RAISED (this is what YOU know — "
                "elaborate in character, invent nothing beyond it):\n"
                + "\n".join(lines))

    # ---- UI --------------------------------------------------------------------

    def overlay_lines(self) -> List[str]:
        known = self.known()
        out = [f"Topics heard: {len(known)}/{len(TOPICS)}",
               "(mention a topic to an NPC to ask about it)", ""]
        for tid in known:
            spec = TOPICS.get(tid)
            if spec:
                out.append(f"* {spec['name']}")
                out.append(f"    {spec['hint']}")
        if not known:
            out.append("(Nothing yet — talk to people, read, listen.)")
        return out
