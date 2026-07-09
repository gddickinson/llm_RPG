"""LLM call discipline (P3.9).

The budget rules, enforced at the call sites:
- Player conversation, persuasion verdicts, heart-event renders: on
  demand (player-initiated, naturally rare).
- Nightly reflection + world director: once per game-day.
- NPC ambient actions: spawned monsters NEVER get LLM minds (heuristic
  hostility is enough); named NPCs get at most one LLM-driven action per
  ACTION_COOLDOWN_MIN of game time — everything between runs on the free
  heuristic provider.
- Plain greetings (T with no message) are cached per NPC for
  GREETING_TTL_MIN game minutes.
"""

import logging

logger = logging.getLogger("llm_rpg.llm_budget")

ACTION_COOLDOWN_MIN = 30
GREETING_TTL_MIN = 60


def heuristic_provider(engine):
    """Lazily-created shared heuristic provider for fallback decisions."""
    prov = getattr(engine, "_heuristic_fallback", None)
    if prov is None:
        from llm.providers.heuristic import HeuristicProvider
        prov = HeuristicProvider()
        engine._heuristic_fallback = prov
    return prov


def llm_action_allowed(engine, npc) -> bool:
    """May this NPC spend an LLM call on its ambient action right now?
    (Also stamps the cooldown when granting.)"""
    iface = getattr(engine, "llm_interface", None)
    if iface is None or getattr(iface, "provider_name",
                                "heuristic") == "heuristic":
        return True   # the heuristic provider is free — no throttle
    if npc.id.startswith("enc_"):
        return False  # spawned monsters don't need an LLM mind
    last = npc.metadata.get("last_llm_action", -10**9)
    if engine.world.time - last < ACTION_COOLDOWN_MIN:
        return False
    npc.metadata["last_llm_action"] = engine.world.time
    return True


def cached_greeting(engine, npc):
    """Return a still-fresh cached greeting, or None."""
    cache = npc.metadata.get("greet_cache")
    if not cache:
        return None
    if engine.world.time - cache.get("at", -10**9) > GREETING_TTL_MIN:
        return None
    return cache.get("text")


def store_greeting(engine, npc, text: str) -> None:
    npc.metadata["greet_cache"] = {"text": text,
                                   "at": engine.world.time}
