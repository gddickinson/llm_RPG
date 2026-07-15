"""The Adventurers' Guild — quest points as a meta-currency (P4.3).

Every authored quest grants quest points (1-3, in its data entry;
radiant quests grant none). QP totals unlock guild ranks with concrete
perks — the OSRS pattern where even small quests feed a larger unlock:

  5 QP  Member    — the tavern board carries 2 extra notices
 10 QP  Veteran   — travel focus recovers in half the time
 15 QP  Champion  — a fourth companion may join your party

23 QP exist across the 13 authored quests, so Champion demands most of
the questbook. QP lives in `player.metadata["quest_points"]`.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.guild")

RANKS: Tuple[Tuple[int, str], ...] = (
    (15, "Champion"),
    (10, "Veteran"),
    (5, "Member"),
)


class GuildSystem:
    def __init__(self, engine):
        self.engine = engine

    # ---- quest points -----------------------------------------------------

    def quest_points(self) -> int:
        return int(self.engine.player.metadata.get("quest_points", 0))

    def award_points(self, points: int) -> List[str]:
        """Add QP; returns announcements (incl. rank-ups)."""
        if points <= 0:
            return []
        rank_before = self.rank()
        meta = self.engine.player.metadata
        meta["quest_points"] = self.quest_points() + points
        notes = [f"+{points} quest point{'s' if points > 1 else ''} "
                 f"({self.quest_points()} total)"]
        rank_after = self.rank()
        if rank_after != rank_before:
            notes.append(
                f"*** The Adventurers' Guild names you {rank_after}! "
                f"{self._perk_line(rank_after)} ***")
        return notes

    def rank(self) -> Optional[str]:
        qp = self.quest_points()
        for threshold, name in RANKS:
            if qp >= threshold:
                return name
        return None

    def _perk_line(self, rank: str) -> str:
        return {
            "Member": "The tavern board now carries more work for you.",
            "Veteran": "Your travel focus recovers twice as fast.",
            "Champion": "A fourth companion may walk beside you.",
        }.get(rank, "")

    # ---- perks --------------------------------------------------------------

    def radiant_cap_bonus(self) -> int:
        return 2 if self.rank() in ("Member", "Veteran", "Champion") \
            else 0

    def teleport_cooldown_multiplier(self) -> float:
        return 0.5 if self.rank() in ("Veteran", "Champion") else 1.0

    def companion_cap(self) -> int:
        return 4 if self.rank() == "Champion" else 3

    # ---- UI -----------------------------------------------------------------

    def status_line(self) -> str:
        rank = self.rank() or "(no rank yet — 5 QP to join)"
        return f"Quest points: {self.quest_points()}   Guild: {rank}"
