"""Quest system for LLM-RPG.

Public API:
- Quest, QuestObjective, QuestStatus, ObjectiveType
- QuestManager — tracks active/completed quests
- QUEST_TEMPLATES, create_quest()
"""

from quests.quest import Quest, QuestObjective, QuestStatus, ObjectiveType
from quests.quest_manager import QuestManager
from quests.quest_templates import QUEST_TEMPLATES, create_quest, all_quest_ids

__all__ = [
    "Quest", "QuestObjective", "QuestStatus", "ObjectiveType",
    "QuestManager",
    "QUEST_TEMPLATES", "create_quest", "all_quest_ids",
]
