"""P34.2 facial expression, blink & emote bubbles (pure, headless-testable).

At a ~7–14px head, SHAPE beats detail: a couple of pixels of brow angle and mouth
curvature carry the whole emotion. An expression is three parameters — brow tilt,
mouth curve, eye mode — and `body_parts.draw_face` renders them. Blinking is a
small per-character state machine over the anim dict. Emotes/mood set the current
expression; a floating symbol BUBBLE (alert/question/sleep/love/anger/note) backs
it up for legibility (Animal Crossing / Undertale style).
"""

# name -> {brow: inner-brow dy (+ = angry/lowered, − = sad/raised),
#          mouth: curve (>0 smile, <0 frown), eyes: mode}
EXPRESSIONS = {
    "neutral":   {"brow": 0, "mouth": 0.0, "eyes": "dot"},
    "happy":     {"brow": -1, "mouth": 0.7, "eyes": "dot"},
    "laughing":  {"brow": -1, "mouth": 1.0, "eyes": "arch"},
    "angry":     {"brow": 2, "mouth": -0.5, "eyes": "squint"},
    "sad":       {"brow": -2, "mouth": -0.6, "eyes": "dot"},
    "scared":    {"brow": 1, "mouth": -0.3, "eyes": "wide"},
    "surprised": {"brow": -1, "mouth": 0.1, "eyes": "wide"},
    "hurt":      {"brow": 1, "mouth": -0.4, "eyes": "x"},
}
DEFAULT_EXPR = "neutral"

# an emote/clip implies a fleeting expression
EMOTE_EXPR = {
    "hurt": "hurt", "cheer": "happy", "dance": "happy", "wave": "happy",
    "kiss": "happy", "hug": "happy", "handshake": "happy", "knockdown": "hurt",
    "tumble": "scared", "guard": "angry", "cast": "surprised", "bow": "neutral",
    "attack": "angry", "wrestle": "angry", "taunt": "angry", "throw": "angry",
}

BUBBLES = ("alert", "question", "sleep", "love", "angry", "note")


def expr_for(char):
    """The character's current expression name (from `metadata['_expr']`)."""
    e = (getattr(char, "metadata", None) or {}).get("_expr")
    return e if e in EXPRESSIONS else DEFAULT_EXPR


def spec(name):
    return EXPRESSIONS.get(name, EXPRESSIONS[DEFAULT_EXPR])


def blink_step(anim, dt, seed):
    """Advance a per-character blink clock over the anim dict; return True while
    the eyes are shut. Intervals jitter by seed so a crowd doesn't blink in
    lockstep. Pure state on `anim` (blink_t / blinking / blink_n)."""
    t = anim.get("blink_t")
    if t is None:
        anim["blink_t"] = 1.5 + (seed % 30) / 10.0
        anim["blinking"] = False
        return False
    t -= dt
    if t <= 0:
        if anim.get("blinking"):
            n = anim.get("blink_n", 0) + 1
            anim["blink_n"] = n
            anim["blinking"] = False
            anim["blink_t"] = 2.0 + ((seed + n * 37) % 45) / 10.0
        else:
            anim["blinking"] = True
            anim["blink_t"] = 0.11
    else:
        anim["blink_t"] = t
    return anim.get("blinking", False)
