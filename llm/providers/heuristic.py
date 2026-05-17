"""
Heuristic (rule-based) LLM provider.

No external dependencies — the game is fully playable without any LLM running.
The "AI" decisions are produced by combining the character's personality,
goals, recent visible environment, and a small library of randomized
dialog/emote templates.

This provider keeps gameplay coherent and lively. It's not as creative as
an actual LLM, but it makes the demo runnable anywhere, anytime.
"""

import logging
import random
from typing import Any, Dict, List

from .base import LLMProvider

logger = logging.getLogger("llm_rpg.providers.heuristic")


# Templates by character class / role -----------------------------------------

_GREETINGS = {
    "merchant": [
        "Welcome, friend! Looking to buy or sell today?",
        "Step inside, I have the finest wares in the region.",
        "A customer! Let me show you what I have.",
    ],
    "guard": [
        "Halt. State your business in our village.",
        "Eyes open, stranger. Trouble is brewing on the road.",
        "Welcome to Oakvale. Keep the peace and we'll have no quarrel.",
    ],
    "warrior": [
        "Well met, traveler. The roads are dangerous of late.",
        "A fellow blade! Care to share a story?",
    ],
    "wizard": [
        "Ahh, an interesting aura around you...",
        "The threads of fate brought you here today.",
    ],
    "bard": [
        "Hail and well met! Care to hear a song?",
        "A new face! Have you any tales worth a verse?",
    ],
    "villager": [
        "Oh, hello there. Quiet day, isn't it?",
        "Welcome, traveler.",
    ],
    "cleric": [
        "Blessings of the Light upon you, friend.",
        "May your path be clear and your heart steady.",
    ],
    "brigand": [
        "Hand over your coin if you value your skin!",
        "You picked the wrong road to wander, fool.",
    ],
    "monster": [
        "*GROWLS*",
        "*roars menacingly*",
    ],
}

_GENERIC_REPLIES = [
    "Hmm, that is something to consider.",
    "Aye, you may be right about that.",
    "Strange times we live in.",
    "I'll have to think on that.",
    "Truth be told, I don't rightly know.",
]

_GOAL_REPLIES = {
    "Make a profit": "Times have been hard, but I get by.",
    "Protect the village": "I've sworn my blade to this town.",
    "Find adventure": "I yearn for the open road myself.",
    "Rob travelers": "Hand it over!",
}

_EMOTIONS = ["calm", "wary", "cheerful", "tired", "curious", "suspicious", "angry"]


# ---------------------------------------------------------------------------


