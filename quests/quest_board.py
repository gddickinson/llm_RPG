"""Quest board — a posting at the tavern that lists available quests.

The board is a logical entity tied to a location. When the player is at
that location, they can browse and accept all currently-AVAILABLE quests
that haven't been assigned a specific NPC giver.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from quests.quest import Quest, QuestStatus

logger = logging.getLogger("llm_rpg.quest_board")


@dataclass
class QuestBoard:
    """A bulletin board listing quests offered to the player."""
    location_name: str
    posted_quest_ids: List[str] = field(default_factory=list)
    description: str = "A wooden board covered in notices and requests."


def default_boards() -> List[QuestBoard]:
    """Boards that are spawned at world creation time."""
    return [
        QuestBoard(
            location_name="Oakvale Tavern",
            posted_quest_ids=[
                "tavern_intro", "herb_gathering", "cave_exploration",
                "deliver_sword", "survive_night",
            ],
            description="The tavern's adventurer board. Notices flutter in the breeze.",
        ),
    ]


class QuestBoardManager:
    """Tracks quest boards and exposes browsing/acceptance API."""

    def __init__(self, engine):
        self.engine = engine
        self.boards: List[QuestBoard] = default_boards()

    def board_at(self, location_name: str) -> Optional[QuestBoard]:
        for b in self.boards:
            if b.location_name == location_name:
                return b
        return None

    def board_at_player(self) -> Optional[QuestBoard]:
        # Interior-aware (PT3.1 finding: solid walls made the tavern
        # board unreachable — the board hangs INSIDE the tavern now)
        try:
            loc = self.engine.player_location()
        except Exception:
            loc = self.engine.world.get_location_at(
                *self.engine.player.position)
        if not loc:
            return None
        return self.board_at(loc.name)

    def list_available(self, board: QuestBoard) -> List[Quest]:
        """Return quests on this board still in AVAILABLE state."""
        if not self.engine.quest_manager:
            return []
        out = []
        for qid in board.posted_quest_ids:
            q = self.engine.quest_manager.get(qid)
            if q and q.status == QuestStatus.AVAILABLE and \
                    self.engine.quest_manager.is_unlocked(q):
                out.append(q)
        return out

    def accept_from_board(self, quest_id: str) -> bool:
        """Accept a quest currently posted on a nearby board."""
        board = self.board_at_player()
        if not board:
            return False
        if quest_id not in board.posted_quest_ids:
            return False
        return self.engine.accept_quest(quest_id)

    # ---- persistence (P0.1b) -------------------------------------------

    def to_dict(self) -> dict:
        """Each board's LIVE postings — radiant notices and DM quests get
        added/removed at runtime, so the defaults alone don't round-trip."""
        return {"boards": {b.location_name: list(b.posted_quest_ids)
                           for b in self.boards}}

    def from_dict(self, data: dict) -> None:
        saved = data.get("boards", {})
        known = {b.location_name for b in self.boards}
        for b in self.boards:
            if b.location_name in saved:
                b.posted_quest_ids = list(saved[b.location_name])
        # a board that existed only in the save (a DM-raised board) — keep it
        for loc, ids in saved.items():
            if loc not in known:
                self.boards.append(
                    QuestBoard(location_name=loc,
                               posted_quest_ids=list(ids)))
