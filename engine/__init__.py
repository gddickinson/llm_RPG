"""Engine package for LLM-RPG.

Public API:
- GameEngine: core orchestrator
- MemoryManager: timestamped event history
- CombatSystem, EconomySystem, DialogSystem, ActionRouter, PlayerActions
- SaveManager: JSON persistence
- Skill, Difficulty, roll_check
"""

from engine.game_engine import GameEngine
from engine.memory_manager import MemoryManager
from engine.combat_system import CombatSystem
from engine.economy_system import EconomySystem
from engine.dialog_system import DialogSystem
from engine.action_router import ActionRouter
from engine.player_actions import PlayerActions
from engine.save_load import SaveManager
from engine.skills import Skill, Difficulty, roll_check, opposed_check

__all__ = [
    "GameEngine",
    "MemoryManager",
    "CombatSystem", "EconomySystem", "DialogSystem",
    "ActionRouter", "PlayerActions",
    "SaveManager",
    "Skill", "Difficulty", "roll_check", "opposed_check",
]
