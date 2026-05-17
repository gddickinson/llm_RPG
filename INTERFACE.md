# LLM-RPG — INTERFACE.md

Top-level navigation map for the codebase. Read this **before** opening source files.

## Architecture Overview

```
llm_RPG/
├── main.py                     # Entry point
├── config.py                   # Centralized config + system prompts
├── INTERFACE.md                # This file
├── SESSION_LOG.md              # Development progress log
├── README.md                   # User-facing docs
├── ROADMAP.md                  # Future plans
├── requirements.txt
│
├── engine/                     # Game engine — core game loop, turn logic
├── characters/                 # Characters, NPCs, factions, schedules, party
├── world/                      # World, map, calendar, biomes, interiors
├── items/                      # Item system + crafting
├── quests/                     # Quest system + quest boards
├── llm/                        # LLM interface + providers
├── ui/                         # GUI (pygame) and terminal UI
├── saves/                      # Saved games (created at runtime)
├── tests/                      # Unit tests (107+)
└── _archive/                   # Old/deprecated code
```

## Module Index

### engine/ — Core game logic

- **`game_engine.py`** — `GameEngine`; orchestrates world, NPCs, player, all subsystems.
- **`action_router.py`** — Routes NPC actions to specialized handlers.
- **`combat_system.py`** — Player vs NPC vs NPC combat, damage, defeat, loot, faction rep on kill.
- **`economy_system.py`** — Buy/sell/trade/give between characters.
- **`dialog_system.py`** — Player↔NPC dialog flow.
- **`dialog_trees.py`** — Branching dialog tree templates for heuristic NPCs.
- **`memory_manager.py`** — Event history.
- **`save_load.py`** — JSON full-state save/load.
- **`skills.py`** — D&D-style skill checks.
- **`leveling.py`** — XP curve, auto level-up with HP/stat increases.
- **`banking.py`** — Deposit/withdraw gold at temples/shops.
- **`npc_process.py`** / **`npc_process_manager.py`** — Multiprocess NPC AI (optional).
- **`player_actions.py`** — Player-driven actions (pickup/drop/use/attack/move).

### characters/ — Characters, NPCs, social systems

- **`character.py`** — `Character` dataclass (player + NPC).
- **`character_types.py`** — Class/race/alignment/trait/status enums.
- **`npc_manager.py`** — NPC creation + presets.
- **`factions.py`** — `Faction` enum, reputation tracking, faction relationships, on-defeat hooks.
- **`schedules.py`** — Daily routines per NPC class (work / eat / drink / sleep).
- **`needs.py`** — Hunger and fatigue simulation for NPCs.
- **`companions.py`** — `CompanionManager`; party recruitment, follow-and-fight behavior.

### world/ — World, map, calendar, locations

- **`world.py`** — `World`; high-level world state; `get_location_at` returns innermost.
- **`world_map.py`** — `WorldMap`, `TerrainType`; tile grid, movement, FOV.
- **`location.py`** — `Location`, `LocationFactory`.
- **`biome.py`** — `Biome` enum and biome→terrain mapping.
- **`calendar.py`** — `Date`, `Season`; 12-month calendar, day-night clock, season tints.
- **`world_generator.py`** — `WorldGenerator`; procedural world.
- **`interiors.py`** — Building interior mini-maps (tavern, forge, shop, temple).
- **`encounters.py`** — `EncounterManager`; wilderness monster spawns.

### items/ — Item system + crafting

- **`item.py`** — `Item` dataclass; types, rarity, effects.
- **`item_registry.py`** — 35+ predefined items.
- **`loot_tables.py`** — Drop tables by enemy class.
- **`crafting.py`** — Recipe registry + `craft()` function (forge-gated, ingredients).

### quests/ — Quest system

- **`quest.py`** — `Quest`, `QuestObjective`, `QuestStatus`, `ObjectiveType`.
- **`quest_manager.py`** — Tracks quests, event hooks for progress.
- **`quest_templates.py`** — Predefined quests.
- **`quest_board.py`** — `QuestBoardManager`; tavern bulletin board.

