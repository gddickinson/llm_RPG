"""Quest, QuestObjective, and related types."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ObjectiveType(Enum):
    KILL = "kill"            # Defeat N of target NPC/class
    FETCH = "fetch"          # Acquire N of an item
    TALK = "talk"            # Talk to NPC
    EXPLORE = "explore"      # Reach a location
    DELIVER = "deliver"      # Bring item to NPC
    SURVIVE = "survive"      # Survive N turns/days


class QuestStatus(Enum):
    AVAILABLE = "available"      # Offered, not yet accepted
    ACTIVE = "active"            # Player is working on it
    COMPLETED = "completed"      # Objectives met, can turn in
    TURNED_IN = "turned_in"      # Player got the reward
    FAILED = "failed"


@dataclass
class QuestObjective:
    """A single objective inside a quest."""
    obj_type: ObjectiveType
    target: str             # NPC id, item id, location name, ...
    required: int = 1
    progress: int = 0
    description: str = ""

    def is_complete(self) -> bool:
        return self.progress >= self.required

    def increment(self, amount: int = 1) -> bool:
        """Return True if newly completed this call."""
        was_complete = self.is_complete()
        self.progress = min(self.required, self.progress + amount)
        return self.is_complete() and not was_complete

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obj_type": self.obj_type.value,
            "target": self.target,
            "required": self.required,
            "progress": self.progress,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QuestObjective":
        return cls(
            obj_type=ObjectiveType(d["obj_type"]),
            target=d["target"],
            required=d.get("required", 1),
            progress=d.get("progress", 0),
            description=d.get("description", ""),
        )

    def __str__(self) -> str:
        return f"{self.description} ({self.progress}/{self.required})"


@dataclass
class Quest:
    """A quest the player can undertake.

    Attributes
    ----------
    id : str
        Stable id used for save/load and templates.
    title : str
    description : str
    objectives : list of QuestObjective
        ALL must be complete for the quest to be COMPLETED.
    status : QuestStatus
    giver_id : str
        NPC id of the quest giver (for turn-in).
    reward_gold : int
    reward_items : list of item ids
    reward_xp : int
    """
    id: str
    title: str
    description: str
    objectives: List[QuestObjective] = field(default_factory=list)
    status: QuestStatus = QuestStatus.AVAILABLE
    giver_id: str = ""
    reward_gold: int = 0
    reward_items: List[str] = field(default_factory=list)
    reward_xp: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_complete(self) -> bool:
        return all(o.is_complete() for o in self.objectives)

    def update_status(self) -> None:
        if self.status == QuestStatus.ACTIVE and self.is_complete():
            self.status = QuestStatus.COMPLETED

    def progress_summary(self) -> str:
        lines = [f"{self.title}: {self.description}"]
        for obj in self.objectives:
            mark = "[X]" if obj.is_complete() else "[ ]"
            lines.append(f"  {mark} {obj}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "objectives": [o.to_dict() for o in self.objectives],
            "status": self.status.value,
            "giver_id": self.giver_id,
            "reward_gold": self.reward_gold,
            "reward_items": self.reward_items,
            "reward_xp": self.reward_xp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Quest":
        return cls(
            id=d["id"],
            title=d["title"],
            description=d["description"],
            objectives=[QuestObjective.from_dict(o) for o in d.get("objectives", [])],
            status=QuestStatus(d.get("status", "available")),
            giver_id=d.get("giver_id", ""),
            reward_gold=d.get("reward_gold", 0),
            reward_items=d.get("reward_items", []),
            reward_xp=d.get("reward_xp", 0),
            metadata=d.get("metadata", {}),
        )
