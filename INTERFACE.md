# LLM-RPG — INTERFACE.md

Top-level navigation map for the codebase. Read this **before** opening source files.

## Architecture Overview

```
llm_RPG/
├── main.py                     # Entry point — argparse, mode selection
├── config.py                   # Centralized config + system prompts
├── INTERFACE.md                # This file
├── SESSION_LOG.md              # Development progress log
├── README.md                   # User-facing docs
├── ROADMAP.md                  # Future plans
├── requirements.txt
│
├── engine/                     # Game engine — core game loop, turn logic
├── characters/                 # Character/NPC classes, types
├── world/                      # World, map, locations, biomes
├── items/                      # Item system (NEW)
├── quests/                     # Quest system (NEW)
├── llm/                        # LLM interface + providers
├── ui/                         # GUI (pygame) and terminal UI
├── saves/                      # Saved games (created at runtime)
├── tests/                      # Unit tests
└── _archive/                   # Old/deprecated code
```

## Module Index (by package)

### engine/ — Core game logic
- **`game_engine.py`** — `GameEngine` class; orchestrates world, NPCs, player. Main entry point for all game actions.
- **`action_router.py`** — Routes NPC actions to specialized handlers (combat/social/economic/...).
- **`combat_system.py`** — `CombatSystem`; player vs NPC vs NPC combat, damage rolls, death, loot.
- **`economy_system.py`** — `EconomySystem`; buy/sell/trade/give between characters.
- **`dialog_system.py`** — Player↔NPC dialog flow using LLM or heuristic provider.
- **`memory_manager.py`** — `MemoryManager`; event history, save/load history.
- **`save_load.py`** — `SaveManager`; serialize/deserialize full game state to JSON.
- **`skills.py`** — `SkillSystem`; D&D-style skill checks with ability score modifiers.
- **`npc_process.py`** — NPC subprocess main loop (multiprocess LLM calls).
- **`npc_process_manager.py`** — `NPCProcessManager`; spawns/manages NPC processes.

### characters/ — Characters & NPCs
- **`character.py`** — `Character` dataclass (player + NPC); HP, stats, inventory, memories, relationships, skills.
- **`character_types.py`** — `CharacterClass`, `CharacterRace`, `Alignment`, `CharacterTrait`, `CharacterStatus` enums.
- **`npc_manager.py`** — `NPCManager`; create/track NPCs (presets + random generation).

### world/ — World, map, locations
- **`world.py`** — `World`; high-level world state (time, locations, ground items, shrines).
- **`world_map.py`** — `WorldMap`, `TerrainType`; tile grid, movement, FOV.
- **`location.py`** — `Location`, `LocationFactory`; named regions (towns, taverns, shops...).
- **`biome.py`** — `Biome` enum and biome→terrain mapping (NEW).
- **`world_generator.py`** — `WorldGenerator`; procedural world generation w/ biomes (NEW).

### items/ — Item system (NEW)
- **`item.py`** — `Item` dataclass; name, type, value, effect, rarity.
- **`item_registry.py`** — `ITEM_REGISTRY`; predefined items by ID (potions, weapons, armor, ...).
- **`loot_tables.py`** — Loot drop tables by enemy class/level.

### quests/ — Quest system (NEW)
- **`quest.py`** — `Quest`, `QuestObjective`, `QuestStatus`, `ObjectiveType`.
- **`quest_manager.py`** — `QuestManager`; track active/completed quests, check progress.
- **`quest_templates.py`** — Predefined quest templates (kill troll, fetch herbs, ...).

### llm/ — LLM integration
- **`llm_interface.py`** — `LLMInterface`; high-level API used by engine. Delegates to a provider.
- **`providers/`** — Provider implementations.
  - **`base.py`** — `LLMProvider` abstract base class.
  - **`heuristic.py`** — `HeuristicProvider`; rule-based fallback (no LLM needed). **Default.**
  - **`ollama.py`** — Ollama HTTP provider (local).
  - **`anthropic.py`** — Anthropic Claude provider (needs ANTHROPIC_API_KEY).
  - **`openai.py`** — OpenAI provider (needs OPENAI_API_KEY).
  - **`__init__.py`** — `get_provider(name)` factory.

### ui/ — User interfaces
- **`gui.py`** — `GameGUI`; main pygame entry point (window, event loop, menus).
- **`renderer.py`** — `MapRenderer`; draws the world map (tiles, sprites, lighting).
- **`sprite_loader.py`** — `SpriteLoader`; procedural sprite generation (no PNG assets needed).
- **`hud.py`** — `HUD`; status bars, mini-map, event log, dialog box.
- **`input_handler.py`** — `InputHandler`; keyboard/mouse → game actions.
- **`terminal_ui.py`** — `TerminalUI`; text-based interface.
- **`gui_interface.py`** — Legacy launcher (kept for backward compat).
- **`threaded_llm_interface.py`** — Threaded LLM (older variant, kept).

## Key Classes — where to find them

| Class                  | File                                |
|------------------------|-------------------------------------|
| `GameEngine`           | `engine/game_engine.py`             |
| `Character`            | `characters/character.py`           |
| `NPCManager`           | `characters/npc_manager.py`         |
| `World`                | `world/world.py`                    |
| `WorldMap`             | `world/world_map.py`                |
| `WorldGenerator`       | `world/world_generator.py`          |
| `Item`                 | `items/item.py`                     |
| `Quest`                | `quests/quest.py`                   |
| `QuestManager`         | `quests/quest_manager.py`           |
| `SaveManager`          | `engine/save_load.py`               |
| `CombatSystem`         | `engine/combat_system.py`           |
| `LLMProvider`          | `llm/providers/base.py`             |
| `HeuristicProvider`    | `llm/providers/heuristic.py`        |
| `MapRenderer`          | `ui/renderer.py`                    |
| `SpriteLoader`         | `ui/sprite_loader.py`               |

## Module dependency direction

```
main.py
  └── engine.game_engine
        ├── world.world / world.world_map / world.world_generator
        ├── characters.npc_manager → characters.character
        ├── items.item_registry
        ├── quests.quest_manager
        ├── llm.llm_interface → llm.providers.*
        ├── engine.combat_system / economy_system / dialog_system
        ├── engine.memory_manager / save_load / skills
        └── engine.npc_process_manager
ui.gui
  ├── ui.renderer → ui.sprite_loader
  ├── ui.hud
  └── ui.input_handler
```

Engine never depends on UI. UI depends on engine.

## Adding new content — quick recipes

- **New item**: add entry to `items/item_registry.py`.
- **New quest**: add template to `quests/quest_templates.py`.
- **New NPC type**: extend `CharacterClass` in `characters/character_types.py`, optionally add factory method to `npc_manager.py`.
- **New action**: add handler method to `engine/action_router.py` (or specialized system).
- **New LLM provider**: subclass `LLMProvider` in `llm/providers/`, register in `llm/providers/__init__.py`.
- **New terrain**: extend `TerrainType` in `world/world_map.py`, add sprite in `ui/sprite_loader.py`.

## File size policy

All source files must stay **under 500 lines** (per global coding preferences). If you're adding code that pushes a file past this limit, split it first.
