"""Romance & rivalry (P20.6) — relationship TYPES, not one scalar.

The player's bond with an NPC was a single affinity number. This gives it a
SHAPE. Type `/court` while talking to someone you've grown close to and, if
their regard is warm enough, you climb a ladder — courting → sweetheart →
betrothed → married — a real, named relationship that rides the save. Court
a second while another is already your sweetheart and the first grows
JEALOUS, their regard cooling and a bitter word going round. And the ledger
runs the other way too: someone whose regard for you has curdled deep
enough becomes a RIVAL, and will not be wooed.

The weddings and the jealousies are `[Legend]` beats, so they write
themselves into the P20.5 chronicle; a spouse quietly provides, a small
gift most days. Heuristic, deterministic; every thread lives on the NPCs'
own `metadata`, so a marriage survives a save.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.romance")

LADDER = ["courting", "sweetheart", "betrothed", "married"]
GATE = {"courting": 25, "sweetheart": 50, "betrothed": 70, "married": 85}
RIVAL_AT = -50
PARTNERED = ("sweetheart", "betrothed", "married")

_LINES = {
    "courting": "You begin to court {name}.",
    "sweetheart": "{name} and you are sweethearts now.",
    "betrothed": "{name} and you are betrothed!",
    "married": "You and {name} are wed — the realm has a new couple.",
}


def stage_of(npc):
    return (getattr(npc, "metadata", {}) or {}).get("romance")


def is_rival(npc) -> bool:
    return stage_of(npc) == "rival"


def spouse_of_player(engine):
    for npc in engine.npc_manager.npcs.values():
        if stage_of(npc) == "married" and npc.is_active():
            return npc
    return None


def _partners(engine, exclude_id=None):
    return [n for n in engine.npc_manager.npcs.values()
            if n.is_active() and n.id != exclude_id
            and stage_of(n) in PARTNERED]


def court(engine, npc) -> str:
    """The /court action — advance one rung if regard allows."""
    player = engine.player
    cur = stage_of(npc)
    if cur == "rival":
        return f"{npc.name} wants nothing to do with you."
    if cur == "married":
        return f"You and {npc.name} are already wed."
    rel = npc.get_relationship(player.id)
    nxt = LADDER[LADDER.index(cur) + 1] if cur in LADDER else LADDER[0]
    if rel < GATE[nxt]:
        npc.modify_relationship(player.id, -2)   # a clumsy advance cools it
        return (f"{npc.name} isn't ready for that — win warmer regard "
                f"first.")
    if nxt == "married":
        other = spouse_of_player(engine)
        if other is not None and other.id != npc.id:
            return f"You are already wed to {other.name}."
    jealous = _stir_jealousy(engine, npc) if nxt in PARTNERED else []
    npc.metadata["romance"] = nxt
    npc.modify_relationship(player.id, 6)
    line = _LINES[nxt].format(name=npc.name)
    engine.memory_manager.add_event(f"[Legend] {line}")
    for jline in jealous:
        engine.memory_manager.add_event(f"[Realm] {jline}")
    return line


def _stir_jealousy(engine, courting_npc):
    """Existing partners cool when you court another."""
    lines = []
    for other in _partners(engine, exclude_id=courting_npc.id):
        other.modify_relationship(engine.player.id, -15)
        if stage_of(other) == "married":
            other.metadata["romance"] = "betrothed"   # a marriage strained
        lines.append(f"{other.name} hears you courting {courting_npc.name} "
                     f"and burns with jealousy.")
    return lines


def provoke_rival(engine, npc) -> bool:
    """A deeply-soured NPC becomes a declared rival (passive/threshold)."""
    if stage_of(npc) in PARTNERED or stage_of(npc) == "married":
        return False
    if npc.get_relationship(engine.player.id) <= RIVAL_AT \
            and stage_of(npc) != "rival":
        npc.metadata["romance"] = "rival"
        engine.memory_manager.add_event(
            f"[Legend] {npc.name} has become your sworn rival.")
        return True
    return False


class RomanceSystem:
    """Nightly upkeep: a spouse provides, and grudges harden into rivalry."""

    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    def run_day(self) -> int:
        acted = 0
        spouse = spouse_of_player(self.engine)
        if spouse is not None and self.rng.random() < 0.5:
            try:
                self.engine.player.gold += self.rng.randint(3, 9)
            except Exception:
                pass
            self.engine.memory_manager.add_event(
                f"[Realm] {spouse.name}, your spouse, sets a little by for you.")
            acted += 1
        for npc in list(self.engine.npc_manager.npcs.values()):
            if npc.is_active() and provoke_rival(self.engine, npc):
                acted += 1
        return acted
