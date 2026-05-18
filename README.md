# LLM-RPG

A locally-runnable, D&D-style RPG with optional LLM-powered NPCs.
The default mode requires **no LLM at all** — a heuristic NPC engine
keeps the world alive — but you can plug in Ollama, Anthropic Claude,
or OpenAI for richer character behavior.

## Highlights

- **Local-first**: Single-process Pygame game; runs on any modern Mac/Linux/Windows.
- **Start menu + character creator**: Title screen with New Game / Load / Quit. Quick Start or full multi-step Customize (name → race → class → 4d6 stats → confirm).
- **No mandatory LLM**: Heuristic provider gives NPCs personality, daily routines, schedules, combat behavior, and branching dialog out of the box.
- **Pluggable LLM**: One flag to switch between heuristic / Ollama / Anthropic / OpenAI.
- **Bigger world** (60×40): two settlements (Oakvale Village + Riverside Hamlet) connected by a road.
- **Procedural dungeons**: step onto a cave tile and descend into BSP-generated tunnels with rooms, monsters, loot.
- **Weather**: clear / cloudy / rain / fog / snow / storm; biased by season; reduces visibility.
- **Foraging**: pick herbs and berries from forest/grass tiles with regen cooldown.
- **Living world**: NPC daily schedules + needs (hunger, fatigue), seasons, calendar, day/night cycle.
- **Spells + mana**: Wizard / cleric / sorcerer / druid spells with mana pool, range, and status effects.
- **Status effects**: Poison ticks damage; paralyzed skips turns; blessed/cursed shift damage.
- **Equipment slots**: Worn weapon / armor / shield / amulet / ring / boots, separate from the inventory bag.
- **Real items + crafting**: Weapons, armor, potions, quest items; recipes for ingredients.
- **Quests**: 6 quest types. Accept from NPC dialog or the tavern's quest board.
- **Factions**: 8 factions with reputation tracking.
- **Companions**: Recruit followers who fight alongside you.
- **Building interiors**: Walk into the tavern, forge, shop, or temple.
- **Random encounters**: Wilderness monster spawns.
- **Banking**: Deposit gold safely at temple or shop.
- **Save / load**: One-key F5/F9 JSON saves.
- **Death popup**: When the player dies, a popup offers Restart or Quit.
- **Procedural worldgen + sprite renderer**: No PNG asset files needed.
- **D&D skill checks + leveling**: 18 skills, XP curve with class-favored stat gains.

## Quick Start

