"""T2.1 — NPCs INGEST world events.

The rich nightly simulation ([Realm] wars/ambitions/shortages/raids, [Legend]
deaths, [Town]/[Overnight]/[Board] beats) used to reach only the event LOG — the
villager standing beside you had no idea any of it happened. This memory-manager
observer feeds each significant world beat into a few RELEVANT NPCs' own memories
(those nearest you, plus a couple elsewhere), so they KNOW it — and can mention it
in dialog (the prompt reads their memories), gossip about it, and reflect on it
overnight. Cheap: fires only on the tagged beats, seeds a capped handful of NPCs.
"""

import random

# the beat prefixes worth spreading (the consequential world/social news)
_SPREAD = ("[Realm]", "[Legend]", "[Overnight]", "[Town]", "[Board]")
_NEAR = 4                 # NPCs nearest the player who 'hear' a beat
_FAR = 2                  # a couple elsewhere, so news travels
_MAX_BEATS = 8            # cap the per-NPC world-beat memory so it can't flood


def make_observer(engine):
    """Return an observer(event_text) that seeds world beats into NPC memory."""
    def _observe(text):
        try:
            if not text or not text.startswith(_SPREAD):
                return
            npcs = [n for n in engine.npc_manager.npcs.values()
                    if n.is_active()]
            if not npcs:
                return
            px, py = engine.player.position
            near = sorted(
                npcs,
                key=lambda n: abs(n.position[0] - px) + abs(n.position[1] - py)
            )[:_NEAR]
            heard = list(near)
            pool = [n for n in npcs if n not in near]
            if pool:
                heard += random.sample(pool, min(_FAR, len(pool)))
            for n in heard:
                _remember(n, text)
        except Exception:
            pass
    return _observe


def _remember(npc, text):
    try:
        npc.add_memory(text, importance=3)
        beats = npc.metadata.setdefault("_world_beats", [])
        if text not in beats:
            beats.append(text)
            if len(beats) > _MAX_BEATS:
                del beats[0]
    except Exception:
        pass


def recent_world_beat(npc, rng=None):
    """A world beat this NPC has heard (for heuristic gossip / a talking point),
    or None. The stored text keeps its [Prefix] — strip it for a spoken line."""
    beats = (getattr(npc, "metadata", None) or {}).get("_world_beats") or []
    if not beats:
        return None
    return (rng or random).choice(beats)
