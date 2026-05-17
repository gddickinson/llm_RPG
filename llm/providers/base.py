"""
Abstract base class for LLM providers.

A provider implements 3 entry points used by the game engine:
- generate_response(prompt, system_prompt, ...) — generic completion
- get_npc_action(character, world_state, history, visible_map) — structured action dict
- generate_npc_dialog(character, player_message, history) — dialog string
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger("llm_rpg.providers.base")


class LLMProvider(ABC):
    """Abstract LLM provider."""

    name: str = "base"

    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        ...

    @abstractmethod
    def get_npc_action(
        self,
        character: Any,
        world_state: Dict[str, Any],
        game_history: List[str],
        visible_map: str,
    ) -> Dict[str, str]:
        ...

    @abstractmethod
    def generate_npc_dialog(
        self,
        character: Any,
        player_message: str,
        recent_history: List[str],
    ) -> str:
        ...

    # Shared helpers ----------------------------------------------------------

    @staticmethod
    def parse_action_response(response: str) -> Dict[str, str]:
        """Parse 'ACTION: ...\\nTARGET: ...' style responses into a dict."""
        data = {
            "action": "",
            "target": "",
            "dialog": "",
            "thoughts": "",
            "emotion": "",
            "goal_update": "",
        }
        keys = {
            "ACTION:": "action",
            "TARGET:": "target",
            "DIALOG:": "dialog",
            "THOUGHTS:": "thoughts",
            "EMOTION:": "emotion",
            "GOAL_UPDATE:": "goal_update",
        }
        for line in response.split("\n"):
            line = line.strip()
            for prefix, key in keys.items():
                if line.upper().startswith(prefix):
                    data[key] = line[len(prefix):].strip()
                    break

        if not data["action"]:
            if "wait" in response.lower():
                data["action"] = "wait"
                data["target"] = "patiently"
            else:
                data["action"] = "wait"
                data["target"] = "looking around"
                data["thoughts"] = "Not sure what to do."
        return data

    @staticmethod
    def shutdown() -> None:
        """Override if the provider needs cleanup (threads, sockets, ...)."""
        return None
