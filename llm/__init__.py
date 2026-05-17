"""LLM package: high-level interface + pluggable providers.

Public API:
- LLMInterface — facade used by the engine
- get_provider(name) — direct provider construction
- available_providers() — list registered providers
"""

from llm.llm_interface import LLMInterface
from llm.providers import get_provider, available_providers, LLMProvider

__all__ = ["LLMInterface", "get_provider", "available_providers", "LLMProvider"]
