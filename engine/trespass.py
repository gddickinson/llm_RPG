"""Trespass & consequences (P9A.4) — entering uninvited is WITNESSED.

The chain George asked for, assembled from parts already in place:
doors know how you got in (P9A.1), homes know who lives there (P9A.3),
reputation drives the bounty ladder (P7.2), and guards patrol (P7.1).

Rules:
- Taverns, temples, shrines and daytime shops are PUBLIC — no cost.
- Derelict buildings have no one left to care.
- A private home (or a shop after hours) is TRESPASS. If the owner is
  home or nearby, you are witnessed: they object out loud, remember it
  (NPC memory + relationship), and word costs villager reputation.
- FORCING a door doubles everything, hits GUARD reputation too (it's
  a crime, not a faux pas), and any guard in earshot is alerted and
  converges on the door. Repeat offenders drive guard reputation
  toward the P7.2 threshold — the watch posts a bounty. The player
  can make a real enemy of the law.
- Slipping in and out unseen costs nothing today… but the ledger
  remembers (`unseen_break_ins`), for future fence/heist content.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.trespass")

WITNESS_RADIUS = 8       # owner this close to home sees you
GUARD_EARSHOT = 12       # forced doors are LOUD
REP_TRESPASS = -4        # villagers, witnessed sneaky entry
REP_BREAKIN_VILLAGERS = -6
REP_BREAKIN_GUARDS = -8
RELATIONSHIP_HIT = -10
NIGHT_HOURS = (21, 22, 23, 0, 1, 2, 3, 4, 5)


class TrespassSystem:
    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------ hook

    def on_enter(self, loc) -> Optional[str]:
        """Called by enter_building after a successful entry."""
        engine = self.engine
        door = engine.door_manager.door(loc.name)
        policy = door.get("policy", "open")
        if policy == "open":
            return None
        hour = (engine.world.time // 60) % 24
        if policy == "night_locked" and hour not in NIGHT_HOURS:
            return None                      # shop in business hours
        if engine.homes.is_derelict(loc.name):
            return None
        day = engine.world.time // (24 * 60)
        forced = (door.get("state") == "broken" and
                  engine.player.metadata.get("forced_entry_day") == day)
        owner = engine.homes.owner_of(loc.name)
        witnessed = self._witnessed(loc, owner, hour)
        if forced:
            return self._crime(loc, owner, witnessed)
        if witnessed:
            return self._objection(loc, owner)
        marks = engine.player.metadata
        marks["unseen_break_ins"] = marks.get("unseen_break_ins", 0) + 1
        return None

    # ------------------------------------------------------- internals

    def _witnessed(self, loc, owner, hour: int) -> bool:
        if owner is None:
            return False
        if hour in NIGHT_HOURS:
            return True                      # everyone's home at night
        ox, oy = owner.position
        cx = loc.x + loc.width // 2
        cy = loc.y + loc.height // 2
        return abs(ox - cx) + abs(oy - cy) <= WITNESS_RADIUS

    def _objection(self, loc, owner) -> str:
        engine = self.engine
        msg = (f"{owner.name} rounds on you: \"You have no business "
               f"in my home!\"")
        engine.memory_manager.add_event(msg)
        self._cost(owner, villagers=REP_TRESPASS, guards=0)
        return msg

    def _crime(self, loc, owner, witnessed: bool) -> str:
        engine = self.engine
        if witnessed and owner is not None:
            msg = (f"{owner.name} cries out: \"Thief! The watch! "
                   f"THE WATCH!\"")
        else:
            msg = ("The splintered door will not go unnoticed. "
                   "Someone whistles for the watch.")
        engine.memory_manager.add_event(msg)
        self._cost(owner if witnessed else None,
                   villagers=REP_BREAKIN_VILLAGERS,
                   guards=REP_BREAKIN_GUARDS)
        self._alert_guards(loc)
        try:   # the ledger remembers (P12.9)
            self.engine.law.add_bounty(
                10 if witnessed else 5,
                reason=f"a break-in at the {loc.name}",
                witnessed=witnessed)
        except Exception:
            pass
        return msg

    def _cost(self, owner, villagers: int, guards: int) -> None:
        engine = self.engine
        try:
            from characters.factions import Faction, modify_rep
            if villagers:
                new = modify_rep(engine.player, Faction.VILLAGERS,
                                 villagers)
                engine.memory_manager.add_event(
                    f"Reputation with villagers: {villagers} ({new})")
            if guards:
                new = modify_rep(engine.player, Faction.GUARDS, guards)
                engine.memory_manager.add_event(
                    f"Reputation with guards: {guards} ({new})")
        except Exception:
            pass
        if owner is not None:
            pid = engine.player.id
            owner.relationships[pid] = \
                owner.relationships.get(pid, 0) + RELATIONSHIP_HIT
            try:
                owner.memories.append(
                    f"{engine.player.name} broke into my home.")
            except Exception:
                pass

    def _alert_guards(self, loc) -> None:
        """Guards in earshot converge on the door (pack-alert reuse)."""
        engine = self.engine
        cx = loc.x + loc.width // 2
        cy = loc.y + loc.height - 1
        alerted = 0
        for npc in engine.npc_manager.npcs.values():
            if getattr(npc.character_class, "value", "") != "guard":
                continue
            if not npc.is_active():
                continue
            nx, ny = npc.position
            if abs(nx - cx) + abs(ny - cy) <= GUARD_EARSHOT:
                npc.metadata["alert"] = [cx, cy]
                alerted += 1
        if alerted:
            engine.memory_manager.add_event(
                "Armored footsteps quicken somewhere nearby.")
