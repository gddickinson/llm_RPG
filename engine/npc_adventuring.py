"""NPC adventuring (George: the world's OTHER heroes go on adventures too —
they should discover and WORK an adventure quest chain, not just the player).

An eligible adventurer NPC (one of the `AdventurerSystem` heroes, strong enough
to plausibly survive) ADOPTS an unresolved adventure the player hasn't started,
and works it ACT BY ACT over game-days — a `[Realm]` beat for setting out and
for each act — until it faces the boss and RESOLVES the adventure (reusing
`adventure_seed.resolve_adventure`: the guardians disperse, the threat thins,
the world reshapes) under a triumphant `[Legend]`. The deed grows the hero.

Gated to be RARE and SAFE: only adventures with NO player quest-progress are
adopted (the player never loses one they're working), at most `MAX_CONCURRENT`
run at once, and only every so often. When an NPC finishes an adventure its
now-impossible quests are marked FAILED so the player can't accept a dead end —
the classic "a rival beat you to it" stake (as `lairs.claim_by_rival` already
does for hoards). No per-tick LLM; state persists.
"""

import logging
import os
import random
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.npc_adventuring")

ACT_DAYS = 2            # game-days an NPC spends on each act
ACTS = 3               # the standard 3-act adventure
START_CHANCE = 0.20    # per-day chance a free hero takes up an adventure
MIN_LEVEL = 5          # a hero needs some steel to walk into a boss lair
MAX_CONCURRENT = 2

# the seeder attributes that expose adventure_id()/is_resolved()/resolve()
_ADV_ATTRS = ("emberfell", "blackbanner", "wychwood", "ravenmoor")

# each act's beat, completed with " {threat}" (a threat reads "the <name>")
_ACT_FLAVOR = ("takes up the trail of", "presses deeper into the hunt for",
               "closes on the lair of")


class NpcAdventuringSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.active: dict = {}      # hero_id -> {"adv","act","day"}

    # ---- nightly ---------------------------------------------------

    def run_day(self, day: int = 0) -> None:
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return
        self._advance(day)
        self._maybe_start(day)

    def _advance(self, day: int) -> None:
        for hid in list(self.active):
            st = self.active[hid]
            hero = self.engine.npc_manager.npcs.get(hid)
            if hero is None or not hero.is_active():
                del self.active[hid]           # the hero fell on the road
                continue
            if day - st["day"] < ACT_DAYS:
                continue
            st["day"] = day
            st["act"] += 1
            if st["act"] > ACTS:
                self._finish(hero, st["adv"])
                del self.active[hid]
            else:
                self._beat(f"[Realm] {hero.name} {_ACT_FLAVOR[st['act'] - 1]} "
                           f"{self._threat(st['adv'])}.")

    def _maybe_start(self, day: int) -> None:
        if len(self.active) >= MAX_CONCURRENT:
            return
        if self.rng.random() > START_CHANCE:
            return
        adv = self._pick_adventure()
        hero = self._pick_hero()
        if adv is None or hero is None:
            return
        self.active[hero.id] = {"adv": adv, "act": 1, "day": day}
        self._beat(f"[Realm] The adventurer {hero.name} sets out to end "
                   f"{self._threat(adv)}.")

    # ---- selection -------------------------------------------------

    def _pick_adventure(self) -> Optional[str]:
        taken = {st["adv"] for st in self.active.values()}
        pool = [aid for aid in self._open_adventures() if aid not in taken]
        return self.rng.choice(pool) if pool else None

    def _open_adventures(self) -> List[str]:
        """Seeded, unresolved adventures the PLAYER has not begun."""
        out = []
        for attr in _ADV_ATTRS:
            sub = getattr(self.engine, attr, None)
            if sub is None or not hasattr(sub, "resolve"):
                continue
            try:
                if not sub.is_active() or sub.is_resolved():
                    continue
            except Exception:
                continue
            aid = sub.adventure_id() if hasattr(sub, "adventure_id") else attr
            if aid and not self._player_engaged(aid):
                out.append(aid)
        return out

    def _player_engaged(self, adv_id: str) -> bool:
        from quests.quest import QuestStatus
        pref = f"q_{adv_id}_"
        for qid, q in self.engine.quest_manager.quests.items():
            if qid.startswith(pref) and q.status != QuestStatus.AVAILABLE:
                return True
        return False

    def _pick_hero(self):
        advs = getattr(self.engine, "adventurers", None)
        if advs is None:
            return None
        cands = []
        for aid in advs.living():
            hero = self.engine.npc_manager.npcs.get(aid)
            if hero is None or aid in self.active:
                continue
            if getattr(hero, "level", 1) >= MIN_LEVEL:
                cands.append(hero)
        return self.rng.choice(cands) if cands else None

    # ---- resolution ------------------------------------------------

    def _finish(self, hero, adv_id: str) -> None:
        seeder = self._seeder(adv_id)
        if seeder is None:
            return
        self._defeat_boss(seeder)
        self._legend(f"[Legend] {hero.name} has ended {self._threat(adv_id)}, "
                     f"and returns to the guild halls in triumph.")
        try:
            from engine.adventure_seed import resolve_adventure
            resolve_adventure(self.engine, adv_id, "npc")
        except Exception as e:
            logger.debug(f"npc resolve {adv_id}: {e}")
        self._fail_player_quests(adv_id)
        self._reward(hero)

    def _defeat_boss(self, seeder) -> None:
        for nid in getattr(seeder, "foe_ids", []):
            foe = self.engine.npc_manager.npcs.get(nid)
            if foe is None or not foe.metadata.get("adventure_boss"):
                continue
            foe.status = "defeated"
            try:
                self.engine.world.map.remove_character(foe)
            except Exception:
                pass

    def _fail_player_quests(self, adv_id: str) -> None:
        """The player missed their chance — the now-impossible quests fail so
        no dead-end can be accepted (the rival-beat-you-to-it stake)."""
        from quests.quest import QuestStatus
        pref = f"q_{adv_id}_"
        for qid, q in self.engine.quest_manager.quests.items():
            if qid.startswith(pref) and q.status == QuestStatus.AVAILABLE:
                q.status = QuestStatus.FAILED

    def _reward(self, hero) -> None:
        try:
            from engine.leveling import award_xp
            award_xp(hero, 400)
        except Exception:
            pass

    # ---- helpers ---------------------------------------------------

    def _seeder(self, adv_id: str):
        for attr in _ADV_ATTRS:
            sub = getattr(self.engine, attr, None)
            if sub is None:
                continue
            aid = sub.adventure_id() if hasattr(sub, "adventure_id") else attr
            if aid == adv_id:
                return sub
        return None

    def _threat(self, adv_id: str) -> str:
        from items.data_loader import load_data_file
        for f in (f"{adv_id}.json",):
            try:
                d = load_data_file(f) or {}
                if d.get("resolved_name"):
                    return "the " + d["resolved_name"]
            except Exception:
                pass
        return f"the threat at {adv_id}"

    def _beat(self, line: str) -> None:
        try:
            self.engine.memory_manager.add_event(line)
        except Exception:
            pass

    _legend = _beat

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"active": self.active}

    def from_dict(self, d: dict) -> None:
        self.active = (d or {}).get("active", {}) or {}
