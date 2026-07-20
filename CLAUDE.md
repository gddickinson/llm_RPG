# CLAUDE.md — llm_RPG

@INTERFACE.md

## Orientation
- **Read `INTERFACE.md` first** — it maps every module. `DEVELOPMENT_PLAN.md`
  holds the phased plan (Phases 0–5 complete; Phase 6 = the Dungeon Master
  layer; P7 = conflict systems). `SESSION_LOG.md` records every development
  round. `ROADMAP.md` is a thin pointer.
- Development happens in small tested rounds on branch `v2-development`;
  **commit AND push after every green round**.

## Environment & commands
- Python venv at `.venv/` (pygame, numpy, pytest installed):
  - Run the game: `.venv/bin/python main.py`
    (flags: `--tutorial`, `--dm-bridge`, `--provider anthropic|ollama|openai`,
    `--ui terminal`, `--load`)
  - Tests: `.venv/bin/python -m unittest discover tests/`  (3650+, keep green)
  - Content validator: `.venv/bin/python -m items.data_validate`
    (run after ANY `data/` edit; exit 1 = broken cross-references)
- Headless work: `tests/__init__.py` forces SDL dummy drivers; scripts should
  set `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy`.

## Hard rules
- **Every file under 500 lines** — split modules before exceeding.
- **Content is data, not code**: items/recipes/spells/shops/monsters/quests/
  NPCs/skills/gathering/diaries/secrets/topics/heart-events/pets live in
  `data/*.json`. New content = JSON edit + validator pass. Never re-hardcode.
- **State that must survive saves** goes in `player.metadata` /
  `npc.metadata` / a subsystem `to_dict`/`from_dict` registered in
  `engine/save_load.py`. Add a round-trip test for anything new.
- **LLM discipline**: the LLM proposes, the engine disposes. All LLM output
  is parsed defensively with a heuristic fallback; per-tick LLM calls are
  forbidden (see `engine/llm_budget.py`). The game must be fully playable
  with `--provider heuristic` (the default).
- **DM charter** (`engine/dm_api.py`): the DM never touches the player
  directly; caps and budgets are enforced in code, not prompts. New DM
  powers need charter tests in `tests/test_dm_safety.py`.

## Conventions that pay off
- Event log lines are load-bearing: the topic journal, sound effects, and
  playtest assertions all observe `memory_manager.add_event` text. Prefix
  conventions: `[DM]`, `[Realm]`, `[Board]`, `[Overnight]`, `[Legend]`,
  `[Collection]`, `[Topic]`, `[Lesson]`.
- The hint bar (`ui/hints.py`) is the game's tutorial — new player-facing
  features should advertise themselves there.
- Playtesting: run scripted-and-judged sessions per the Playtest Matrix in
  `DEVELOPMENT_PLAN.md` (12 dimensions); findings become fixes or plan items.
- The historic ~1-in-10 worldgen flake was root-caused (2026-07-10):
  companion follow stalled on obstacles; fixed with obstacle-sliding in
  `characters/companions.py`. If a new intermittent failure appears,
  suspect NPC movement/worldgen randomness and rerun once — but don't
  assume it's the old flake; that one is dead.
