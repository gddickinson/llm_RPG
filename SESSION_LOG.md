# LLM-RPG — Session Log

## 2026-05-17 — Major expansion: independent fully-functional game

**Goal:** Transform llm_RPG (v1) into a standalone, expansive, fully-functional locally-runnable game. Bring in the best ideas from `llm_RPG_2` and `autonomous_world` without making this a fork of either.

### Pre-existing state (snapshot)

- ~5,900 LOC across `engine/`, `world/`, `characters/`, `llm/`, `ui/`
- Two oversized files violating 500-LOC rule: `engine/game_engine.py` (1566), `ui/gui.py` (1104)
- Ollama-only LLM integration (no fallback if Ollama is offline)
- No save/load, no quests, no real items (items were bare strings), no skills
- Tests directory existed but contained only stubs
- pygame GUI worked, terminal UI worked

### Reference repos surveyed

- **`/Volumes/GeorgeDrive/claude_test/llm_RPG_2`** — v2 prototype: FastAPI web server, multi-provider LLM abstraction (`llm/interface.py`), typer CLI, tkinter GUI client.
- **`/Users/george/Documents/GitHub/autonomous_world`** — large autonomous world simulator: procedural world gen, biomes, D&D systems, quest boards, economy, sprite-based pygame rendering, 155 systems modules.

### Plan executed this session

**Phase 1 — Foundation**
- INTERFACE.md (project navigation map)
- SESSION_LOG.md (this file)
- LLM provider abstraction (`llm/providers/`) with heuristic fallback so the game runs without Ollama

**Phase 2 — Game depth**
- Real items system (`items/`) — `Item` class, registry, loot tables
- Quest system (`quests/`) — kill/fetch/talk/explore objectives, templates
- Save/load (`engine/save_load.py`) — JSON full-state persistence
- Skills (`engine/skills.py`) — D&D-style skill checks

**Phase 3 — Refactor**
- Split `engine/game_engine.py` into `combat_system.py`, `economy_system.py`, `dialog_system.py`, `action_router.py`, plus thinner `game_engine.py`
- Split `ui/gui.py` into `renderer.py`, `sprite_loader.py`, `hud.py`, `input_handler.py`, thinner `gui.py`

**Phase 4 — Visual & World polish**
- Procedural sprite renderer (no external PNGs needed; inspired by `autonomous_world/game/ui/sprite_loader.py`)
- Day/night visual overlay
- Biome-based procedural world generation

**Phase 5 — Tests + docs**
- Unit tests for items, quests, save/load, combat, world gen
- Updated README + ROADMAP

### Design decisions

- **Heuristic LLM fallback by default**: keeps the game playable for anyone without Ollama, while still benefiting users who have it.
- **JSON saves**: human-readable, easy to debug, no schema lock-in.
- **No new heavy dependencies**: kept the stack at pygame + requests + (optional) anthropic/openai. No FastAPI server (kept simpler than llm_RPG_2).
- **Procedural sprites over PNG assets**: no asset pipeline, fully self-contained game.
- **Did NOT port**: the multiprocess NPC architecture stays as-is (existing one works); web server (overkill for local game); 3D renderer (out of scope).

### How to run

```bash
python main.py --ui gui                 # Pygame GUI (default)
python main.py --ui terminal            # Terminal mode
python main.py --provider heuristic     # No-LLM mode (default)
python main.py --provider ollama --model llama3
python main.py --load saves/quicksave.json
```

### Known issues / next steps

- See ROADMAP.md.
