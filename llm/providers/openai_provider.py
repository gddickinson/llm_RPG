"""
OpenAI Chat Completions provider.

Requires the `openai` SDK and an OPENAI_API_KEY env variable.
"""

import json
import logging
import os
from typing import Any, Dict, List

import config
from .base import LLMProvider

logger = logging.getLogger("llm_rpg.providers.openai")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None, **_):
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from e
        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        logger.info(f"OpenAIProvider initialized (model={self.model})")

    def generate_response(self, prompt: str, system_prompt: str = "",
                          max_tokens: int = 512, temperature: float = 0.7) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            return ""

    def get_npc_action(self, character: Any, world_state: Dict[str, Any],
                       game_history: List[str], visible_map: str) -> Dict[str, str]:
        prompt = (
            f"CHARACTER:\n{json.dumps(character.to_dict(), indent=2)}\n\n"
            f"LOCATION: {world_state.get('current_location', 'wilderness')}\n"
            f"VISIBLE:\n{visible_map}\n\nRECENT:\n{game_history[-5:]}\n\n"
            f"What does {character.name} do next?"
        )
        return self.parse_action_response(
            self.generate_response(prompt, config.NPC_ACTION_ENHANCED_PROMPT, 400, 0.8)
        )

    def generate_npc_dialog(self, character: Any, player_message: str,
                            recent_history: List[str]) -> str:
        system_prompt = (
            f"You are {character.name}, a {character.race.value} "
            f"{character.character_class.value} in a fantasy RPG. "
            "Stay in character; reply in one or two sentences."
        )
        prompt = (
            f"RECENT:\n{recent_history[-3:] if recent_history else []}\n"
            f"PLAYER: \"{player_message}\"\n\nReply:"
        )
        return self.generate_response(prompt, system_prompt, max_tokens=200) or "..."
