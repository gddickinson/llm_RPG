# LLM-RPG

A sophisticated D&D-style roleplaying game powered by local Large Language Models, featuring dynamic NPCs that make independent decisions, engage in combat, trade items, and interact with the game world.

![LLM-RPG Game](https://via.placeholder.com/800x400?text=LLM-RPG+Game)

## Overview

LLM-RPG creates an immersive fantasy world where non-player characters (NPCs) are controlled by local LLMs. Each NPC has its own personality, goals, memories, and can make decisions based on its character sheet and current game state. The game runs entirely on your local machine, using Ollama to interact with models like Llama 3.

### Key Features

- **LLM-Powered NPCs**: Each NPC runs in its own process with a dedicated LLM, allowing for parallel, non-blocking decision making
- **Dynamic World**: NPCs move around, interact with each other, engage in combat, and trade items
- **Memory System**: Characters remember past events and interactions, influencing future decisions
- **Combat System**: Turn-based combat with stats-based outcomes, health tracking, and defeat mechanics
- **Economy**: NPCs can buy, sell, and trade items with each other and the player
- **Revival System**: Defeated characters can be revived at special shrines in the game world
- **Multiprocess Architecture**: Responsive gameplay even with multiple NPCs active at once
- **Graphical Interface**: Easy-to-use UI with map visualization, character stats, and inventory management

## Requirements

- Python 3.8 or higher
- Ollama with Llama 3 model installed
- M1/M2 Mac, Windows, or Linux machine (32GB RAM recommended for best performance)
- Required Python packages (see requirements.txt)

## Installation

1. **Clone the repository**:
   ```
   git clone https://github.com/yourusername/llm-rpg.git
   cd llm-rpg
   ```

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Download and start Ollama**:
   - Install from [ollama.ai](https://ollama.ai)
   - Pull the Llama 3 model:
     ```
     ollama pull llama3
     ```

## Usage

### Starting the Game

Run the game with the graphical interface (recommended):
```
python main.py --ui gui
```

Or use the terminal interface:
```
python main.py --ui terminal
```

### Command Line Options

- `--model MODEL`: Specify which LLM model to use (default: llama3)
- `--ui [gui|terminal]`: Choose the user interface (default: gui if available)
- `--width WIDTH`: Set window width for the GUI (default: 1200)
- `--height HEIGHT`: Set window height for the GUI (default: 800)
- `--debug`: Enable debug logging

## Game Controls

### GUI Mode

- **Movement**: WASD or arrow keys
- **Combat**:
  - SPACE: Attack nearest hostile character
  - F: Attack any character (with selection for multiple targets)
- **Interaction**:
  - T: Talk to nearby NPC
  - E: Examine/Interact with objects
  - I: Open inventory
  - C: View character sheet
  - M: View map
  - ESC: Settings/Cancel dialog

### Terminal Mode

- **Movement**: WASD or arrow keys
- **Interaction**:
  - T: Talk to NPC
  - I: Show inventory
  - C: Show character
  - M: Show map
  - L: Look around
  - H: Show help
  - Q: Quit game

## Project Architecture

### Modular Design

The project uses a modular architecture for easy maintenance and extension:

```
llm_rpg/
├── main.py                   # Main entry point
├── config.py                 # Configuration settings
├── engine/                   # Core game engine
│   ├── game_engine.py        # Main game logic
│   ├── memory_manager.py     # Game history tracking
│   ├── npc_process.py        # NPC process module
│   └── npc_process_manager.py # Multi-process management
├── world/                    # World representation
│   ├── world.py              # World management
│   ├── world_map.py          # Map and movement
│   └── location.py           # Location definitions
├── characters/               # Character system
│   ├── character.py          # Character class
│   ├── character_types.py    # Character enums
│   └── npc_manager.py        # NPC management
├── llm/                      # LLM integration
│   ├── llm_interface.py      # Basic LLM interface
│   └── threaded_llm_interface.py # Threaded LLM interface
└── ui/                       # User interfaces
    ├── gui.py                # Graphical interface
    ├── gui_interface.py      # GUI launcher
    └── terminal_ui.py        # Terminal interface
```

### Multi-Process Architecture

LLM-RPG uses a multi-process architecture to ensure responsive gameplay:

1. **Main Process**: Handles game state, player input, and UI rendering
2. **NPC Processes**: Each NPC runs in its own separate process with:
   - Dedicated LLM instance
   - Command/response queues for communication
   - Independent decision making

This approach allows NPCs to "think" in parallel without blocking the main game loop, resulting in a more responsive experience.

## NPC System

### Character Components

Each character (including NPCs) has:

- **Basic Attributes**: Name, class, race, level, stats (STR, DEX, CON, INT, WIS, CHA)
- **Status**: HP, max HP, status (alive, defeated, dead)
- **Inventory**: Items, gold
- **Personality**: Traits, likes, dislikes
- **Relationships**: How they feel about other characters
- **Goals**: What they're trying to accomplish
- **Memories**: Important events they remember

### NPC Decision Making

NPCs make decisions based on:

1. Their character sheet and personality
2. Current game state and visible environment
3. Recent game history
4. Their memories of past events
5. Their goals and motivations

The LLM generates structured actions including:
- Movement (where to go)
- Combat (who to attack)
- Dialog (what to say)
- Economic actions (buying/selling)
- World interactions (using items, searching)

## Combat System

The combat system includes:

- **Attack Logic**: Based on character stats and weapon types
- **Damage Calculation**: Influenced by strength, dexterity, and other factors
- **Health Tracking**: Characters have HP that decreases when damaged
- **Defeat Mechanics**: Characters at 0 HP are defeated and removed from play
- **Relationships**: Combat affects how characters feel about each other

## Revival System

The game includes a revival system:

1. **Revival Shrines**: Special locations on the map
2. **Body Items**: Defeated characters leave behind body items
3. **Resurrection Mechanics**: Bodies near shrines can be revived after time
4. **Health Recovery**: Revived characters return with partial health

## Extending the Game

### Adding New NPCs

1. Create a new NPC in `npc_manager.py`:
   ```python
   def create_custom_npc(self, position=(x, y)):
       npc = Character(
           id="custom_npc_01",
           name="CustomName",
           character_class=CharacterClass.CHOSEN_CLASS,
           race=CharacterRace.CHOSEN_RACE,
           # Other attributes...
       )
       self.add_npc(npc)
       return npc
   ```

2. Call this method when initializing the world.

### Adding New Locations

1. Modify `world.py` to add new locations:
   ```python
   # In create_simple_world method
   self.map.add_terrain_feature(TerrainType.CHOSEN_TYPE, x, y, width, height)
   self.add_location(Location("Location Name", "Description", x, y, width, height))
   ```

### Creating New Character Classes/Races

1. Add new options to the enums in `character_types.py`:
   ```python
   class CharacterClass(Enum):
       # Existing classes...
       NEW_CLASS = "new_class"

   class CharacterRace(Enum):
       # Existing races...
       NEW_RACE = "new_race"
   ```

## Performance Considerations

- **Memory Usage**: Each NPC process uses memory for its LLM instance
- **CPU Usage**: Multiple LLM instances will use significant CPU resources
- **Process Suspension**: Inactive NPCs have their processes suspended to save resources
- **Distance-Based Processing**: Only NPCs near the player are actively processed

## Troubleshooting

### Common Issues

1. **Game Freezes**:
   - Check if Ollama is running
   - Reduce the number of active NPCs
   - Increase `NPC_ACTION_INTERVAL` in config.py

2. **NPCs Not Moving**:
   - Verify LLM is generating valid actions
   - Check debug logs for movement failures

3. **Memory Usage Too High**:
   - Reduce `NUM_LLM_THREADS` in config.py
   - Use a smaller LLM model

## License

MIT License

## Acknowledgments

- This project uses Ollama for local LLM integration
- Pygame and pygame_gui for the graphical interface
- The multiprocessing library for parallel NPC processing

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
