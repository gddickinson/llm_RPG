"""Conspiracy & retaliation (P7.2) — the player can make a REAL enemy.

Playtest 2: deep hostile reputation only moved shop prices; nothing in
the world ever answered back. Now factions conspire against an infamous
player on an escalating, telegraphed ladder:

- rep ≤ THRESHOLD with a hunting faction → a warning first (a rumor and
  a `[Realm]` event: a price on your head), never an ambush from
  nowhere;
- still hostile a few days later → a level-scaled bounty hunter spawns
  off-screen and converges on your last known position (the pack-alert
  mechanic hostiles already use);
- rep ≤ DEEP → they send a pair.

Both outlaws and lawmen play: slaughter villagers and the GUARDS post
the bounty; betray the brigands (the fence storyline) and the road gets
dangerous. Reputation recovering above the threshold stands the hunt
down. State persists in saves; checks run once per game night, no LLM.
"""

import logging
from typing import List

from characters.factions import Faction, get_rep

logger = logging.getLogger("llm_rpg.retaliation")

THRESHOLD = -30
DEEP = -60
COOLDOWN_DAYS = 3
HUNTING_FACTIONS = (Faction.BRIGANDS, Faction.GUARDS)
SPAWN_MIN = 8           # never in the player's face...
SPAWN_MAX = 14          # ...never irrelevantly far
_OPEN_TERRAIN = ("grass", "forest", "swamp", "road")


class RetaliationSystem:
    def __init__(self, engine):
        self.engine = engine
        # faction value -> {"stage": 0 warned-not-yet, "last_day": int}
        self.state = {}

    # ---------------------------------------------------------- nightly

    def run_night(self) -> List[str]:
        engine, notes = self.engine, []
        player = engine.player
        if player is None or getattr(engine, "player_dead", False):
            return notes
        day = engine.world.time // (24 * 60)
        for faction in HUNTING_FACTIONS:
            rep = get_rep(player, faction)
            st = self.state.setdefault(
                faction.value, {"stage": 0, "last_day": -COOLDOWN_DAYS})
            if rep > THRESHOLD:
                st["stage"] = 0        # forgiveness stands the hunt down
                continue
            if day - st["last_day"] < COOLDOWN_DAYS:
                continue
            st["last_day"] = day
            if st["stage"] == 0:
                st["stage"] = 1
                note = (f"Word travels: the {faction.value} have put "
                        f"a price on your head.")
            else:
                count = 2 if rep <= DEEP else 1
                sent = sum(1 for _ in range(count)
                           if self._send_hunter())
                if not sent:
                    continue
                note = ("Bounty hunters are on your trail."
                        if sent > 1 else
                        "A bounty hunter has picked up your trail.")
            engine.memory_manager.add_event(f"[Realm] {note}")
            try:
                engine.world_director.rumors.append(note)
                del engine.world_director.rumors[:-5]
            except Exception:
                pass
            notes.append(note)
        return notes

    # ---------------------------------------------------------- hunters

    def _send_hunter(self) -> bool:
        from world.monsters import build_monster
        engine = self.engine
        wmap = engine.world.map
        px, py = engine.player.position
        spot = None
        for d in range(SPAWN_MIN, SPAWN_MAX + 1):
            for dx in range(-d, d + 1):
                dy = d - abs(dx)
                for sy in (dy, -dy):
                    x, y = px + dx, py + sy
                    if not (0 <= x < wmap.width and
                            0 <= y < wmap.height):
                        continue
                    try:
                        if wmap.get_terrain_at(x, y).value not in \
                                _OPEN_TERRAIN:
                            continue
                        if wmap.get_character_at(x, y) is not None:
                            continue
                    except Exception:
                        continue
                    spot = (x, y)
                    break
                if spot:
                    break
            if spot:
                break
        if spot is None:
            return False
        hunter = build_monster("bounty_hunter", spot)
        level = max(getattr(hunter, "level", 1), engine.player.level)
        bonus_hp = 4 * max(0, level - getattr(hunter, "level", 1))
        hunter.level = level
        hunter.max_hp += bonus_hp
        hunter.hp = hunter.max_hp
        hunter.metadata["alert"] = [px, py]   # converge on the trail
        hunter.metadata["bounty_hunter"] = True
        engine.npc_manager.add_npc(hunter)
        wmap.place_character(hunter, *spot)
        return True

    # ------------------------------------------------------ persistence

    def to_dict(self) -> dict:
        return {"state": self.state}

    def from_dict(self, data: dict) -> None:
        self.state = dict(data.get("state", {}))
