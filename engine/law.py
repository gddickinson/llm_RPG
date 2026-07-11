"""Crime & law II (P12.9) — the guard-resolution menu.

Every settlement keeps a BOUNTY LEDGER (player.metadata["bounties"]
by settlement name). Crimes feed it: forcing doors, witnessed
trespass, assaulting citizens, robbing the unconscious. When a
guard stands beside you in a settlement where your name is worth
gold, the CONFRONTATION opens — Skyrim's menu, keys 1-5:

  1 PAY the fine (gold for a clean slate)
  2 JAIL (the day passes behind bars, and idle hands dull: the
    fine's worth of XP drains from your best lattice skill)
  3 BRIBE (60% of the fine + a CHA check; a refused bribe OFFENDS
    and the fine grows)
  4 TALK your way out (one Persuasion check per confrontation —
    a crit clears it free, a success halves the fine)
  5 RESIST (the fine grows half again, the guard swings, and the
    watch remembers)

Walking out of reach shelves the confrontation (short grace), it
does not clear the ledger. Remainder (planned): stolen-item flags
with fence-only sales, disguises vs witness memory.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.law")

GRACE_MINUTES = 60          # after any resolution or walk-away
JAIL_HOURS = 12
BRIBE_FRACTION = 0.6
GUARD_CLASSES = ("guard", "paladin")

MENU = ("[Law] The guard bars your way: \"There's a price on "
        "your head here.\"  1 pay {amount}g · 2 jail · 3 bribe "
        "{bribe}g · 4 talk · 5 resist")


class LawSystem:
    def __init__(self, engine):
        self.engine = engine
        self.active = None          # {"guard_id", "settlement", ...}

    # ------------------------------------------------------ ledger

    def _ledger(self) -> dict:
        return self.engine.player.metadata.setdefault("bounties", {})

    def settlement_here(self) -> str:
        """Nearest settlement center claims jurisdiction."""
        px, py = self.engine.player.position
        best, best_d = "the wilds", None
        for loc in self.engine.world.locations:
            name = loc.name
            if not any(k in name for k in ("Village", "Hamlet",
                                           "Camp")):
                continue
            d = abs(loc.x + loc.width // 2 - px) + \
                abs(loc.y + loc.height // 2 - py)
            if best_d is None or d < best_d:
                best, best_d = name, d
        return best

    def add_bounty(self, amount: int, reason: str = "",
                   settlement: str = None) -> None:
        settlement = settlement or self.settlement_here()
        ledger = self._ledger()
        ledger[settlement] = ledger.get(settlement, 0) + amount
        self.engine.memory_manager.add_event(
            f"[Law] Word spreads in {settlement}: "
            f"{reason or 'a crime'} (+{amount}g bounty, "
            f"now {ledger[settlement]}g).")

    def bounty_here(self) -> int:
        return self._ledger().get(self.settlement_here(), 0)

    # ------------------------------------------------- confrontation

    def check_contact(self) -> Optional[str]:
        """Per turn: an adjacent guard collects on the ledger."""
        engine = self.engine
        player = engine.player
        if self.active:
            guard = engine.npc_manager.npcs.get(
                self.active["guard_id"])
            if guard is None or not guard.is_active() or \
                    self._dist(guard) > 3:
                self.active = None
                player.metadata["law_grace_until"] = \
                    engine.world.time + GRACE_MINUTES
                engine.memory_manager.add_event(
                    "[Law] You slip out of the guard's reach — "
                    "the ledger remembers.")
            return None
        if engine.world.time < player.metadata.get(
                "law_grace_until", 0):
            return None
        amount = self.bounty_here()
        if amount <= 0:
            return None
        guard = self._adjacent_guard()
        if guard is None:
            return None
        self.active = {"guard_id": guard.id,
                       "settlement": self.settlement_here(),
                       "amount": amount, "talked": False}
        msg = MENU.format(amount=amount,
                          bribe=int(amount * BRIBE_FRACTION))
        engine.memory_manager.add_event(msg)
        return msg

    def resolve(self, choice: int) -> str:
        """Keys 1-5 while the confrontation is open."""
        if not self.active:
            return ""
        return {1: self._pay, 2: self._jail, 3: self._bribe,
                4: self._talk, 5: self._resist}.get(
                    choice, lambda: "")()

    # -------------------------------------------------- resolutions

    def _close(self, cleared: bool) -> None:
        if cleared:
            self._ledger().pop(self.active["settlement"], None)
        self.engine.player.metadata["law_grace_until"] = \
            self.engine.world.time + GRACE_MINUTES
        self.active = None

    def _pay(self) -> str:
        player = self.engine.player
        amount = self.active["amount"]
        if player.gold < amount:
            msg = (f"[Law] You can't cover the {amount}g fine — "
                   f"choose again.")
            self.engine.memory_manager.add_event(msg)
            return msg
        player.gold -= amount
        self._close(cleared=True)
        msg = f"[Law] You pay the {amount}g fine. The slate is clean."
        self.engine.memory_manager.add_event(msg)
        return msg

    def _jail(self) -> str:
        engine = self.engine
        player = engine.player
        amount = self.active["amount"]
        settlement = self.active["settlement"]
        engine.world.advance_time(JAIL_HOURS * 60)
        # idle hands: the fine's worth of XP drains from your best
        from engine.skill_progression import SKILLS, get_skill_xp
        skills = player.metadata.get("skills", {})
        if skills:
            top = max(skills, key=skills.get)
            skills[top] = max(0.0, skills[top] - amount * 2)
            drained = SKILLS.get(top, {}).get("name", top)
        else:
            drained = "nothing"
        player.metadata["fatigue"] = 30
        self._close(cleared=True)
        msg = (f"[Law] A cold night in the {settlement} cells. "
               f"You emerge cleared — but rusty ({drained} suffers).")
        engine.memory_manager.add_event(msg)
        return msg

    def _bribe(self) -> str:
        engine = self.engine
        player = engine.player
        cost = int(self.active["amount"] * BRIBE_FRACTION)
        if player.gold < cost:
            msg = "[Law] Your purse can't back the whisper."
            engine.memory_manager.add_event(msg)
            return msg
        from engine.skills import Skill, check
        result = check(player, Skill.PERSUASION, dc=12,
                       rng=engine.combat_system.rng)
        if result.success:
            player.gold -= cost
            self._close(cleared=True)
            msg = (f"[Law] {cost}g changes hands and the guard "
                   f"looks elsewhere.")
        else:
            self.active["amount"] = int(self.active["amount"] * 1.25)
            ledger = self._ledger()
            ledger[self.active["settlement"]] = self.active["amount"]
            msg = (f"[Law] \"Are you trying to BRIBE me?\" The fine "
                   f"grows ({self.active['amount']}g). Choose again.")
        engine.memory_manager.add_event(msg)
        return msg

    def _talk(self) -> str:
        engine = self.engine
        if self.active["talked"]:
            msg = "[Law] The guard is done listening."
            engine.memory_manager.add_event(msg)
            return msg
        self.active["talked"] = True
        from engine.skills import Degree, Skill, check
        result = check(engine.player, Skill.PERSUASION, dc=14,
                       rng=engine.combat_system.rng)
        if result.degree is Degree.CRIT_SUCCESS:
            self._close(cleared=True)
            msg = ("[Law] Your story is so good the guard waves "
                   "you through with a laugh. Cleared.")
        elif result.success:
            self.active["amount"] = max(1, self.active["amount"] // 2)
            ledger = self._ledger()
            ledger[self.active["settlement"]] = self.active["amount"]
            msg = (f"[Law] The guard softens — the fine is halved "
                   f"({self.active['amount']}g). Choose again.")
        else:
            msg = "[Law] The guard has heard it all before."
        engine.memory_manager.add_event(msg)
        return msg

    def _resist(self) -> str:
        engine = self.engine
        self.active["amount"] = int(self.active["amount"] * 1.5)
        ledger = self._ledger()
        ledger[self.active["settlement"]] = self.active["amount"]
        guard = engine.npc_manager.npcs.get(self.active["guard_id"])
        msg = (f"[Law] You shove past the law! The bounty grows "
               f"({self.active['amount']}g) — and the watch "
               f"remembers.")
        engine.memory_manager.add_event(msg)
        if guard is not None and guard.is_active():
            guard.modify_relationship(engine.player.id, -40)
            engine.combat_system._resolve(guard, engine.player)
        self._close(cleared=False)
        return msg

    # ------------------------------------------------------ helpers

    def _dist(self, npc) -> int:
        px, py = self.engine.player.position
        return max(abs(npc.position[0] - px),
                   abs(npc.position[1] - py))

    def _adjacent_guard(self):
        try:
            from engine.presence import npc_adjacent_to_player
        except Exception:
            npc_adjacent_to_player = None
        for npc in self.engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            if getattr(npc.character_class, "value", "") not in \
                    GUARD_CLASSES:
                continue
            if npc_adjacent_to_player is not None:
                if npc_adjacent_to_player(self.engine, npc, 1.5):
                    return npc
            elif self._dist(npc) <= 1:
                return npc
        return None
