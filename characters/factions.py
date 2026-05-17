"""Faction system — group identity + reputation.

Each Character may have a `faction` attribute. The player has a per-faction
reputation score in `player.metadata['faction_rep']`. Reputation changes
when the player acts (kills, helps, trades) in ways that affect a faction.

Reputation scale: -100 (hated) ... +100 (revered).
"""

from enum import Enum
from typing import Dict


class Faction(Enum):
    VILLAGERS = "villagers"        # Oakvale residents
    GUARDS = "guards"              # Town watch
    MERCHANTS = "merchants"        # Traders / shopkeepers
    BRIGANDS = "brigands"          # Outlaws on the road
    MONSTERS = "monsters"          # Wild beasts / trolls
    TEMPLE = "temple"              # Clergy / pious
    BARDIC = "bardic"              # Performers / wandering folk
    NEUTRAL = "neutral"            # Unaligned wildlife / outsiders


# Default class -> faction mapping (used during NPC creation)
CLASS_TO_FACTION = {
    "villager": Faction.VILLAGERS,
    "guard": Faction.GUARDS,
    "merchant": Faction.MERCHANTS,
    "brigand": Faction.BRIGANDS,
    "troll": Faction.BRIGANDS,
    "monster": Faction.MONSTERS,
    "cleric": Faction.TEMPLE,
    "paladin": Faction.TEMPLE,
    "bard": Faction.BARDIC,
}


# How killing one faction affects rep with another (relationship matrix).
# Key: (defeated_faction, affected_faction) -> rep_delta
KILL_REP_DELTA = {
    # Killing brigands pleases villagers, guards, temple
    (Faction.BRIGANDS, Faction.VILLAGERS): +5,
    (Faction.BRIGANDS, Faction.GUARDS): +8,
    (Faction.BRIGANDS, Faction.TEMPLE): +3,
    (Faction.BRIGANDS, Faction.BRIGANDS): -10,
    # Killing monsters pleases everyone moderately
    (Faction.MONSTERS, Faction.VILLAGERS): +3,
    (Faction.MONSTERS, Faction.GUARDS): +3,
    (Faction.MONSTERS, Faction.MERCHANTS): +2,
    (Faction.MONSTERS, Faction.TEMPLE): +2,
    # Killing villagers/merchants/guards is bad with everyone good
    (Faction.VILLAGERS, Faction.VILLAGERS): -25,
    (Faction.VILLAGERS, Faction.GUARDS): -20,
    (Faction.VILLAGERS, Faction.MERCHANTS): -10,
    (Faction.VILLAGERS, Faction.BRIGANDS): +5,
    (Faction.MERCHANTS, Faction.MERCHANTS): -25,
    (Faction.MERCHANTS, Faction.VILLAGERS): -10,
    (Faction.MERCHANTS, Faction.GUARDS): -15,
    (Faction.GUARDS, Faction.GUARDS): -30,
    (Faction.GUARDS, Faction.VILLAGERS): -15,
    (Faction.GUARDS, Faction.BRIGANDS): +10,
    (Faction.TEMPLE, Faction.TEMPLE): -25,
    (Faction.TEMPLE, Faction.VILLAGERS): -10,
}


REP_LABELS = (
    (80, "revered"),
    (50, "honored"),
    (20, "friendly"),
    (5, "warming"),
    (-15, "neutral"),
    (-50, "wary"),
    (-80, "hostile"),
    (-101, "hated"),
)


def rep_label(score: int) -> str:
    for threshold, label in REP_LABELS:
        if score >= threshold:
            return label
    return "hated"


def get_rep(player, faction: Faction) -> int:
    meta = getattr(player, "metadata", None) or {}
    if not isinstance(meta, dict):
        return 0
    return meta.get("faction_rep", {}).get(faction.value, 0)


def set_rep(player, faction: Faction, value: int) -> None:
    meta = getattr(player, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        player.metadata = meta
    rep = meta.setdefault("faction_rep", {})
    rep[faction.value] = max(-100, min(100, int(value)))


def modify_rep(player, faction: Faction, delta: int) -> int:
    """Adjust reputation with a faction; returns new score."""
    cur = get_rep(player, faction)
    new = max(-100, min(100, cur + int(delta)))
    set_rep(player, faction, new)
    return new


def on_defeat(player, victim_class: str) -> Dict[str, int]:
    """Update faction rep when the player defeats an NPC of given class.

    Returns the delta-by-faction dict for event logging.
    """
    victim_faction = CLASS_TO_FACTION.get(victim_class, Faction.NEUTRAL)
    deltas: Dict[str, int] = {}
    for (defeated, affected), delta in KILL_REP_DELTA.items():
        if defeated == victim_faction and delta != 0:
            new_score = modify_rep(player, affected, delta)
            sign = "+" if delta > 0 else ""
            deltas[affected.value] = delta
            _ = new_score  # avoid unused var lint
    return deltas


def faction_of_class(class_value: str) -> Faction:
    return CLASS_TO_FACTION.get(class_value, Faction.NEUTRAL)


def is_hostile_pair(faction_a: Faction, faction_b: Faction) -> bool:
    """Are these two factions naturally hostile?"""
    hostile_pairs = {
        frozenset((Faction.BRIGANDS, Faction.VILLAGERS)),
        frozenset((Faction.BRIGANDS, Faction.GUARDS)),
        frozenset((Faction.BRIGANDS, Faction.MERCHANTS)),
        frozenset((Faction.BRIGANDS, Faction.TEMPLE)),
        frozenset((Faction.MONSTERS, Faction.VILLAGERS)),
        frozenset((Faction.MONSTERS, Faction.GUARDS)),
        frozenset((Faction.MONSTERS, Faction.MERCHANTS)),
    }
    return frozenset((faction_a, faction_b)) in hostile_pairs
