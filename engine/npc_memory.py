"""Per-NPC memory: retrieval + reflection (P3.2, Generative Agents lite).

Replaces the old "substring-scan the global event log" approach:

- `remember(npc, event, importance, world_time)` appends a memory carrying
  GAME time (the old add_memory stamped wall-clock time and re-sorted).
- `retrieve(npc, query, world_time)` scores every memory by
  recency x importance x relevance (word overlap — no embeddings needed
  for a local game) and returns the top K.
- `log_exchange(npc, player_line, npc_line)` keeps the last 10 dialog
  exchanges verbatim in `npc.metadata["dialog_log"]`.
- `nightly_reflection(engine)` runs once per game-day: each named NPC
  with fresh memories distills 1-2 durable "opinions"
  (`npc.metadata["opinions"]`, capped) — via one LLM call per NPC when a
  provider is active, or a cheap template in heuristic mode.

All state rides Character.memories / Character.metadata → saves free.
"""

import logging
import re
from typing import List

logger = logging.getLogger("llm_rpg.npc_memory")

MAX_DIALOG_LOG = 10
MAX_OPINIONS = 3
RECENCY_HALFLIFE_MIN = 24 * 60      # one game day
MINUTES_PER_DAY = 24 * 60

_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "is",
              "was", "i", "you", "my", "me", "it", "for", "on", "at",
              "with", "that", "this", "said", "says"}


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z']+", text.lower())
            if w not in _STOPWORDS and len(w) > 2}


# ---- write ----------------------------------------------------------------

def remember(npc, event: str, importance: int, world_time: int) -> None:
    npc.memories.append({
        "event": event,
        "importance": max(1, min(10, importance)),
        "game_time": world_time,
    })


def log_exchange(npc, player_line: str, npc_line: str) -> None:
    meta = npc.metadata
    log = meta.setdefault("dialog_log", [])
    log.append({"player": player_line, "npc": npc_line})
    del log[:-MAX_DIALOG_LOG]


# ---- retrieve ---------------------------------------------------------------

def retrieve(npc, query: str, world_time: int, k: int = 5) -> List[str]:
    """Top-k memory events by recency x importance x relevance."""
    query_words = _words(query)
    scored = []
    for mem in npc.memories:
        event = mem.get("event", "")
        importance = mem.get("importance", 1) / 10.0
        gt = mem.get("game_time")
        if gt is not None:
            age = max(0, world_time - gt)
            recency = 0.5 ** (age / RECENCY_HALFLIFE_MIN)
        else:
            recency = 0.3     # legacy wall-clock memories: mildly stale
        mem_words = _words(event)
        overlap = len(query_words & mem_words)
        relevance = overlap / (len(query_words) + 1)
        score = recency * 0.4 + importance * 0.3 + relevance * 1.2
        scored.append((score, event))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [event for _, event in scored[:k]]


def opinions(npc) -> List[str]:
    return list(npc.metadata.get("opinions", []))


def recent_exchanges(npc, k: int = 4) -> List[str]:
    out = []
    for entry in npc.metadata.get("dialog_log", [])[-k:]:
        out.append(f"They said: \"{entry['player']}\" — "
                   f"you replied: \"{entry['npc']}\"")
    return out


# ---- reflect ----------------------------------------------------------------

def nightly_reflection(engine) -> int:
    """Distill fresh memories into opinions. Returns NPCs reflected."""
    count = 0
    use_llm = getattr(engine.llm_interface, "provider_name",
                      "heuristic") != "heuristic"
    for npc in engine.npc_manager.npcs.values():
        if not npc.is_active():
            continue
        meta = npc.metadata
        seen = meta.get("reflected_upto", 0)
        fresh = npc.memories[seen:]
        if len(fresh) < 3:
            continue
        opinion = None
        if use_llm:
            opinion = _llm_opinion(engine, npc, fresh)
        if not opinion:
            # Heuristic: the most important fresh memory becomes a theme
            top = max(fresh, key=lambda m: m.get("importance", 1))
            opinion = f"Lately I keep thinking about this: {top['event']}"
        ops = meta.setdefault("opinions", [])
        ops.append(opinion)
        del ops[:-MAX_OPINIONS]
        meta["reflected_upto"] = len(npc.memories)
        count += 1
    if count:
        logger.info(f"Nightly reflection: {count} NPCs")
    return count


def _llm_opinion(engine, npc, fresh) -> str:
    try:
        events = "\n".join(f"- {m['event']}" for m in fresh[-8:])
        raw = engine.llm_interface.generate_response(
            f"You are {npc.name}. Recent experiences:\n{events}\n\n"
            f"In ONE first-person sentence, state the most important "
            f"opinion or conclusion you now hold.",
            "Reply with exactly one sentence, no preamble.",
            max_tokens=60, temperature=0.7)
        line = (raw or "").strip().split("\n")[0].strip()
        return line[:200] if line else ""
    except Exception as e:
        logger.debug(f"LLM reflection failed for {npc.name}: {e}")
        return ""
