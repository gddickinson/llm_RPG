"""
Configuration settings for LLM-RPG
"""

# LLM Settings
LLM_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000

# Game Settings
DEFAULT_MAP_WIDTH = 30
DEFAULT_MAP_HEIGHT = 20
DEFAULT_VISIBILITY_RANGE = 5
MAX_HISTORY_ITEMS = 100
NPC_ACTION_INTERVAL = 5  # How many player turns before NPCs act
GAME_TICK_INTERVAL = 0.1  # Seconds between game ticks

# UI Settings
ENABLE_COLORS = True
MAP_SYMBOLS = {
    "player": "@",
    "npc": "N",
    "grass": ".",
    "forest": "T",
    "mountain": "^",
    "water": "~",
    "road": "=",
    "building": "#",
    "cave": "C"
}

# System Prompts
NPC_ACTION_SYSTEM_PROMPT = """You are roleplaying as an NPC in a D&D-style game.
Based on your character sheet, memories, and current situation, decide what action to take next.
Respond using the following format ONLY:

ACTION: [move/talk/use_item/attack/wait/etc]
TARGET: [target of the action]
DIALOG: [Any dialog the character says]
THOUGHTS: [Internal thoughts, not spoken]
EMOTION: [Current emotional state]
GOAL_UPDATE: [Any updates to current goals]

Be authentic to your character's personality and motivations."""

# Multiprocessing settings
NPC_PROCESS_ENABLED = True
NPC_PROCESS_TIMEOUT = 5.0  # Seconds to wait for NPC response before fallback
NPC_DIALOG_TIMEOUT = 5.0  # Seconds to wait for dialog response
NPC_MAX_PROCESSES = 8  # Maximum number of NPC processes to run concurrently
