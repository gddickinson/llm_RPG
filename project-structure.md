# LLM-RPG Project Structure

This document outlines the file structure and organization of the LLM-RPG project.

```
llm_rpg/
├── main.py                   # Main entry point for the game
├── config.py                 # Configuration settings
├── requirements.txt          # Project dependencies
├── README.md                 # Project documentation
├── engine/
│   ├── __init__.py
│   ├── game_engine.py        # Core game engine
│   └── memory_manager.py     # Game history and memory management
├── world/
│   ├── __init__.py
│   ├── world.py              # World management
│   ├── world_map.py          # Map representation and functions
│   └── location.py           # Location class and features
├── characters/
│   ├── __init__.py
│   ├── character.py          # Base Character class
│   ├── character_types.py    # Character enums and types
│   └── npc_manager.py        # NPC management
├── llm/
│   ├── __init__.py
│   └── llm_interface.py      # Interface to Ollama/LLM
└── ui/
    ├── __init__.py
    └── terminal_ui.py        # Simple terminal-based UI
```

## Module Descriptions

- **main.py**: Entry point that initializes all components and runs the game loop
- **config.py**: Centralized configuration for the game engine
- **engine/**: Core game engine and state management
- **world/**: World representation, maps, and location management
- **characters/**: Character classes, NPCs, and related functionality
- **llm/**: Interface to LLM for NPC decision making
- **ui/**: User interface modules (starting with simple terminal UI)
