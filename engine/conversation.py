"""Conversation menu (PUX.6) — the key things a talk with an NPC can
reveal, as numbered quick-pick options.

Talking to someone used to be a blank text box with hidden 1–9 quest
hotkeys you had to guess at. This builds the visible menu instead: the
quests they can give or take in, whether they'll trade, the topics you
can ask them about, and any secret they might let slip. Pure data —
the GUI lists these and dispatches them; every engine call they make
(`quests_offered_by`, `quests_to_turn_in_with`, the shop, the topic
journal, `secrets`) already exists.
"""

from typing import List

from engine import secrets as _secrets

# classes that keep a shop the player can barter at
MERCHANT_CLASSES = ("merchant", "cleric", "wizard", "ranger")
_TOPIC_CAP = 3          # keep the menu short


def _class_of(npc) -> str:
    return getattr(getattr(npc, "character_class", None), "value", "")


def is_merchant(npc) -> bool:
    return _class_of(npc) in MERCHANT_CLASSES


def askable_topics(engine, npc) -> List[str]:
    """Topics the player has heard of that THIS NPC can speak to."""
    try:
        known = engine.topic_journal.known()
    except Exception:
        return []
    out = []
    for tid in known:
        try:
            if engine.topic_journal.npc_response(npc, tid):
                out.append(tid)
        except Exception:
            pass
        if len(out) >= _TOPIC_CAP:
            break
    return out


def _topic_name(tid: str) -> str:
    from engine.topics import TOPICS
    return TOPICS.get(tid, {}).get("name", tid)


def menu(engine, npc) -> List[dict]:
    """The numbered quick-pick options for talking to `npc`, in the
    order they're offered (turn-ins first — the player came to hand
    something in — then new quests, trade, topics, secrets)."""
    items: List[dict] = []
    for q in engine.quests_to_turn_in_with(npc.id):
        items.append({"kind": "turnin", "label": f"Turn in: {q.title}",
                      "quest_id": q.id})
    for q in engine.quests_offered_by(npc.id):
        items.append({"kind": "accept", "label": f"Accept: {q.title}",
                      "quest_id": q.id})
    if is_merchant(npc):
        items.append({"kind": "trade", "label": "Trade / barter"})
    for tid in askable_topics(engine, npc):
        items.append({"kind": "topic",
                      "label": f"Ask about {_topic_name(tid)}",
                      "topic": tid})
    if _secrets.unlocked_secrets(engine, npc):
        items.append({"kind": "secret",
                      "label": "Press them — what aren't they saying?"})
    # PUX.6 / I2 a warm gesture — greet / embrace / kiss by your standing
    from engine import interactions
    social = interactions.player_social_option(engine, npc)
    if social:
        items.append({"kind": "social", "label": social[1],
                      "social": social[0]})
    return items
