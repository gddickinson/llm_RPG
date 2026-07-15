"""
LLM Interface — facade over the providers package.

The engine and other modules construct LLMInterface(provider=..., model=...)
and treat it as a single API. Internally, the call is forwarded to a
provider implementation (heuristic / ollama / anthropic / openai).

The legacy positional API LLMInterface(model_name=...) is preserved so
existing code (and the NPC subprocess) keeps working.
"""

import logging
from typing import Any, Dict, List

import config
from llm.providers import get_provider

logger = logging.getLogger("llm_rpg.llm")


class LLMInterface:
    """High-level LLM API used throughout the engine.

    Parameters
    ----------
    model_name : str
        Model identifier (default from config). Forwarded to the provider.
    provider : str
        Provider name: 'heuristic' (default), 'ollama', 'anthropic', 'openai'.
    api_url : str | None
        Override API URL (mainly for ollama).
    """

    def __init__(
        self,
        model_name: str = None,
        provider: str = None,
        api_url: str = None,
        **kwargs,
    ):
        self.model_name = model_name or config.DEFAULT_MODEL
        self.provider_name = provider or getattr(config, "DEFAULT_PROVIDER", "heuristic")

        provider_kwargs = {"model": self.model_name, **kwargs}
        if api_url:
            provider_kwargs["api_url"] = api_url

        self.provider = get_provider(self.provider_name, **provider_kwargs)
        # Observability: how many calls of each kind this session (P3.9)
        self.call_counts = {"response": 0, "action": 0, "dialog": 0}
        logger.info(
            f"LLMInterface initialized (provider={self.provider.name}, model={self.model_name})"
        )

    # ------------------------------------------------------------------ #

    def generate_response(self, prompt: str, system_prompt: str = "",
                          max_tokens: int = config.DEFAULT_MAX_TOKENS,
                          temperature: float = config.DEFAULT_TEMPERATURE) -> str:
        self.call_counts["response"] += 1
        return self.provider.generate_response(prompt, system_prompt,
                                               max_tokens, temperature)

    def get_npc_action(self, character: Any, world_state: Dict[str, Any],
                       game_history: List[str], visible_map: str,
                       system_prompt: str = None) -> Dict[str, str]:
        # system_prompt kwarg retained for compatibility with older callers
        self.call_counts["action"] += 1
        return self.provider.get_npc_action(character, world_state,
                                            game_history, visible_map)

    def generate_npc_dialog(self, character: Any, player_message: str,
                            recent_history: List[str]) -> str:
        self.call_counts["dialog"] += 1
        return self.provider.generate_npc_dialog(character, player_message,
                                                 recent_history)

    def shutdown(self) -> None:
        if hasattr(self.provider, "shutdown"):
            try:
                self.provider.shutdown()
            except Exception as e:
                logger.warning(f"Provider shutdown error: {e}")

    # --------- backward compat with old code that used _parse_action_response
    def _parse_action_response(self, response: str) -> Dict[str, str]:
        from llm.providers.base import LLMProvider
        return LLMProvider.parse_action_response(response)
