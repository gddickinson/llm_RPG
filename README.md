# LLM-RPG

A D&D-style RPG game with LLM-powered NPCs. This project demonstrates how to create a game where non-player characters are controlled by a local LLM (Language Model), making their actions and dialog more dynamic and responsive to the game state.

## Features

- Terminal-based D&D-style RPG
- NPCs powered by local LLM (Llama3 via Ollama)
- Procedural world generation
- Character memory and relationships
- Turn-based gameplay

## Requirements

- Python 3.8+
- Ollama with Llama3 model installed
  - Install from [ollama.ai](https://ollama.ai)
  - Run `ollama pull llama3` to download the model

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/llm-rpg.git
   cd llm-rpg
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make sure Ollama is running with the Llama3 model:
   ```
   ollama pull llama3
   ```

## Usage

Run the game:

```
python main.py
```

Optional arguments:
- `--model MODEL` - Use a different LLM model (default: llama3)
- `--debug` - Enable debug logging

## Game Controls

- Move: W/A/S/D or arrow keys
- Talk to NPC: T (when next to an NPC)
- View inventory: I
- View character: C
- Quit: Q

## How It Works

1. The game engine manages the game state, world, and characters
2. NPCs are controlled by sending their character data, memories, and environment to the LLM
3. The LLM generates appropriate actions and dialog based on the NPC's personality and goals
4. The game engine enacts these decisions and updates the game state

## Extending the Game

- Add new character classes and races in `characters/character_types.py`
- Create new world generation patterns in `world/world.py`
- Modify the LLM prompts in `config.py` to adjust NPC behavior

## License

MIT
