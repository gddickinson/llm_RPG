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
├── data/                       # JSON content — items, recipes, spells, shops, monsters, quests, NPCs
├── llm/                        # LLM interface + providers
├── ui/                         # GUI (pygame) and terminal UI
├── saves/                      # Saved games (created at runtime)
├── tests/                      # Unit tests (290+)
```

## Module Index

### engine/ — Core game logic

- **`game_engine.py`** — `GameEngine`; orchestrates world, NPCs, player, all subsystems.
- **`demo_setup.py`** — `initialize_demo_world()`, `create_default_player(spec)`.
- **`action_router.py`** — Routes NPC actions to specialized handlers.
- **`combat_system.py`** — Player vs NPC vs NPC combat, damage, defeat, loot, faction rep on kill.
- **`economy_system.py`** — Buy/sell/trade/give between characters.
- **`dialog_system.py`** — Player↔NPC dialog flow (routes through dialog_protocol for LLM providers).
- **`dialog_protocol.py`** — Structured JSON dialog contract: whitelisted actions, engine-validated execution.
- **`npc_memory.py`** — Per-NPC memory: recency×importance×relevance retrieval, verbatim dialog log, nightly reflection → opinions.
- **`secrets.py`** — Gated NPC secrets from `data/secrets.json`; locked secrets never reach the prompt (injection-proof).
- **`persuasion.py`** — `/persuade` `/intimidate` `/deceive` social checks; LLM or dice adjudication, day-long lockouts, haggle tokens.
- **`memory_manager.py`** — Event history.
- **`save_load.py`** — JSON full-state save/load.
- **`skills.py`** — D&D-style skill checks.
- **`leveling.py`** — XP curve, auto level-up with HP/stat increases.
- **`skill_progression.py`** — 8-skill lattice from `data/skills.json`; geometric curve, `add_skill_xp()`, levels 1–50.
- **`collection_log.py`** — `CollectionLog`; unique items/kills/crafts/places vs registry totals (O-key overlay).
- **`pets.py`** — `PetSystem`; rare skilling-pet rolls from `data/pets.json`, follower trails the player.
- **`diaries.py`** — `DiaryManager`; regional task tiers from `data/diaries.json`, auto-claim rewards + shop discounts (J-key overlay).
- **`travel.py`** — `TravelSystem`; Agility terrain shortcuts + diary-unlocked teleports with toll/cooldown (U-key menu).
- **`spells.py`** — `SpellSystem`, spell registry, mana mechanics.
- **`banking.py`** — Deposit/withdraw gold at temples/shops.
- **`npc_process.py`** / **`npc_process_manager.py`** — Multiprocess NPC AI (optional).
- **`player_actions.py`** — Player-driven actions (pickup/drop/use/attack/move); weather travel penalty.
- **`game_api_mixin.py`** — `GameAPIMixin`; thin engine wrappers: party, interiors, dungeons, spells, banking, crafting, `effective_visibility()`.
- **`shop.py`** — `ShopManager`; per-merchant catalogs, faction-aware prices, persistence.
- **`effects.py`** — Effective AC / stat / damage bonuses from worn equipment (broken gear contributes 0).
- **`durability.py`** — Gear wear on uncommon+ weapons/armor; break, repair at forge, `durability_label()`.
- **`projectiles.py`** — In-flight arrows/bolts + spell projectiles with per-turn ticks.

### characters/ — Characters, NPCs, social systems

- **`character.py`** — `Character` dataclass (player + NPC).
- **`character_types.py`** — Class/race/alignment/trait/status enums.
- **`npc_manager.py`** — NPC creation + lifecycle.
- **`npc_presets.py`** — Preset NPCs loaded from `data/npcs/*.json`; `make_npc(id)`, `all_presets()`.
- **`factions.py`** — `Faction` enum, reputation tracking, on-defeat hooks.
- **`schedules.py`** — Daily routines per NPC class.
- **`needs.py`** — Hunger and fatigue simulation.
- **`status_effects.py`** — Poison / paralyzed / blessed / cursed / etc. with duration ticks.
- **`equipment.py`** — Worn weapon / armor / shield / amulet / ring / boots slots.
- **`companions.py`** — `CompanionManager`; party recruitment, follow-and-fight.
- **`families.py`** — Static family ties for preset NPCs.
- **`gossip.py`** — Gossip lines pulled from family ties + recent memory events.

### world/ — World, map, calendar, locations

- **`world.py`** — `World`; high-level world state; `get_location_at` returns innermost.
- **`world_map.py`** — `WorldMap`, `TerrainType`; tile grid, movement, FOV.
- **`location.py`** — `Location`, `LocationFactory`.
- **`biome.py`** — `Biome` enum and biome→terrain mapping.
- **`calendar.py`** — `Date`, `Season`; 12-month calendar, day-night clock, season tints.
- **`world_generator.py`** — `WorldGenerator`; procedural world. Two settlements (Oakvale + Riverside Hamlet) connected by road on 60×40+ maps.
- **`interiors.py`** — Building interior mini-maps.
- **`blueprints.py`** — Building footprint blueprints used by the world generator.
- **`chunked_world.py`** — `WorldStreamer`; off-map region transitions (chunk streaming).
- **`encounters.py`** — `EncounterManager`; wilderness monster spawns (weather-scaled chance).
- **`monsters.py`** — Monster templates from `data/monsters.json`; feeds encounters + dungeons; `build_monster()`.
- **`weather.py`** — `WeatherSystem`; rain/fog/snow/storm tied to season, with visibility multipliers.
- **`foraging.py`** — `ForageManager`; pickable herbs/berries from forest tiles with cooldown.
- **`gathering.py`** — `GatheringManager`; mining/woodcutting/fishing nodes from `data/gathering.json`, tier level gates, tool checks.
- **`dungeon.py`** — `Dungeon`, `generate_dungeon`, `populate_dungeon`; BSP-lite procedural dungeons accessible from cave tiles.
- **`history_sim.py`** — Pre-game multi-year simulation: faction shifts, ruined keep, lore lines.

### items/ — Item system + crafting

- **`item.py`** — `Item` dataclass; types, rarity, effects.
- **`data_loader.py`** — `load_data_dir()`; merges `data/<subdir>/*.json` content files (Phase 1 data layer).
- **`data_validate.py`** — `validate_all()` / `python -m items.data_validate`; cross-reference checks for all content.
- **`item_registry.py`** — thin loader over `data/items/*.json` (69 items); `create_item()`, `item_by_name()`.
- **`loot_tables.py`** — Drop tables by enemy class.
- **`crafting.py`** — `craft()` + recipes loaded from `data/recipes.json` (forge-gated, ingredients).

### quests/ — Quest system

- **`quest.py`** — `Quest`, `QuestObjective`, `QuestStatus`, `ObjectiveType`.
- **`quest_manager.py`** — Tracks quests, event hooks for progress.
- **`quest_templates.py`** — Quests loaded from `data/quests.json`; `create_quest(id)`.
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

- **`gui.py`** — `GameGUI`; pygame main window + death popup mode.
- **`start_menu.py`** — Title screen with New Game / Load / Quit; routes into the character creator.
- **`character_creator.py`** — Multi-step character creation flow + `CharacterSpec`, race/class data.
- **`renderer.py`** — `MapRenderer`; map tiles + sprites + lighting.
- **`sprite_loader.py`** — Procedural sprite generation (no PNG assets).
- **`crafting_panel.py`** — `CraftingPanel`; K-key recipe browser with have/need counts, crafts via `engine.craft()`.
- **`hints.py`** — `context_hints(engine)`; contextual key hints (talk/barter/forage/enter/…) rendered as the HUD hint bar.
- **`hud.py`** — Status, HP/XP bars, mini-map, event log, quest tracker.
- **`input_handler.py`** — Keyboard input routing (movement, dialog, quest hotkeys, death popup).
- **`terminal_ui.py`** — Text-based UI.
- **`inventory_panel.py`** — I-key equipment + bag overlay (equip/use/drop).
- **`shop_panel.py`** — B-key two-column buy/sell overlay.
- **`body_renderer.py`** — Layered character body sprites (race/class/equipment).
- **`combat_effects.py`** — Damage popups, hit flashes, death particles.
- **`lighting.py`** — Night darkness + torch/window light punches (weather-scaled).
- **`weather_overlay.py`** — Rain/snow/fog particle overlays.
- **`gui_interface.py`** — Minimal GUI-facing engine interface helpers.

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

- **New item**: add an entry to the matching `data/items/*.json` file (only non-default fields needed).
- **New recipe**: add an entry to `data/recipes.json`.
- **New quest**: add an entry to `data/quests.json`; post to a board via `default_boards()` if appropriate.
- **New named NPC**: add an entry to the matching `data/npcs/*.json` file.
- **New NPC class**: extend `CharacterClass` in `characters/character_types.py`; add schedule in `characters/schedules.py`; add to `CLASS_TO_FACTION` in `characters/factions.py`.
- **New action**: add handler in `engine/action_router.py`.
- **New terrain**: extend `TerrainType` + add sprite in `ui/sprite_loader.py`.
- **New monster**: add an entry to `data/monsters.json` (`encounter_weight` for wilderness, `"dungeon": true` for dungeons).
- **New LLM provider**: subclass `LLMProvider` in `llm/providers/`, register in `llm/providers/__init__.py`.

## File size policy

All source files stay **under 500 lines** (per global coding preferences). Split modules before exceeding.
