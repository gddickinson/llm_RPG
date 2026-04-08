# LLM-RPG (v1) — Roadmap

## Current State
Original version of the LLM-powered D&D RPG, superseded by `llm_RPG_2`. Uses argparse CLI, standard logging, pygame GUI, and Ollama-only LLM integration. Modular structure with `engine/`, `characters/`, `world/`, `llm/`, and `ui/` packages. Has a `threaded_llm_interface.py` for async NPC processing. No tests, no web UI, Ollama-only. The project has been largely replaced by v2 but may still serve as a simpler reference implementation.

## Short-term Improvements
- [ ] Add a deprecation notice in README pointing to `llm_RPG_2` as the active version
- [ ] Remove `test_pygame.py` if it is just a sanity check, or move it to a `tests/` directory
- [ ] Clean up `npc_process_4743.log` — should be in a `logs/` directory or gitignored
- [ ] Add `requirements.txt` version pins (currently unpinned)
- [ ] Add error handling in `main.py` game loop — the `time.sleep(0.1)` busy loop could be more robust
- [ ] Add docstrings to `engine/game_engine.py`, `engine/npc_process_manager.py`

## Feature Enhancements
- [ ] Backport web UI from v2 if this version is to be maintained independently
- [ ] Add support for additional LLM providers (Anthropic, OpenAI) via `llm/llm_interface.py`
- [ ] Add save/load game functionality
- [ ] Improve `ui/gui.py` pygame rendering: add minimap, better sprite rendering, inventory panel
- [ ] Add NPC personality customization via config files instead of hardcoded values
- [ ] Add sound effects using `pygame.mixer`

## Long-term Vision
- [ ] **Decision point**: either archive this project in favor of `llm_RPG_2`, or differentiate it as the "lightweight/offline" version
- [ ] If maintaining: strip down to a minimal, well-tested single-LLM RPG engine
- [ ] If archiving: add clear documentation about what was learned and what changed in v2
- [ ] Consider extracting the core RPG engine as a shared library used by both v1 and v2

## Technical Debt
- [ ] `ui/gui_interface.py` and `ui/gui.py` have unclear separation — consolidate or document the boundary
- [ ] `llm/threaded_llm_interface.py` vs `llm/llm_interface.py` — naming inconsistency, should clarify sync vs async
- [ ] `config.py` uses mutable module globals (same issue as v2)
- [ ] No `__init__.py` content in most packages — missing re-exports and docstrings
- [ ] `engine/npc_process_manager.py` (v1) vs `engine/process_manager.py` (v2) — naming divergence
- [ ] No tests at all — add at minimum smoke tests for engine initialization and character creation
- [ ] Stale log file `npc_process_4743.log` committed to repo
