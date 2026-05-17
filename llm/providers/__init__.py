"""
LLM Provider factory.

Currently registered providers:
- heuristic: rule-based, no external dependencies (default)
- ollama: local Ollama HTTP API
- anthropic: Anthropic Claude API
- openai: OpenAI Chat Completions

Use `get_provider(name, **kwargs)` to construct one.
"""

import logging
from typing import Optional
from .base import LLMProvider
from .heuristic import HeuristicProvider

logger = logging.getLogger("llm_rpg.providers")

# Lazy-imported providers (so missing optional deps don't break import)
_PROVIDER_REGISTRY = {}


def _register_lazy(name: str, factory_callable):
    _PROVIDER_REGISTRY[name] = factory_callable


def _make_heuristic(**kwargs):
    return HeuristicProvider(**kwargs)


def _make_ollama(**kwargs):
    from .ollama import OllamaProvider
    return OllamaProvider(**kwargs)


def _make_anthropic(**kwargs):
    from .anthropic import AnthropicProvider
    return AnthropicProvider(**kwargs)


def _make_openai(**kwargs):
    from .openai_provider import OpenAIProvider
    return OpenAIProvider(**kwargs)


_register_lazy("heuristic", _make_heuristic)
_register_lazy("ollama", _make_ollama)
_register_lazy("anthropic", _make_anthropic)
_register_lazy("openai", _make_openai)


def get_provider(name: str = "heuristic", **kwargs) -> LLMProvider:
    """Construct a provider by name. Falls back to heuristic on import errors."""
    if name not in _PROVIDER_REGISTRY:
        logger.warning(f"Unknown provider '{name}', falling back to heuristic")
        return HeuristicProvider(**{k: v for k, v in kwargs.items()
                                   if k in ("seed",)})
    try:
        return _PROVIDER_REGISTRY[name](**kwargs)
    except ImportError as e:
        logger.warning(f"Provider '{name}' unavailable ({e}), falling back to heuristic")
        return HeuristicProvider()
    except Exception as e:
        logger.warning(f"Provider '{name}' failed to initialize ({e}), falling back to heuristic")
        return HeuristicProvider()


def available_providers() -> list:
    return list(_PROVIDER_REGISTRY.keys())


__all__ = ["LLMProvider", "HeuristicProvider", "get_provider", "available_providers"]
