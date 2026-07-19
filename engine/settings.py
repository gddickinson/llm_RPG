"""Player settings (PUX.4a) — a small, persisted options store.

Each option is DATA — a key, a label, the values it cycles through,
and a default. Values live in `player.metadata` (under `settings`, or
at a `meta_key` for options that share an existing store like the
event-log verbosity) so they survive saves. The GUI settings overlay
reads and cycles these; applying the visual side (map zoom, muting
sound) is the panel's job, but the VALUES and their persistence are
pure and unit-tested here.
"""

from typing import List

# order = display order in the overlay
OPTIONS: List[dict] = [
    {"key": "log_detail", "label": "Event log",
     "choices": ["quiet", "normal", "verbose"], "default": "normal",
     "meta_key": "log_verbosity"},     # shares event_filter's store
    {"key": "hints", "label": "Hint bar",
     "choices": ["on", "off"], "default": "on"},
    {"key": "minimap", "label": "Mini-map",
     "choices": ["on", "off"], "default": "on"},
    {"key": "sound", "label": "Sound",
     "choices": ["on", "off"], "default": "on"},
    {"key": "music", "label": "Music",
     "choices": ["on", "off"], "default": "on"},
    {"key": "zoom", "label": "Map zoom",
     "choices": [24, 32, 48, 64, 80], "default": 64},
    {"key": "smooth", "label": "Smooth sprites",   # P34.7 SSAA on/off
     "choices": ["on", "off"], "default": "on"},
    {"key": "renderer", "label": "Renderer",       # P41.7 view: 3D iso or flat
     "choices": ["topdown", "iso"], "default": "topdown"},
    {"key": "autoplay", "label": "Auto-play (away)",
     "choices": ["off", "on"], "default": "off"},
    {"key": "disposition", "label": "Away disposition",
     "choices": ["balanced", "valiant", "cautious", "sociable",
                 "explorer", "greedy"], "default": "balanced"},
    {"key": "ambition", "label": "Away ambition",
     "choices": ["none", "wealth", "delve", "mastery", "fellowship"],
     "default": "none"},
]
_BY_KEY = {o["key"]: o for o in OPTIONS}


def all_options() -> List[dict]:
    return OPTIONS


def option(key: str) -> dict:
    return _BY_KEY[key]


def get_setting(player, key):
    o = _BY_KEY[key]
    mk = o.get("meta_key")
    if mk:
        return player.metadata.get(mk, o["default"])
    return player.metadata.setdefault("settings", {}).get(key,
                                                          o["default"])


def set_setting(player, key, value):
    o = _BY_KEY[key]
    mk = o.get("meta_key")
    if mk:
        player.metadata[mk] = value
    else:
        player.metadata.setdefault("settings", {})[key] = value
    return value


def cycle_setting(player, key, step: int = 1):
    """Advance an option to its next (or previous) value, wrapping."""
    choices = _BY_KEY[key]["choices"]
    cur = get_setting(player, key)
    i = choices.index(cur) if cur in choices else 0
    return set_setting(player, key, choices[(i + step) % len(choices)])


def enabled(player, key) -> bool:
    """True for an on/off option that is on — for HUD gating."""
    return get_setting(player, key) == "on"
