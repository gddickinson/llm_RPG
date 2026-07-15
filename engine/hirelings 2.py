"""Hirelings (M.7) — party members you PAY, not befriend.

A recruit (M.6/companions) throws in with you out of TRUST. A hireling
throws in for COIN: an upfront fee, then a daily wage. They serve for an
agreed term (a fixed number of days) or on an open salary, and they walk
the moment the coin stops — an unpaid hireling grumbles a day, then spits
and quits, souring on you. This is how you fill out a party of strangers
before anyone likes you: the taverns and (M.7b) guild halls are full of
blades for hire.

The whole contract lives on `npc.metadata["hire"]` (wage, term, what
they've been paid through), so it rides the normal NPC save; the system
itself is stateless, reading the world clock each night to settle wages.
Any adventuring-class NPC can be hired — including an M.6 adventurer, who
you can thus either befriend into a free companion or simply pay.
"""

import logging

logger = logging.getLogger("llm_rpg.hirelings")

SIGN_PER_LEVEL = 15         # the upfront signing fee, per level
WAGE_PER_LEVEL = 5          # the daily wage, per level
GRACE_DAYS = 1             # missed paydays tolerated before they walk
HIREABLE = {"warrior", "ranger", "wizard", "cleric", "bard",
            "paladin", "rogue"}


class HirelingSystem:
    def __init__(self, engine):
        self.engine = engine

    # ---- helpers ---------------------------------------------------

    def _day(self) -> int:
        return self.engine.world.time // (24 * 60)

    def cost(self, npc):
        """(signing fee, daily wage) — scaled by the hireling's level."""
        lvl = max(1, getattr(npc, "level", 1))
        return SIGN_PER_LEVEL * lvl, WAGE_PER_LEVEL * lvl

    def is_hireling(self, npc) -> bool:
        return bool((getattr(npc, "metadata", {}) or {}).get("hire"))

    def can_hire(self, npc) -> str:
        """Empty string if hireable now, else the reason you can't."""
        if npc is None:
            return "There's no one here to hire."
        cm = self.engine.companion_manager
        if npc.id in cm.party:
            return f"{npc.name} is already with you."
        if not npc.is_active():
            return f"{npc.name} can't take a contract now."
        klass = getattr(npc.character_class, "value", "")
        if klass not in HIREABLE:
            return f"A {klass} is no blade for hire."
        cap = 3
        try:
            cap = self.engine.guild.companion_cap()
        except Exception:
            pass
        if len(cm.party) >= cap:
            return f"Your party is full ({cap} max)."
        signing, _ = self.cost(npc)
        if getattr(self.engine.player, "gold", 0) < signing:
            return f"You can't cover {npc.name}'s {signing}g signing fee."
        return ""

    # ---- the contract ----------------------------------------------

    def hire(self, npc_id: str, days: int = None) -> str:
        npc = self.engine.npc_manager.get_npc(npc_id)
        reason = self.can_hire(npc)
        if reason:
            return reason
        signing, wage = self.cost(npc)
        self.engine.player.gold -= signing
        day = self._day()
        npc.metadata["hire"] = {
            "wage": wage, "signing": signing, "hired_on": day,
            "paid_through": day,
            "term_end": (day + int(days)) if days else None,
            "missed": 0,
        }
        npc.metadata["seeking_party"] = False
        self.engine.companion_manager.party.append(npc_id)
        term = f" for {int(days)} days" if days else " an open salary"
        msg = (f"{npc.name} pockets your {signing}g and signs on{term} "
               f"— wage {wage}g a day.")
        self.engine.memory_manager.add_event(f"[Hire] {msg}")
        try:
            npc.add_memory(
                f"I took {self.engine.player.name}'s coin as a hireling.", 3)
        except Exception:
            pass
        return msg

    # ---- the nightly reckoning -------------------------------------

    def run_day(self, day: int = None) -> None:
        """Settle every hireling's wage for the day: pay them, end an
        expired term amiably, or — if the purse is empty past the grace —
        let them walk soured."""
        day = self._day() if day is None else day
        cm = self.engine.companion_manager
        for nid in list(cm.party):
            npc = self.engine.npc_manager.get_npc(nid)
            if npc is None:
                continue
            c = (getattr(npc, "metadata", {}) or {}).get("hire")
            if not c:
                continue
            if c.get("term_end") is not None and day >= c["term_end"]:
                self._leave(npc, f"{npc.name}'s contract is up; they take "
                                 f"their leave with a nod and a fair word.")
                continue
            if c.get("paid_through", -1) >= day:
                continue                     # already paid for today
            wage = c.get("wage", 0)
            if getattr(self.engine.player, "gold", 0) >= wage:
                self.engine.player.gold -= wage
                c["paid_through"] = day
                c["missed"] = 0
            else:
                c["missed"] = c.get("missed", 0) + 1
                if c["missed"] > GRACE_DAYS:
                    self._leave(npc, f"Unpaid one day too many, {npc.name} "
                                     f"spits, breaks the contract, and walks.",
                                sour=True)
                else:
                    self.engine.memory_manager.add_event(
                        f"[Hire] {npc.name} scowls about the wage you owe.")

    def _leave(self, npc, msg: str, sour: bool = False) -> None:
        cm = self.engine.companion_manager
        if npc.id in cm.party:
            cm.party.remove(npc.id)
        try:
            npc.metadata.pop("hire", None)
        except Exception:
            pass
        if sour:
            try:
                pid = self.engine.player.id
                npc.relationships[pid] = npc.get_relationship(pid) - 20
            except Exception:
                pass
        self.engine.memory_manager.add_event(f"[Hire] {msg}")

    # ---- parse the /hire command's optional term -------------------

    @staticmethod
    def parse_days(message: str):
        """`/hire` → None (open salary); `/hire 5` → 5 days."""
        parts = message.split()
        for p in parts[1:]:
            if p.isdigit():
                return int(p)
        return None
