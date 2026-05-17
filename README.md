# LLM-RPG

A locally-runnable, D&D-style RPG with optional LLM-powered NPCs.
The default mode requires **no LLM at all** — a heuristic NPC engine
keeps the world alive — but you can plug in Ollama, Anthropic Claude,
or OpenAI for richer character behavior.

## Highlights

- **Local-first**: Single-process Pygame game; runs on any modern Mac/Linux/Windows.
- **No mandatory LLM**: Heuristic provider gives NPCs personality, combat
  behavior, and dialog patterns out of the box.
- **Pluggable LLM**: One flag to switch between heuristic / Ollama / Anthropic / OpenAI.
- **Real items**: Weapons, armor, potions, quest items — with stats, rarity, value.
- **Quest system**: Kill / fetch / talk / explore / deliver / survive objectives.
- **Save / load**: One-key F5/F9 JSON saves.
- **Procedural worldgen**: Forest borders, river, mountains, village with shops.
- **Sprite-based renderer**: All sprites generated procedurally — no asset files.
- **D&D skill checks**: 18 skills with ability modifiers, advantage / disadvantage.
- **NPC processes**: Optional multiprocess NPC AI for parallel LLM calls.

## Quick Start

```bash
pip install -r requirements.txt
python main.py                                  # Pygame GUI, heuristic AI
python main.py --ui terminal                    # Terminal mode
python main.py --provider ollama --model llama3 # Ollama backend
python main.py --provider anthropic \
       --model claude-haiku-4-5-20251001        # Anthropic Claude
python main.py --load                           # Resume quicksave
python main.py --no-quests --no-npc-processes   # Minimal mode
```

For LLM modes, install the matching SDK:
```bash
pip install anthropic        # for --provider anthropic
pip install openai           # for --provider openai
# Ollama: see https://ollama.ai/
```

## Controls (GUI)

| Key                    | Action                          |
|------------------------|---------------------------------|
| WASD / Arrows          | Move                            |
| SPACE / F              | Attack adjacent enemy           |
| T                      | Talk to adjacent NPC            |
| G / E                  | Pick up item                    |
| H                      | Drink potion                    |
| I                      | Inventory overlay               |
| Q                      | Quest log                       |
| C                      | Character sheet                 |
| F5 / F9                | Save / Load                     |
| F1 / `/`               | Help                            |
| ESC                    | Close menu / quit               |

In dialog mode: type your message, Enter to send, Esc to leave.

## Project Layout

See [`INTERFACE.md`](INTERFACE.md) for the full navigation map.

```
llm_RPG/
├── main.py                 # Entry point
├── config.py
├── INTERFACE.md            # Project map (READ FIRST)
├── SESSION_LOG.md          # Development history
├── README.md / ROADMAP.md
├── engine/                 # Core game logic
│   ├── game_engine.py      # Orchestrator (363 LOC)
│   ├── combat_system.py
│   ├── economy_system.py
│   ├── dialog_system.py
│   ├── action_router.py
│   ├── player_actions.py
│   ├── save_load.py        # JSON persistence
│   ├── skills.py           # D&D skill checks
│   ├── memory_manager.py
│   └── npc_process*.py     # Multiprocess NPC AI (optional)
├── characters/             # Character + NPC system
├── world/                  # World, map, biomes, procedural gen
├── items/                  # Item system (NEW)
├── quests/                 # Quest system (NEW)
├── llm/                    # LLM facade + providers
│   ├── llm_interface.py
│   └── providers/
│       ├── base.py
│       ├── heuristic.py    # default (no LLM)
│       ├── ollama.py
│       ├── anthropic.py
│       └── openai_provider.py
├── ui/                     # Pygame + terminal UIs
│   ├── gui.py              # Thin orchestrator (237 LOC)
│   ├── renderer.py         # Map rendering
│   ├── sprite_loader.py    # Procedural sprites
│   ├── hud.py              # Status panels, minimap, log
│   ├── input_handler.py    # Input routing
│   └── terminal_ui.py
├── tests/                  # 44+ unit tests
└── saves/                  # Created at runtime
```

## Game Systems

### Combat
- Player vs NPC vs NPC, weapon damage + armor reduction.
- Stat-vs-stat hit chance, randomized damage.
- Defeated characters drop class-appropriate loot via `items/loot_tables.py`.
- Player kills grant XP (tracked in `player.metadata["xp"]`).

### Items
- Real `Item` class — weapons, armor, shields, consumables, quest items.
- Effects: damage, armor, heal_amount, value, rarity.
- 35+ predefined items in `items/item_registry.py`. Add more there.

### Quests
- 6 starter quests (kill troll, fetch herbs, deliver sword, explore cave, ...).
- Event hooks wire automatically to engine actions:
  defeating an NPC, picking up an item, talking to someone,
  entering a location, surviving turns, delivering items.

### NPC AI
- **Heuristic mode**: rule-based behavior keyed on class + visible state.
  Brigands attack on sight, merchants greet customers, guards patrol.
- **LLM mode**: NPCs run in their own processes, decide actions every
  N turns based on full character context, visible map, history, memories.

### World
- 30x20 default; procedural generation with forest/river/mountain/village.
- Day-night cycle visible as color overlay.
- Revival shrines that bring back defeated NPCs.

### Saves
- JSON, one file per slot. `saves/quicksave.json` by default.
- Captures world, player, all NPCs, ground items, quests, history.

## Running Tests

```bash
python -m unittest discover tests/
```

44 tests cover items, quests, save/load, combat, world gen, skills, engine.

## Configuration

Edit `config.py` to tune:
- `DEFAULT_PROVIDER`: heuristic | ollama | anthropic | openai
- `DEFAULT_MODEL`: model name for the chosen provider
- `DEFAULT_MAP_WIDTH` / `_HEIGHT`
- `NPC_ACTION_INTERVAL`: turns between NPC LLM calls
- `MAX_HISTORY_ITEMS`: event log retention

## Adding Content

Quick recipes (see INTERFACE.md for details):
- **New item**: append to `items/item_registry.py`.
- **New quest**: add template in `quests/quest_templates.py`.
- **New NPC class**: extend `CharacterClass` enum.
- **New action**: add handler in `engine/action_router.py`.
- **New terrain**: extend `TerrainType` + add sprite in `ui/sprite_loader.py`.

## Requirements

- Python 3.8+
- pygame (or pygame-ce) — for GUI mode
- requests — for Ollama
- (optional) anthropic, openai — for cloud providers

## License

MIT
