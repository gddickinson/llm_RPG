"""Quest templates — loaded from `data/quests.json`.

Adding a quest = adding a JSON entry with title, description, objectives
(type/target/required), giver_id, and rewards. `QUEST_TEMPLATES` keeps its
historical shape (id → zero-arg factory) so existing callers are unchanged.
"""

from typing import Callable, Dict, List

from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus


def _quest_from_entry(quest_id: str, entry: dict) -> Quest:
    return Quest(
        id=quest_id,
        title=entry["title"],
        description=entry.get("description", ""),
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType(o["type"]),
                target=o["target"],
                required=o.get("required", 1),
                description=o.get("description", ""),
            )
            for o in entry.get("objectives", [])
        ],
        giver_id=entry.get("giver_id", ""),
        reward_gold=entry.get("reward_gold", 0),
        reward_items=list(entry.get("reward_items", [])),
        reward_xp=entry.get("reward_xp", 0),
        metadata={
            key: entry[key]
            for key in ("prereq_quest", "reward_unlocks",
                        "quest_points", "requires_bond",
                        # branching (P21.1)
                        "excludes", "excluded_by", "sets_flag",
                        "prereq_flag", "blocked_by_flag", "reward_choices",
                        # the main arc (P21.2)
                        "main", "main_finale",
                        # set-pieces (P21.4)
                        "time_limit")
            if key in entry
        },
    )


def _build_templates() -> Dict[str, Callable[[], Quest]]:
    from items.data_loader import load_data_file
    raw = load_data_file("quests.json")

    def make_factory(qid: str, entry: dict) -> Callable[[], Quest]:
        return lambda: _quest_from_entry(qid, entry)

    return {qid: make_factory(qid, entry) for qid, entry in raw.items()}


# Registry of quest factory callables keyed by quest id
QUEST_TEMPLATES: Dict[str, Callable[[], Quest]] = _build_templates()


def create_quest(quest_id: str) -> Quest:
    """Build a fresh quest instance from the template registry."""
    if quest_id not in QUEST_TEMPLATES:
        raise KeyError(f"Unknown quest id: {quest_id}")
    quest = QUEST_TEMPLATES[quest_id]()
    quest.status = QuestStatus.AVAILABLE
    return quest


def all_quest_ids() -> List[str]:
    return list(QUEST_TEMPLATES.keys())
