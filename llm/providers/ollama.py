"""
Ollama HTTP API provider.

Connects to a locally-running Ollama instance.
Requires the `requests` package (already a project dep).
"""

import json
import logging
from typing import Any, Dict, List

import requests

import config
from .base import LLMProvider

logger = logging.getLogger("llm_rpg.providers.ollama")


class OllamaProvider(LLMProvider):
    """Ollama provider — local LLM via HTTP."""

    name = "ollama"

    def __init__(self, model: str = None, api_url: str = None,
                 timeout: float = 30.0, **_):
        self.model = model or config.DEFAULT_MODEL
        self.api_url = api_url or config.LLM_API_URL
        self.timeout = timeout
        logger.info(f"OllamaProvider initialized (model={self.model})")

    def generate_response(self, prompt: str, system_prompt: str = "",
                          max_tokens: int = config.DEFAULT_MAX_TOKENS,
                          temperature: float = config.DEFAULT_TEMPERATURE) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            r = requests.post(self.api_url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return ""

    def get_npc_action(self, character: Any, world_state: Dict[str, Any],
                       game_history: List[str], visible_map: str) -> Dict[str, str]:
        prompt = (
            f"CHARACTER:\n{json.dumps(character.to_dict(), indent=2)}\n\n"
            f"LOCATION: {world_state.get('current_location', 'wilderness')}\n"
            f"TIME OF DAY: {world_state.get('time_of_day', 'day')}\n\n"
            f"VISIBLE ENVIRONMENT:\n{visible_map}\n\n"
            f"RECENT HISTORY:\n{game_history[-5:] if len(game_history) > 5 else game_history}\n\n"
            f"MEMORIES:\n{[m.get('event', '') for m in (character.memories or [])[-5:]]}\n\n"
            f"What does {character.name} do next?"
        )
        response = self.generate_response(
            prompt, system_prompt=config.NPC_ACTION_ENHANCED_PROMPT,
            temperature=0.8,
        )
        return self.parse_action_response(response)

    def generate_npc_dialog(self, character: Any, player_message: str,
                            recent_history: List[str]) -> str:
        system_prompt = (
            f"You are {character.name}, a {character.race.value} "
            f"{character.character_class.value} in a fantasy RPG. "
            "Stay in character. Brief and conversational."
        )
        prompt = (
            f"CHARACTER:\n{json.dumps(character.to_dict(), indent=2)}\n\n"
            f"RECENT CONVERSATION:\n{recent_history[-3:] if recent_history else []}\n\n"
            f"PLAYER SAYS: \"{player_message}\"\n\n"
            f"How does {character.name} respond?"
        )
        response = self.generate_response(prompt, system_prompt, temperature=0.7)
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        return response or "..."