```bash
pip install -r requirements.txt
python main.py                                  # Pygame GUI, heuristic AI
python main.py --ui terminal                    # Terminal mode
python main.py --provider ollama --model llama3 # Ollama backend
python main.py --provider anthropic \
       --model claude-haiku-4-5-20251001        # Anthropic Claude
python main.py --load                           # Resume quicksave
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
| 1–9 (in dialog)        | Accept / turn in offered quests |
| G / E                  | Pick up item                    |
| H                      | Drink potion                    |
| I                      | Inventory overlay               |
| Q                      | Quest log                       |
| C                      | Character sheet                 |
| F5 / F9                | Save / Load                     |
| F1 / `/`               | Help                            |
| ESC                    | Close menu / quit               |

In dialog mode: type your message, Enter to send, Esc to leave.

## Game Systems

### NPCs — daily schedules + needs

Peaceful NPCs follow class-specific daily routines: villagers and merchants work during the day, eat at the tavern at meals, drink in the evening, sleep at night. Bards play music in the tavern; clerics pray at the temple. NPCs accumulate hunger and fatigue as time passes; starving or exhausted NPCs break from their schedule to find food or rest.

Hostile NPCs (brigands, trolls, monsters) hunt the player on sight.

### Combat

- Player vs NPC vs NPC; stat-vs-stat hit chance with weapon damage / armor reduction.
- Defeated characters drop class-keyed loot via `items/loot_tables.py`.
- Player kills grant XP and shift faction reputation.

### Factions + reputation

Eight factions: villagers, guards, merchants, brigands, monsters, temple, bardic, neutral. Killing a brigand pleases villagers, guards, and temple — and hardens the brigand-rep further. Attacking a villager turns the town hostile.

Reputation labels: revered ▶ honored ▶ friendly ▶ warming ▶ neutral ▶ wary ▶ hostile ▶ hated.

### Quests

Quests start AVAILABLE — discover them through NPC dialog (accept with 1-9) or the **quest board** at the tavern. Turn in completed quests at the giver for gold, items, and XP.

Objective types: KILL, FETCH, TALK, EXPLORE, DELIVER, SURVIVE.

### Items + crafting

- 35+ predefined items with type, rarity, value, effects.
- Recipes turn ingredients into output items (`items/crafting.py`).
- Some recipes are forge-gated — visit Durgan's Forge to craft weapons.

### Banking

Visit the Temple of Light or General Store to deposit/withdraw gold. Balance is stored in `player.metadata["bank"]`.

### Companions

Recruit certain NPC classes (warrior, bard, cleric, wizard, ranger, paladin) once you've built up enough relationship (≥30). Up to 3 party members. They follow you and fight adjacent hostiles automatically.

### Building interiors

Step on a tavern / forge / shop / temple tile and press E (or the interact button) to enter the indoor mini-map. Each interior has furniture and NPC spots. Step on the door tile to leave.

### Random encounters

When you wander far from town through grass or forest tiles, monsters (wolves, bandits, goblins, wandering trolls) may spawn nearby. Cooldown between encounters keeps them from being constant.

### Calendar + seasons

12 months × 30 days = 360-day year. Four seasons (spring/summer/autumn/winter) each tint the world's colors. The current date is shown in the HUD.

### Skills + leveling

- D&D-style skill checks: 1d20 + ability modifier (+ proficiency) vs DC, with advantage/disadvantage.
- XP curve: cumulative `50 * N * (N-1)` per level.
- On level-up: +5 max HP, full heal, +1 to two class-favored stats (e.g. Warrior STR+CON, Wizard INT+WIS).

### Save / load

One-key save (F5) and load (F9). Captures world, time, all NPCs, ground items, quests, player progress.

## Project Layout

See [`INTERFACE.md`](INTERFACE.md) for the full navigation map.

## Running Tests

```bash
python -m unittest discover tests/
```

107 tests cover items, quests, save/load, combat, world gen, skills, leveling, factions, calendar, schedules, needs, encounters, banking, crafting, interiors, quest boards, companions, dialog trees, engine.

## Configuration

Edit `config.py` to tune:
- `DEFAULT_PROVIDER`: heuristic | ollama | anthropic | openai
- `DEFAULT_MODEL`: model name for the chosen provider
- `DEFAULT_MAP_WIDTH` / `_HEIGHT`
- `NPC_ACTION_INTERVAL`: turns between NPC actions
- `MAX_HISTORY_ITEMS`: event log retention

## Adding Content

Quick recipes (see INTERFACE.md for details):
- **New item**: append to `items/item_registry.py`.
- **New recipe**: append to `items/crafting.py` `RECIPES` dict.
- **New quest**: add template in `quests/quest_templates.py`; post to a board in `quests/quest_board.py`.
- **New NPC class**: extend `CharacterClass`; add schedule in `characters/schedules.py`; add to `CLASS_TO_FACTION`.
- **New dialog tree**: add factory in `engine/dialog_trees.py`.
- **New encounter monster**: add entry in `world/encounters.py`.
- **New LLM provider**: subclass `LLMProvider` in `llm/providers/`.

## Requirements

- Python 3.8+
- pygame (or pygame-ce) — for GUI mode
- requests — for Ollama
- (optional) anthropic, openai — for cloud providers

## License

MIT
