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
RANGED = 5                                  # tiles a bow can reach
LOW_HP = 0.4                                # heal / flee at or below this
SWARM_HP = 0.75                             # back off a pack below this
_HOSTILE = ("brigand", "troll", "monster")  # matches the game's foe check


def _is_hostile(npc) -> bool:
    return getattr(getattr(npc, "character_class", None), "value", "") \
        in _HOSTILE


def _dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _toward(frm, to):
    return ((to[0] > frm[0]) - (to[0] < frm[0]),
            (to[1] > frm[1]) - (to[1] < frm[1]))


def _away(frm, to):
    return ((frm[0] > to[0]) - (frm[0] < to[0]),
            (frm[1] > to[1]) - (frm[1] < to[1]))


def _healing_item(char):
    """A drinkable in the bag that mends wounds (id-matched — the heal
    payload isn't on `use_effect`)."""
    for it in getattr(char, "inventory", []):
        try:
            if not it.is_consumable():
                continue
        except Exception:
            continue
        iid = getattr(it, "id", "").lower()
        if "potion" in iid or "heal" in iid or "remedy" in iid:
            return it
    return None


def _knows_heal(char) -> bool:
    m = getattr(char, "metadata", {}) or {}
    return "heal" in m.get("spells_known", []) and m.get("mana", 0) >= 3


def _can_shoot(char) -> bool:
    try:
        from characters.equipment import equipped_weapon
        w = equipped_weapon(char)
        return w is not None and w.is_ranged_weapon()
    except Exception:
        return False


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
        self.target_id = None     # the foe we're focusing
        self.home = None          # M.3 potter-around tile while away

    # ---- perception --------------------------------------------

    def _foes_in_sight(self, engine, char):
        out = []
        for npc in engine.npc_manager.npcs.values():
            if npc.id == char.id or not npc.is_active():
                continue
            if not _is_hostile(npc):
                continue
            d = _dist(char.position, npc.position)
            if d <= SIGHT:
                out.append((npc, d))
        out.sort(key=lambda t: t[1])
        return out

    def _focus(self, foes):
        """Keep hammering one target while it lives and is in sight —
        finishing a foe beats spreading damage around."""
        if self.target_id:
            cur = next((f for f, _ in foes if f.id == self.target_id), None)
            if cur is not None:
                return cur
        self.target_id = foes[0][0].id if foes else None
        return foes[0][0] if foes else None

    def _nearest_loot(self, engine, char, r: int = 5):
        x, y = char.position
        best, bd = None, r + 1
        try:
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if engine.world.get_items_at(x + dx, y + dy):
                        d = max(abs(dx), abs(dy))
                        if d < bd:
                            best, bd = (x + dx, y + dy), d
        except Exception:
            return None
        return best

    def _pick_goal(self, engine, char):
        # an away hero potters back toward home (M.3); otherwise roam
        if self.home is not None and tuple(char.position) != tuple(self.home):
            return tuple(self.home)
        w = engine.world.map
        x, y = char.position
        return (max(0, min(w.width - 1, x + self.rng.randint(-6, 6))),
                max(0, min(w.height - 1, y + self.rng.randint(-6, 6))))

    # ---- policy (decide, no side effects) -----------------------

    def decide(self, engine, char):
        """Utility choice, in priority order — survive, don't get
        swarmed, focus a foe (ranged if able), loot, then wander.
        Returns a plan; executes nothing."""
        hp = char.hp / max(1, char.max_hp)
        foes = self._foes_in_sight(engine, char)
        adj = [f for f, d in foes if d <= 1]

        # 1. survive — heal if we can, else run from the nearest threat
        if hp <= LOW_HP:
            pot = _healing_item(char)
            if pot is not None:
                return ("heal_potion", pot)
            if _knows_heal(char):
                return ("heal_spell",)
            if foes:
                return ("flee", _away(char.position, foes[0][0].position))

        # 2. don't stand and trade blows when swarmed in melee
        if len(adj) >= 2 and hp < SWARM_HP:
            return ("flee", _away(char.position, adj[0].position))

        # 3. engage a focused target — shoot if we can, else close
        target = self._focus(foes)
        if target is not None:
            d = _dist(char.position, target.position)
            if d <= 1:
                return ("attack", target)
            if _can_shoot(char) and d <= RANGED:
                return ("shoot", target)
            self.goal = target.position
            return ("move", _toward(char.position, target.position))

        # 4. a light objective — grab loot off the ground
        loot = self._nearest_loot(engine, char)
        if loot is not None:
            if loot == tuple(char.position):
                return ("loot",)
            return ("move", _toward(char.position, loot))

        # 5. wander toward a cached goal
        if self.goal is None or char.position == self.goal:
            self.goal = self._pick_goal(engine, char)
        step = _toward(char.position, self.goal)
        return ("move", step) if step != (0, 0) else ("wait",)

    # ---- act (execute through the real player-action route) -----

    def take_turn(self, engine, char) -> str:
        plan = self.decide(engine, char)
        with acting_as(engine, char):
            k = plan[0]
            if k == "attack":
                engine.attack_character(plan[1].name)
            elif k == "shoot":
                engine.shoot_ranged(plan[1].name)
            elif k == "heal_potion":
                engine.use_item(plan[1].name)
            elif k == "heal_spell":
                engine.cast_spell("heal")
            elif k == "loot":
                engine.pickup_item()
            elif k in ("move", "flee"):
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
    """Run every character an agent should drive this turn: the agent-
    controlled roster heroes, AND any human hero whose player has
    stepped away (M.3) — including the active player."""
    roster = getattr(engine, "roster", None)
    if roster is None:
        return
    for char in roster.characters:
        ctrl = roster.controller_for(char)
        if ctrl is None:
            continue
        if not (ctrl.is_agent or (ctrl.is_human and ctrl.away)):
            continue
        try:
            driver = _driver_for(ctrl, char)
            driver.home = ctrl.away_home if ctrl.away else None
            driver.take_turn(engine, char)
        except Exception as e:
            logger.warning(f"Agent {getattr(char, 'id', '?')}: {e}")
