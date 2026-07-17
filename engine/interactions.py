"""Character-to-character INTERACTIONS (George: "ways for characters to better
interact — hugging, handshakes, kisses, wrestling, throws").

I1 — AMBIENT social interactions: two adjacent, idle, non-hostile neighbours play a
relationship-appropriate coordinated interaction (handshake / hug / kiss / square-up)
through `engine.anim.interact`, so the social graph — friendships, couples, feuds —
becomes VISIBLE in the world. Cosmetic + a tiny regard nudge; heuristic-only, cheap
(nearby pairs, a low per-turn chance, a per-character cooldown).

The combat grapples/throws (I3) build on the same `anim.interact` primitive.
"""

import random as _random

from engine import anim

# relationship thresholds (mirror engine/social_graph FRIEND / FEUD)
_FRIEND = 55
_FEUD = -45
_COOLDOWN = 24          # a character shares a social beat at most this often (turns)

# social kind -> (anim.interact clip, mutual regard nudge, [Town] beat verb)
_SOCIAL = {
    "kiss":      ("kiss", 2, "share a tender kiss"),
    "hug":       ("hug", 2, "embrace warmly"),
    "handshake": ("handshake", 1, "clasp hands in greeting"),
    "squareup":  ("taunt", -1, "square up, bristling at each other"),
}


def _regard(a, b):
    """The coldest and warmest of the two directed regards, as (lo, hi) — a warm
    pair HUGS on the warmest reading, a soured pair SQUARES UP on the coldest (one
    party bristling is enough)."""
    try:
        x, y = a.get_relationship(b.id), b.get_relationship(a.id)
        return (min(x, y), max(x, y))
    except Exception:
        return (0, 0)


def _partnered(a, b):
    """A romance couple (the mutual `partner` link set by ambitions/romance)."""
    return ((a.metadata or {}).get("partner") == b.id
            or (b.metadata or {}).get("partner") == a.id)


def social_kind(a, b):
    """The interaction two neighbours would share by their standing, or None.
    A couple KISSES, warm friends HUG, friendly acquaintances SHAKE hands, a
    feuding pair SQUARES UP; strangers do nothing."""
    if _partnered(a, b):
        return "kiss"
    sa = (a.metadata or {}).get("social") or {}
    sb = (b.metadata or {}).get("social") or {}
    if sa.get(f"feud:{b.id}") or sb.get(f"feud:{a.id}"):
        return "squareup"
    lo, hi = _regard(a, b)
    if lo <= _FEUD:
        return "squareup"
    if hi >= _FRIEND or sa.get(f"friend:{b.id}") or sb.get(f"friend:{a.id}"):
        return "hug"
    if hi >= 12:
        return "handshake"
    return None


def _busy(char):
    """Mid-stride or already playing an emote/stance — leave it be."""
    m = char.metadata or {}
    return bool(m.get("_emote") or m.get("_stance")
                or (m.get("_anim") or {}).get("moving"))


def _turn(engine):
    try:
        return int(engine.turn_counter)
    except Exception:
        return 0


def perform_social(engine, a, b, kind=None):
    """Play a coordinated social interaction between a and b + its small effect.
    Returns the kind played, or None. Reusable by the player-initiated path (I2)."""
    kind = kind or social_kind(a, b)
    if kind is None:
        return None
    clip, regard, verb = _SOCIAL[kind]
    anim.interact(a, b, clip)
    try:
        a.modify_relationship(b.id, regard)
        b.modify_relationship(a.id, regard)
    except Exception:
        pass
    turn = _turn(engine)
    for c in (a, b):
        try:
            c.metadata["_social_turn"] = turn
        except Exception:
            pass
    _beat(engine, a, b, verb)
    return kind


def _beat(engine, a, b, verb):
    """A sparse [Town] event when the pair is near the player, so the whole town's
    social life doesn't spam the log at once."""
    try:
        px, py = engine.player.position
        ax, ay = a.position
        if abs(px - ax) + abs(py - ay) <= 7 and _random.random() < 0.5:
            engine.memory_manager.add_event(
                f"[Town] {a.name} and {b.name} {verb}.")
    except Exception:
        pass


def update_social(engine, rng=None, chance=0.02):
    """Per-turn ambient pass: an idle non-hostile NPC beside an idle non-hostile
    neighbour it has a standing with occasionally shares a social interaction.
    Cheap over the small active cast; deduped so a pair fires once/turn and no more
    than every `_COOLDOWN` turns. The player isn't an ambient initiator (I2 covers
    player-driven interactions)."""
    rng = rng or _random
    try:
        from engine.agent_sense import _is_hostile
        cast = [n for n in engine.npc_manager.npcs.values()
                if n.is_active() and not _is_hostile(n)]
    except Exception:
        return
    turn = _turn(engine)
    done = set()
    for a in cast:
        if a.id in done or _busy(a):
            continue
        if turn - (a.metadata or {}).get("_social_turn", -9999) < _COOLDOWN:
            continue
        if rng.random() > chance:
            continue
        ax, ay = a.position
        for b in cast:
            if b is a or b.id in done or _busy(b):
                continue
            if abs(b.position[0] - ax) > 1 or abs(b.position[1] - ay) > 1:
                continue
            if turn - (b.metadata or {}).get("_social_turn", -9999) < _COOLDOWN:
                continue
            kind = social_kind(a, b)
            if kind:
                perform_social(engine, a, b, kind)
                done.add(a.id)
                done.add(b.id)
                break
