"""Quest templates — predefined quests that can be offered to the player."""

from typing import Dict, List

from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus


def _troll_hunt() -> Quest:
    return Quest(
        id="troll_hunt",
        title="The Troll on the East Road",
        description="A troll named Gorkash terrorizes travelers. Slay him.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.KILL,
                target="troll_brigand_01",
                required=1,
                description="Defeat Gorkash the troll brigand",
            )
        ],
        giver_id="guard_01",
        reward_gold=100,
        reward_items=["longsword"],
        reward_xp=200,
    )


def _herb_gathering() -> Quest:
    return Quest(
        id="herb_gathering",
        title="Herbs for the Apothecary",
        description="Gather healing herbs from the forest for the cleric.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.FETCH,
                target="herb_bundle",
                required=3,
                description="Collect 3 bundles of healing herbs",
            )
        ],
        giver_id="cleric_01",
        reward_gold=30,
        reward_items=["greater_potion"],
        reward_xp=80,
    )


def _tavern_introduction() -> Quest:
    return Quest(
        id="tavern_intro",
        title="A Friendly Welcome",
        description="Goren the tavern keeper wants to greet a newcomer.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.TALK,
                target="tavernkeeper_01",
                required=1,
                description="Speak with Goren in the tavern",
            )
        ],
        giver_id="",
        reward_gold=10,
        reward_items=["ale"],
        reward_xp=15,
    )


def _explore_caves() -> Quest:
    return Quest(
        id="cave_exploration",
        title="The Dark Cave",
        description="Investigate the mysterious cave in the mountains.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.EXPLORE,
                target="Dark Cave",
                required=1,
                description="Enter the Dark Cave",
            )
        ],
        giver_id="minstrel_01",
        reward_gold=50,
        reward_items=["old_map"],
        reward_xp=120,
    )


def _deliver_sword() -> Quest:
    return Quest(
        id="deliver_sword",
        title="A Forged Blade",
        description="Bring a sword from the smith to the guard.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.DELIVER,
                target="sword:guard_01",
                required=1,
                description="Deliver a sword to Karim the guard",
            )
        ],
        giver_id="blacksmith_01",
        reward_gold=40,
        reward_items=["shield"],
        reward_xp=50,
    )


def _survive_night() -> Quest:
    return Quest(
        id="survive_night",
        title="Through the Night",
        description="Survive until dawn while monsters roam.",
        objectives=[
            QuestObjective(
                obj_type=ObjectiveType.SURVIVE,
                target="dawn",
                required=50,
                description="Survive 50 turns",
            )
        ],
        giver_id="",
        reward_gold=80,
        reward_items=["potion", "potion"],
        reward_xp=150,
    )


# Registry of quest factory callables keyed by quest id
QUEST_TEMPLATES = {
    "troll_hunt": _troll_hunt,
    "herb_gathering": _herb_gathering,
    "tavern_intro": _tavern_introduction,
    "cave_exploration": _explore_caves,
    "deliver_sword": _deliver_sword,
    "survive_night": _survive_night,
}


def create_quest(quest_id: str) -> Quest:
    """Build a fresh quest instance from the template registry."""
    if quest_id not in QUEST_TEMPLATES:
        raise KeyError(f"Unknown quest id: {quest_id}")
    quest = QUEST_TEMPLATES[quest_id]()
    quest.status = QuestStatus.AVAILABLE
    return quest


def all_quest_ids() -> List[str]:
    return list(QUEST_TEMPLATES.keys())
