"""Radiant quest generation (P4.1) — the world is never questless.

Each morning (after the world director's overnight events), 1-2 task
quests are generated from actual world state and posted to the tavern
quest board:

- an active shortage -> FETCH that item ("The ale shortage")
- a director monster sighting / hostile in the world -> KILL its kind
- otherwise a gathering/cull template keyed to the region's resources

Rewards scale with player level. At most MAX_ACTIVE radiant quests exist
in the AVAILABLE state; stale ones (unaccepted for EXPIRY_DAYS) are
withdrawn. Radiant quest ids are `radiant_<day>_<n>`; they serialize
through the quest manager like any quest.
"""

import logging
import random
from typing import List, Optional

from quests.quest import Quest, QuestObjective, ObjectiveType, QuestStatus

logger = logging.getLogger("llm_rpg.radiant")

MAX_ACTIVE = 3
EXPIRY_DAYS = 3
BOARD_LOCATION = "Oakvale Tavern"

# Fallback templates: (title, objective type, target, count, flavor)
FALLBACK = [
    ("Herbs for the Stockpot", "fetch", "herb_bundle", 2,
     "The kitchens are low on herbs — gather bundles from the wild."),
    ("Timber Tally", "fetch", "logs", 3,
     "The camp needs timber. Chop and deliver logs."),
    ("Ore for the Forge", "fetch", "copper_ore", 2,
     "Durgan's furnace runs hungry. Bring copper ore."),
    ("Wolf Cull", "kill", "monster", 2,
     "Wolves press close to the roads. Thin them out."),
    ("Fresh Catch", "fetch", "raw_trout", 2,
     "The inn wants river trout for tonight's table."),
]

GIVER_POOL = ["tavernkeeper_01", "guard_01", "camp_foreman_01",
              "hamlet_innkeeper_01"]


class RadiantQuestGenerator:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ---- daily run --------------------------------------------------------

    def run_morning(self) -> List[str]:
        """Expire stale radiants, then top up to the cap. Returns notes."""
        qm = self.engine.quest_manager
        if qm is None:
            return []
        notes = []
        day = self.engine.world.time // (24 * 60)

        # Withdraw stale unaccepted radiants
        for quest in list(qm.quests.values()):
            if not quest.id.startswith("radiant_"):
                continue
            if quest.status != QuestStatus.AVAILABLE:
                continue
            posted_day = self._posted_day(quest.id)
            if posted_day is not None and day - posted_day >= EXPIRY_DAYS:
                del qm.quests[quest.id]
                self._unpost(quest.id)
                notes.append(f"The notice '{quest.title}' was taken down.")

        # Top up
        active = [q for q in qm.quests.values()
                  if q.id.startswith("radiant_") and
                  q.status == QuestStatus.AVAILABLE]
        want = self.rng.randint(1, 2)
        n = 0
        while len(active) < MAX_ACTIVE and n < want:
            quest = self._generate(day, n)
            if quest is None:
                break
            qm.quests[quest.id] = quest
            self._post(quest.id)
            active.append(quest)
            notes.append(f"New notice on the tavern board: {quest.title}")
            n += 1

        for note in notes:
            self.engine.memory_manager.add_event(f"[Board] {note}")
        return notes

    # ---- generation ----------------------------------------------------------

    def _generate(self, day: int, n: int) -> Optional[Quest]:
        qid = f"radiant_{day}_{n}"
        if qid in self.engine.quest_manager.quests:
            return None
        spec = self._from_shortage() or self._from_monsters() or \
            self.rng.choice(FALLBACK)
        title, obj_type, target, count, flavor = spec

        level = max(1, self.engine.player.level)
        reward_gold = 20 + 12 * level + 5 * count
        reward_xp = 30 + 15 * level

        obj = QuestObjective(
            obj_type=(ObjectiveType.FETCH if obj_type == "fetch"
                      else ObjectiveType.KILL),
            target=target,
            required=count,
            description=(f"{'Collect' if obj_type == 'fetch' else 'Slay'} "
                         f"{count}x {target.replace('_', ' ')}"),
        )
        quest = Quest(
            id=qid,
            title=title,
            description=flavor,
            objectives=[obj],
            giver_id=self._pick_giver(),
            reward_gold=reward_gold,
            reward_items=[],
            reward_xp=reward_xp,
        )
        quest.status = QuestStatus.AVAILABLE
        return quest

    def _from_shortage(self):
        try:
            shortages = self.engine.world_director.shortages
            now = self.engine.world.time
            live = [iid for iid, exp in shortages.items() if now < exp]
            if not live:
                return None
            from items.item_registry import ITEM_REGISTRY
            iid = self.rng.choice(live)
            item = ITEM_REGISTRY.get(iid)
            if item is None:
                return None
            return (f"The {item.name} Shortage", "fetch", iid, 2,
                    f"With {item.name} scarce, good coin is paid for "
                    f"fresh supply.")
        except Exception:
            return None

    def _from_monsters(self):
        hostiles = [n for n in self.engine.npc_manager.npcs.values()
                    if n.is_active() and n.id.startswith("enc_")]
        if not hostiles:
            return None
        target = self.rng.choice(hostiles)
        klass = getattr(target.character_class, "value", "monster")
        return (f"Bounty: {target.name}", "kill", klass, 1,
                f"A {target.name} was sighted in the wilds. "
                f"The bounty stands until it's dealt with.")

    def _pick_giver(self) -> str:
        pool = [gid for gid in GIVER_POOL
                if self.engine.npc_manager.get_npc(gid) is not None]
        return self.rng.choice(pool) if pool else ""

    # ---- board plumbing --------------------------------------------------------

    def _board(self):
        return self.engine.quest_board_manager.board_at(BOARD_LOCATION)

    def _post(self, quest_id: str) -> None:
        board = self._board()
        if board is not None and quest_id not in board.posted_quest_ids:
            board.posted_quest_ids.append(quest_id)

    def _unpost(self, quest_id: str) -> None:
        board = self._board()
        if board is not None and quest_id in board.posted_quest_ids:
            board.posted_quest_ids.remove(quest_id)

    def _posted_day(self, quest_id: str) -> Optional[int]:
        try:
            return int(quest_id.split("_")[1])
        except (IndexError, ValueError):
            return None
