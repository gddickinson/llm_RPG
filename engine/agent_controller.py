"""Agent-driven characters (M.2) — a hero played by an autonomous
controller through the SAME player-action route a human uses.

Goal/utility-driven and LLM-free per tick (the DM's cached-plan
discipline, and the per-tick-LLM ban): each turn the controller sees
the world through the character's eyes, PICKS the most useful action
from a small policy — fight an adjacent foe, close on a nearby threat,
else wander toward a cached goal — and EXECUTES it via the engine's
real player actions, temporarily acting AS that character. This is
what lets an agent join the world (M.2) and keep a hero living when
its human is away (M.3), instead of the character vanishing or being a
puppet of the ambient NPC AI.

`drive_agents(engine)` runs every agent-controlled roster hero once;
it is called from the turn pipeline, where `advance_turn` is
re-entrancy-guarded so a hero's move doesn't cascade a nested tick.
"""

import logging
import random
from contextlib import contextmanager

logger = logging.getLogger("llm_rpg.agent")

SIGHT = 8                                   # tiles an agent notices a foe
_HOSTILE = ("brigand", "troll", "monster")  # matches the game's foe check


def _is_hostile(npc) -> bool:
    return getattr(getattr(npc, "character_class", None), "value", "") \
        in _HOSTILE


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _toward(frm, to):
    return ((to[0] > frm[0]) - (to[0] < frm[0]),
            (to[1] > frm[1]) - (to[1] < frm[1]))


@contextmanager
def acting_as(engine, character):
    """Point `engine.player` at `character` for one action so the real
    player-action API operates on it, then restore the prior player."""
    prev = engine.player
    engine.player = character
    try:
        yield
    finally:
        engine.player = prev


class AgentController:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.goal = None          # a cached destination tile

    # ---- policy (decide, no side effects) -----------------------

    def _nearest_foe(self, engine, char):
        best, bd = None, SIGHT + 1
        for npc in engine.npc_manager.npcs.values():
            if npc.id == char.id or not npc.is_active():
                continue
            if not _is_hostile(npc):
                continue
            d = _dist(char.position, npc.position)
            if d < bd:
                best, bd = npc, d
        return best

    def _pick_goal(self, engine, char):
        w = engine.world.map
        x, y = char.position
        return (max(0, min(w.width - 1, x + self.rng.randint(-6, 6))),
                max(0, min(w.height - 1, y + self.rng.randint(-6, 6))))

    def decide(self, engine, char):
        """The utility choice — returns a plan, executes nothing.
        ('attack', foe) | ('move', (dx,dy)) | ('wait',)."""
        foe = self._nearest_foe(engine, char)
        if foe is not None:
            if _dist(char.position, foe.position) <= 1:
                return ("attack", foe)
            self.goal = foe.position
            return ("move", _toward(char.position, foe.position))
        if self.goal is None or char.position == self.goal:
            self.goal = self._pick_goal(engine, char)
        step = _toward(char.position, self.goal)
        return ("move", step) if step != (0, 0) else ("wait",)

    # ---- act (execute through the real player-action route) -----

    def take_turn(self, engine, char) -> str:
        plan = self.decide(engine, char)
        with acting_as(engine, char):
            if plan[0] == "attack":
                engine.attack_character(plan[1].name)
            elif plan[0] == "move":
                dx, dy = plan[1]
                if dx or dy:
                    engine.move_player(dx, dy)
        return plan[0]


def _driver_for(controller, char) -> AgentController:
    if getattr(controller, "driver", None) is None:
        controller.driver = AgentController(
            seed=sum(ord(c) for c in getattr(char, "id", "hero")))
    return controller.driver


def drive_agents(engine) -> None:
    """Run every agent-controlled roster hero once this turn."""
    roster = getattr(engine, "roster", None)
    if roster is None:
        return
    for char in roster.agents():
        ctrl = roster.controller_for(char)
        if ctrl is None:
            continue
        try:
            _driver_for(ctrl, char).take_turn(engine, char)
        except Exception as e:
            logger.warning(f"Agent {getattr(char, 'id', '?')}: {e}")
