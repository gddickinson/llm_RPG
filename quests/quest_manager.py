"""Quest manager — tracks active/completed quests + reacts to game events."""

import logging
from typing import Any, Dict, List, Optional

from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus
from quests.quest_templates import create_quest, all_quest_ids

logger = logging.getLogger("llm_rpg.quests")


class QuestManager:
    """Manages all quests for a single player.

    Game events to wire up (from engine):
    - on_npc_defeated(npc_id, npc_class): KILL objectives
    - on_item_acquired(item_id): FETCH objectives
    - on_item_delivered(item_id, recipient_id): DELIVER objectives
    - on_npc_talked(npc_id): TALK objectives
    - on_location_entered(location_name): EXPLORE objectives
    - on_turn_advanced(): SURVIVE objectives
    """

    def __init__(self):
        self.quests: Dict[str, Quest] = {}     # id -> Quest
        self.event_log: List[str] = []
        logger.info("QuestManager initialized")

    # ----- lifecycle ---------------------------------------------------------

    def offer_quest(self, quest_id: str) -> Optional[Quest]:
        """Create a new quest in the AVAILABLE state."""
        if quest_id in self.quests:
            return self.quests[quest_id]
        try:
            quest = create_quest(quest_id)
        except KeyError:
            logger.warning(f"Cannot offer unknown quest: {quest_id}")
            return None
        self.quests[quest_id] = quest
        return quest

    def is_unlocked(self, quest: Quest) -> bool:
        """A quest with a prerequisite hides until that quest is done."""
        prereq = quest.metadata.get("prereq_quest")
        if not prereq:
            return True
        done = self.quests.get(prereq)
        return done is not None and done.status == QuestStatus.TURNED_IN

    def accept_quest(self, quest_id: str) -> bool:
        quest = self.quests.get(quest_id)
        if not quest or quest.status != QuestStatus.AVAILABLE or \
                not self.is_unlocked(quest):
            return False
        quest.status = QuestStatus.ACTIVE
        self._log(f"Quest accepted: {quest.title}")
        return True

    def turn_in(self, quest_id: str, player) -> bool:
        """Mark a completed quest as turned in and apply rewards to player.

        Returns True if rewards were applied. Level-up messages (if any) are
        appended to `self.event_log` so the engine can surface them.
        """
        quest = self.quests.get(quest_id)
        if not quest:
            return False
        quest.update_status()
        if quest.status != QuestStatus.COMPLETED:
            return False

        # Apply rewards
        player.gold = getattr(player, "gold", 0) + quest.reward_gold
        for item_id in quest.reward_items:
            try:
                from items.item_registry import create_item
                it = create_item(item_id)
                if it:
                    player.inventory.append(it)
            except Exception as e:
                logger.warning(f"Reward item issue: {e}")
        # Grant XP through the leveling system
        if quest.reward_xp:
            try:
                from engine.leveling import award_xp
                msgs = award_xp(player, quest.reward_xp)
                for m in msgs:
                    self._log(m)
            except Exception as e:
                logger.warning(f"Level-up check failed: {e}")

        # Capability unlocks: "teleport:<key>" / "topic:<id>" / "spell:<id>"
        for unlock in quest.metadata.get("reward_unlocks", []):
            self._apply_unlock(player, unlock)

        quest.status = QuestStatus.TURNED_IN
        self._log(f"Quest turned in: {quest.title} (+{quest.reward_gold}g, +{quest.reward_xp}xp)")
        return True

    def _apply_unlock(self, player, unlock: str) -> None:
        kind, _, key = unlock.partition(":")
        meta = player.metadata
        if kind == "teleport":
            bucket = meta.setdefault("teleport_unlocks", [])
            if key not in bucket:
                bucket.append(key)
                self._log(f"Unlocked: fast travel to {key.title()}!")
        elif kind == "topic":
            bucket = meta.setdefault("topics_known", [])
            if key not in bucket:
                bucket.append(key)
                self._log(f"New topic in your journal: {key}")
        elif kind == "spell":
            bucket = meta.setdefault("spells_known", [])
            if key not in bucket:
                bucket.append(key)
                self._log(f"You have learned the {key} spell!")
        else:
            logger.warning(f"Unknown unlock kind: {unlock}")

    def try_deliver(self, player, npc_id: str) -> List[str]:
        """Talking to a DELIVER target hands over carried quest items."""
        notes = []
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type != ObjectiveType.DELIVER or \
                        obj.is_complete():
                    continue
                item_id, _, recipient = obj.target.partition(":")
                if recipient != npc_id:
                    continue
                for it in list(player.inventory):
                    if getattr(it, "id", "") == item_id:
                        player.inventory.remove(it)
                        obj.increment(1)
                        self._newly_completed(quest, obj)
                        notes.append(
                            f"You hand over {getattr(it, 'name', item_id)}.")
                        break
        return notes

    # ----- offered / turn-in queries (NPC-driven UI) ---------------------

    def offered_by(self, giver_id: str) -> List[Quest]:
        """Unlocked AVAILABLE quests offered by this giver."""
        return [q for q in self.quests.values()
                if q.giver_id == giver_id and
                q.status == QuestStatus.AVAILABLE and
                self.is_unlocked(q)]

    def ready_for_turn_in(self, giver_id: str) -> List[Quest]:
        """Quests in COMPLETED state belonging to this giver."""
        return [q for q in self.quests.values()
                if q.giver_id == giver_id and q.status == QuestStatus.COMPLETED]

    # ----- queries -----------------------------------------------------------

    def active(self) -> List[Quest]:
        return [q for q in self.quests.values() if q.status == QuestStatus.ACTIVE]

    def completed(self) -> List[Quest]:
        return [q for q in self.quests.values()
                if q.status in (QuestStatus.COMPLETED, QuestStatus.TURNED_IN)]

    def available(self) -> List[Quest]:
        return [q for q in self.quests.values()
                if q.status == QuestStatus.AVAILABLE]

    def get(self, quest_id: str) -> Optional[Quest]:
        return self.quests.get(quest_id)

    def summary(self) -> str:
        if not self.quests:
            return "No quests active."
        lines = ["=== Quests ==="]
        groups = {
            "Active": self.active(),
            "Completed": [q for q in self.completed() if q.status == QuestStatus.COMPLETED],
            "Turned in": [q for q in self.completed() if q.status == QuestStatus.TURNED_IN],
            "Available": self.available(),
        }
        for label, items in groups.items():
            if not items:
                continue
            lines.append(f"\n-- {label} --")
            for q in items:
                lines.append(q.progress_summary())
        return "\n".join(lines)

    # ----- event hooks -------------------------------------------------------

    def _newly_completed(self, quest: Quest, obj: QuestObjective) -> None:
        if obj.is_complete():
            self._log(f"Objective complete: {obj.description}")
        quest.update_status()
        if quest.status == QuestStatus.COMPLETED:
            self._log(f"Quest ready to turn in: {quest.title}")

    def on_npc_defeated(self, npc_id: str, npc_class: str = "") -> None:
        hostile = npc_class in ("monster", "brigand", "troll")
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type != ObjectiveType.KILL:
                    continue
                # Match by exact id, by class — and 'monster' as a
                # forgiving authoring default matches ANY hostile
                # kill (PT3.3: DM quests targeting 'monster' never
                # completed on brigand-class victims)
                if obj.target == npc_id or obj.target == npc_class \
                        or (obj.target == "monster" and hostile):
                    obj.increment(1)
                    self._newly_completed(quest, obj)

    def on_item_acquired(self, item_id: str, quantity: int = 1) -> None:
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type == ObjectiveType.FETCH and obj.target == item_id:
                    obj.increment(quantity)
                    self._newly_completed(quest, obj)

    def on_item_delivered(self, item_id: str, recipient_id: str) -> None:
        target_key = f"{item_id}:{recipient_id}"
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type == ObjectiveType.DELIVER and obj.target == target_key:
                    obj.increment(1)
                    self._newly_completed(quest, obj)

    def on_npc_talked(self, npc_id: str) -> None:
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type == ObjectiveType.TALK and obj.target == npc_id:
                    obj.increment(1)
                    self._newly_completed(quest, obj)

    def on_location_entered(self, location_name: str) -> None:
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type == ObjectiveType.EXPLORE \
                        and obj.target.lower() == location_name.lower():
                    obj.increment(1)
                    self._newly_completed(quest, obj)

    def on_turn_advanced(self) -> None:
        for quest in self.active():
            for obj in quest.objectives:
                if obj.obj_type == ObjectiveType.SURVIVE:
                    obj.increment(1)
                    self._newly_completed(quest, obj)

    # ----- save/load ---------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quests": {qid: q.to_dict() for qid, q in self.quests.items()},
            "event_log": self.event_log[-100:],
        }

    def from_dict(self, d: Dict[str, Any]) -> None:
        self.quests = {qid: Quest.from_dict(qd)
                       for qid, qd in d.get("quests", {}).items()}
        self.event_log = list(d.get("event_log", []))

    # ----- internal ----------------------------------------------------------

    def _log(self, msg: str) -> None:
        self.event_log.append(msg)
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]
        logger.info(msg)