class HeuristicProvider(LLMProvider):
    """Rule-based provider that needs no LLM backend."""

    name = "heuristic"

    def __init__(self, seed: int = None, **_):
        self.rng = random.Random(seed)

    # Generic completion -----------------------------------------------------

    def generate_response(self, prompt: str, system_prompt: str = "",
                          max_tokens: int = 512, temperature: float = 0.7) -> str:
        return self.rng.choice(_GENERIC_REPLIES)

    # NPC action -------------------------------------------------------------

    def get_npc_action(self, character: Any, world_state: Dict[str, Any],
                       game_history: List[str], visible_map: str) -> Dict[str, str]:
        """Heuristic NPC behavior.

        Strategy:
        - Hostile classes (BRIGAND/MONSTER) attack the player on sight.
        - Peaceful NPCs follow a daily schedule based on the in-game hour;
          urgent needs (starving / exhausted) override the schedule.
        - Otherwise: greet the player, idle, or wander.
        """
        klass = getattr(getattr(character, "character_class", None), "value", "villager")
        emotion = self.rng.choice(_EMOTIONS)
        action, target, dialog = "wait", "for a moment", ""

        player_in_view = "player" in (visible_map or "").lower() or \
                         "@" in (visible_map or "")

        # Hostile classes — same as before
        if klass in ("brigand", "monster", "troll"):
            if player_in_view:
                action, target = "attack", "player"
                dialog = self.rng.choice(_GREETINGS.get("brigand", [""]))
                emotion = "angry"
            else:
                action, target = "move", self.rng.choice(
                    ["north", "south", "east", "west"])
                emotion = "wary"
            return self._wrap(character, action, target, dialog, emotion)

        # Peaceful NPCs — check urgent needs first, then schedule
        try:
            from characters.needs import (
                get_hunger, get_fatigue,
                HUNGER_STARVING, FATIGUE_EXHAUSTED,
            )
            if get_fatigue(character) >= FATIGUE_EXHAUSTED:
                return self._wrap(character, "sleep", "home",
                                  "(I need rest...)", "exhausted")
            if get_hunger(character) >= HUNGER_STARVING:
                return self._wrap(character, "move", "tavern",
                                  "(I must eat soon.)", "hungry")
        except Exception:
            pass

        # Schedule-driven behavior
        try:
            from characters.schedules import current_entry, activity_to_action
            hour = self._parse_hour(world_state)
            entry = current_entry(klass, hour)
            if entry is not None:
                _, activity, loc_keyword = entry
                act, tgt = activity_to_action(activity, loc_keyword)
                # Add a greeting when peaceful NPC sees the player
                if player_in_view and self.rng.random() < 0.25:
                    greet = self.rng.choice(
                        _GREETINGS.get(klass, _GREETINGS["villager"]))
                    return self._wrap(character, "greet", "player",
                                      greet, "calm")
                return self._wrap(character, act, tgt, "", emotion)
        except Exception:
            pass

        # Fallback to old behavior
        if klass == "merchant":
            if self.rng.random() < 0.3:
                action, target = "talk", "passerby"
                dialog = self.rng.choice(_GREETINGS["merchant"])
            else:
                action, target = "wait", "tending shop"
        elif klass == "guard":
            if player_in_view and self.rng.random() < 0.2:
                action, target = "greet", "player"
                dialog = self.rng.choice(_GREETINGS["guard"])
            else:
                action, target = "move", self.rng.choice(
                    ["north", "south", "east", "west"])
        elif klass == "bard":
            if self.rng.random() < 0.5:
                action, target = "talk", "anyone listening"
                dialog = self.rng.choice(_GREETINGS["bard"])
            else:
                action, target = "move", self.rng.choice(
                    ["north", "south", "east", "west"])
        else:
            if self.rng.random() < 0.4:
                action, target = "move", self.rng.choice(
                    ["north", "south", "east", "west"])
            elif self.rng.random() < 0.3 and player_in_view:
                action, target = "greet", "player"
                dialog = self.rng.choice(_GREETINGS.get(klass, _GREETINGS["villager"]))

        return self._wrap(character, action, target, dialog, emotion)

    def _wrap(self, character, action, target, dialog, emotion):
        return {
            "action": action,
            "target": target,
            "dialog": dialog,
            "thoughts": f"({character.name} acts on instinct.)",
            "emotion": emotion,
            "goal_update": "",
        }

    def _parse_hour(self, world_state: Dict[str, Any]) -> int:
        """Best-effort extraction of the current hour."""
        tod = (world_state or {}).get("time_of_day", "")
        # Map to representative hours
        mapping = {"morning": 9, "afternoon": 14,
                   "evening": 19, "night": 23}
        return mapping.get(tod, 12)

    # Dialog -----------------------------------------------------------------

    def generate_npc_dialog(self, character: Any, player_message: str,
                            recent_history: List[str]) -> str:
        msg = (player_message or "").lower()
        klass = getattr(getattr(character, "character_class", None), "value", "villager")

        # Greeting detection
        if any(g in msg for g in ("hello", "hi ", "greetings", "hey", "good day", "well met")):
            return self.rng.choice(_GREETINGS.get(klass, _GREETINGS["villager"]))

        # Trade
        if any(g in msg for g in ("buy", "sell", "trade", "price", "wares")):
            if klass == "merchant":
                return "Aye, I've potions, ale, and trinkets. What catches your eye?"
            return "I'm not much of a trader, but perhaps the merchant in town can help."

        # Quest / rumor
        if any(g in msg for g in ("quest", "rumor", "news", "trouble", "danger")):
            return self.rng.choice([
                "Aye, there's a troll on the east road. Gorkash they call him.",
                "Strange lights in the mountains lately. Some say a wizard returned.",
                "Bandits attacked a merchant caravan last week. Wasn't pretty.",
            ])

        # Personal goal reply
        for goal in getattr(character, "goals", []) or []:
            for key, reply in _GOAL_REPLIES.items():
                if key.lower() in goal.lower():
                    return reply

        # Default
        return self.rng.choice(_GENERIC_REPLIES)
