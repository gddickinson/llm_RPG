"""
Anthropic Claude provider.

Requires the `anthropic` SDK and an ANTHROPIC_API_KEY env variable.
Falls back gracefully if the package isn't installed.
"""

import json
import logging
import os
from typing import Any, Dict, List

import config
from .base import LLMProvider

logger = logging.getLogger("llm_rpg.providers.anthropic")


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20251001",
                 api_key: str = None, **_):
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from e
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        logger.info(f"AnthropicProvider initialized (model={self.model})")

    def generate_response(self, prompt: str, system_prompt: str = "",
                          max_tokens: int = 512, temperature: float = 0.7) -> str:
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in msg.content if hasattr(b, "text"))
        except Exception as e:
            logger.error(f"Anthropic request failed: {e}")
            return ""

    def get_npc_action(self, character: Any, world_state: Dict[str, Any],
                       game_history: List[str], visible_map: str) -> Dict[str, str]:
        prompt = (
            f"CHARACTER:\n{json.dumps(character.to_dict(), indent=2)}\n\n"
            f"LOCATION: {world_state.get('current_location', 'wilderness')}\n"
            f"TIME OF DAY: {world_state.get('time_of_day', 'day')}\n\n"
            f"VISIBLE:\n{visible_map}\n\nRECENT:\n{game_history[-5:]}\n\n"
            f"What does {character.name} do next?"
        )
        response = self.generate_response(
            prompt, config.NPC_ACTION_ENHANCED_PROMPT, max_tokens=400, temperature=0.8,
        )
        return self.parse_action_response(response)

    def generate_npc_dialog(self, character: Any, player_message: str,
                            recent_history: List[str]) -> str:
        system_prompt = (
            f"You are {character.name}, a {character.race.value} "
            f"{character.character_class.value} in a fantasy RPG. "
            "Stay in character. Reply in one or two sentences."
        )
        prompt = (
            f"CHARACTER:\n{json.dumps(character.to_dict(), indent=2)}\n\n"
            f"RECENT:\n{recent_history[-3:] if recent_history else []}\n\n"
            f"PLAYER: \"{player_message}\"\n\nReply:"
        )
        return self.generate_response(prompt, system_prompt, max_tokens=200) or "..."
