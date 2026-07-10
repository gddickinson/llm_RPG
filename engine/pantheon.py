"""The Pantheon (P8.4, pattern ported from autonomous_world).

Five gods watch the realm from `data/pantheon.json`, each with a
domain, deed keywords, one miracle, and an omen line. The loop:

- DEEDS build favor: every ledger entry (engine/player_deeds) is
  matched against each god's keywords — slaying feeds Morrik, harvests
  feed Solara, finished quests feed Veyra, diary tiers feed Grimble.
- PRAYER (SHIFT+P at any shrine or temple, once per game day) goes to
  whichever god favors you most. Below the miracle threshold you get a
  quiet blessing and +1 favor; at threshold the god SPENDS your favor
  on their miracle — engine-enforced and deliberately small: a heal, a
  short blessing, a little found coin, a cured disease, a whispered
  rumor. The LLM never adjudicates this; it's all code and dice.
- OMENS: a god holding deep favor occasionally marks the realm at
  night ("[Realm] Ravens circle the walls sunwise…"), feeding the
  rumor mill and topic journal like all other world news.

Favor and prayer cooldowns ride `player.metadata` — saves are free.
"""

import json
import logging
import os
import random
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.pantheon")

MIRACLE_COST = 10
FAVOR_CAP = 50
OMEN_FAVOR = 25
OMEN_CHANCE = 0.25
MIRACLE_GOLD = 15


def _load() -> Dict[str, dict]:
    try:
        with open(os.path.join("data", "pantheon.json")) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("pantheon.json missing/corrupt; heavens empty")
        return {}


GODS: Dict[str, dict] = _load()


def on_deed(engine, deed: str) -> None:
    """player_deeds hook: deeds are how gods notice you."""
    try:
        favor = engine.player.metadata.setdefault("god_favor", {})
        for gid, god in GODS.items():
            if any(k in deed for k in god.get("keywords", [])):
                favor[gid] = min(FAVOR_CAP, favor.get(gid, 0) + 1)
    except Exception:
        pass


class PantheonSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ------------------------------------------------------------ pray

    def pray(self, at_altar: bool = False) -> str:
        engine = self.engine
        player = engine.player
        if not GODS:
            return "The heavens are empty."
        if not at_altar and not self._at_holy_place():
            return "You murmur a prayer, but this is no holy place. " \
                   "Seek a shrine or temple."
        day = engine.world.time // (24 * 60)
        meta = player.metadata
        if meta.get("last_pray_day") == day:
            return "You have already prayed today. The gods value " \
                   "patience."
        meta["last_pray_day"] = day
        gid, god, favor = self._chosen_god()
        if favor >= MIRACLE_COST:
            meta["god_favor"][gid] = favor - MIRACLE_COST
            msg = self._miracle(gid, god)
        else:
            meta.setdefault("god_favor", {})[gid] = \
                min(FAVOR_CAP, favor + 1)
            msg = (f"You pray to {god['name']} {god['title']}. "
                   f"A quiet warmth answers — nothing more, yet.")
        engine.memory_manager.add_event(msg)
        return msg

    def _at_holy_place(self) -> bool:
        try:
            loc = self.engine.player_location()   # interior-aware
            name = (loc.name if loc else "").lower()
            return "shrine" in name or "temple" in name
        except Exception:
            return False

    def _chosen_god(self) -> Tuple[str, dict, int]:
        favor = self.engine.player.metadata.setdefault("god_favor", {})
        gid = max(GODS, key=lambda g: favor.get(g, 0))
        return gid, GODS[gid], favor.get(gid, 0)

    # -------------------------------------------------------- miracles

    def _miracle(self, gid: str, god: dict) -> str:
        engine, player = self.engine, self.engine.player
        kind = god.get("miracle", "bless")
        head = (f"{god['name']} {god['title']} answers! "
                f"{god['answer']}")
        if kind == "heal":
            player.hp = player.max_hp
            return f"{head} You are fully healed."
        if kind == "bless":
            try:
                from characters.status_effects import apply_effect
                apply_effect(player, "blessed", 60)
            except Exception:
                pass
            return f"{head} You are blessed."
        if kind == "fortune":
            player.gold = getattr(player, "gold", 0) + MIRACLE_GOLD
            return f"{head} (+{MIRACLE_GOLD} gold)"
        if kind == "cure":
            try:
                from engine.disease import is_infected
                if is_infected(player):
                    engine.disease.cure(player)
                    return f"{head} Your sickness is gone."
            except Exception:
                pass
            player.hp = min(player.max_hp, player.hp + 8)
            return f"{head} Your wounds close a little."
        if kind == "insight":
            rumor = self._whisper()
            return f"{head} A voice whispers: \"{rumor}\""
        return head

    def _whisper(self) -> str:
        try:
            rumors = self.engine.world_director.rumors
            if rumors:
                return self.rng.choice(rumors)
        except Exception:
            pass
        return "Walk the roads; the realm rewards the curious."

    # ---------------------------------------------------------- nightly

    def run_day(self) -> Optional[str]:
        """A deeply-pleased god occasionally marks the realm."""
        if not GODS:
            return None
        favor = self.engine.player.metadata.get("god_favor", {})
        gid = max(GODS, key=lambda g: favor.get(g, 0), default=None)
        if gid is None or favor.get(gid, 0) < OMEN_FAVOR:
            return None
        if self.rng.random() >= OMEN_CHANCE:
            return None
        omen = GODS[gid]["omen"]
        self.engine.memory_manager.add_event(f"[Realm] {omen}")
        try:
            self.engine.world_director.rumors.append(omen)
            del self.engine.world_director.rumors[:-5]
        except Exception:
            pass
        return omen