### llm/ — LLM integration

- **`llm_interface.py`** — `LLMInterface`; facade over providers.
- **`providers/`** — Pluggable backends.
  - **`base.py`** — `LLMProvider` ABC.
  - **`heuristic.py`** — Rule-based default; honors NPC schedules + needs.
  - **`ollama.py`** — Local Ollama HTTP.
  - **`anthropic.py`** — Anthropic Claude.
  - **`openai_provider.py`** — OpenAI.

### ui/ — User interfaces

- **`gui.py`** — `GameGUI`; pygame main window.
- **`renderer.py`** — `MapRenderer`; map tiles + sprites + lighting.
- **`sprite_loader.py`** — Procedural sprite generation (no PNG assets).
- **`hud.py`** — Status, HP/XP bars, mini-map, event log, quest tracker.
- **`input_handler.py`** — Keyboard input routing (movement, dialog, quest hotkeys).
- **`terminal_ui.py`** — Text-based UI.

## Key Classes — where to find them

| Class                  | File                                |
|------------------------|-------------------------------------|
| `GameEngine`           | `engine/game_engine.py`             |
| `Character`            | `characters/character.py`           |
| `NPCManager`           | `characters/npc_manager.py`         |
| `CompanionManager`     | `characters/companions.py`          |
| `Faction`              | `characters/factions.py`            |
| `World`                | `world/world.py`                    |
| `WorldGenerator`       | `world/world_generator.py`          |
| `Interior`             | `world/interiors.py`                |
| `EncounterManager`     | `world/encounters.py`               |
| `Date`, `Season`       | `world/calendar.py`                 |
| `Item`                 | `items/item.py`                     |
| `Recipe`, `craft()`    | `items/crafting.py`                 |
| `Quest`                | `quests/quest.py`                   |
| `QuestBoard`           | `quests/quest_board.py`             |
| `Bank`                 | `engine/banking.py`                 |
| `CombatSystem`         | `engine/combat_system.py`           |
| `DialogTree`           | `engine/dialog_trees.py`            |
| `LLMProvider`          | `llm/providers/base.py`             |
| `HeuristicProvider`    | `llm/providers/heuristic.py`        |
| `MapRenderer`          | `ui/renderer.py`                    |
| `SpriteLoader`         | `ui/sprite_loader.py`               |

## Engine subsystems wired to the game loop

Each turn (after a player move / dialog / action):
1. `world.advance_time(1)` — calendar minute passes
2. `quest_manager.on_turn_advanced()` — SURVIVE objectives tick
3. NPC needs tick — hunger / fatigue grow
4. `encounter_manager.maybe_spawn()` — chance of wilderness monster
5. `companion_manager.update()` — party members follow / fight
6. Every N turns: NPC actions (LLM or heuristic-based, including schedules)

## Adding new content — quick recipes

- **New item**: append to `items/item_registry.py`.
- **New recipe**: append to `items/crafting.py` `RECIPES` dict.
- **New quest**: add template in `quests/quest_templates.py`; post to a board via `default_boards()` if appropriate.
- **New NPC class**: extend `CharacterClass` in `characters/character_types.py`; add schedule in `characters/schedules.py`; add to `CLASS_TO_FACTION` in `characters/factions.py`.
- **New dialog tree**: add factory in `engine/dialog_trees.py` and register in `_TREE_BY_CLASS` or `_TREE_BY_NPC_ID`.
- **New action**: add handler in `engine/action_router.py`.
- **New terrain**: extend `TerrainType` + add sprite in `ui/sprite_loader.py`.
- **New encounter monster**: add entry in `world/encounters.py` `_build_monster()` + `ENCOUNTER_TABLE`.
- **New LLM provider**: subclass `LLMProvider` in `llm/providers/`, register in `llm/providers/__init__.py`.

## File size policy

All source files stay **under 500 lines** (per global coding preferences). Split modules before exceeding.
