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
    """A drawn bow is no use without arrows — an agent that dry-fires an
    empty quiver forever just stands and 'shoots' (bug-fix 2026-07-12).
    Require matching ammo unless the weapon is thrown."""
    try:
        from characters.equipment import equipped_weapon
        from items.item import Item
        w = equipped_weapon(char)
        if w is None or not w.is_ranged_weapon():
            return False
        if getattr(w, "weapon_kind", "") == "thrown":
            return True                       # thrown needs no ammo
        ammo = getattr(w, "ammo_type", "")
        if not ammo:
            return True
        return any(isinstance(it, Item) and it.is_ammo()
                   and it.ammo_type == ammo and it.quantity > 0
                   for it in getattr(char, "inventory", []))
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
        # a hero with a life beyond combat (2026-07-12):
        self.greeted = set()      # NPCs we've already struck up a chat with
        self.visited = set()      # named places we've already sought out
        self.goal_name = None     # the place we're currently journeying to

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

    def _friendly_near(self, engine, char, r: int = 7):
        """The nearest living, non-hostile, non-player soul — someone to
        talk to, take a quest from, or recruit."""
        best, bd = None, r + 1
        for npc in engine.npc_manager.npcs.values():
            if npc.id == char.id or not npc.is_active():
                continue
            if _is_hostile(npc) or (getattr(npc, "metadata", {})
                                    or {}).get("player_char"):
                continue
            d = _dist(char.position, npc.position)
            if d < bd:
                best, bd = npc, d
        return best

    def _room_in_party(self, engine) -> bool:
        try:
            cm = engine.companion_manager
            cap = engine.guild.companion_cap() if hasattr(engine, "guild") \
                and hasattr(engine.guild, "companion_cap") else 3
            return len(cm.party) < cap
        except Exception:
            return False

    def _quest_goal(self, engine, char):
        """A place an active quest wants us — a target NPC's tile or a
        named objective location — so the hero pursues what it took on."""
        qm = getattr(engine, "quest_manager", None)
        if qm is None:
            return None
        for q in qm.active():
            for obj in q.objectives:
                tgt = obj.target or ""
                npc = engine.npc_manager.npcs.get(tgt)
                if npc is not None and npc.is_active():
                    return npc.position
                for loc in engine.world.locations:
                    if loc.name == tgt:
                        return loc.center()
        return None

    # class → the kinds of place a hero of that calling is drawn to (P-agent)
    _CLASS_DRAW = {
        "warrior": ("lair", "warren", "den", "keep", "cave", "ruin"),
        "barbarian": ("lair", "den", "cave", "warren"),
        "paladin": ("keep", "temple", "shrine", "lair"),
        "wizard": ("tower", "stones", "shrine", "barrow", "temple"),
        "sorcerer": ("tower", "stones", "barrow"),
        "warlock": ("barrow", "stones", "hollow", "tower"),
        "rogue": ("cave", "market", "ruin", "barrow", "hollow"),
        "ranger": ("hollow", "camp", "cave", "forest", "ruin"),
        "druid": ("hollow", "shrine", "stones", "forest"),
        "cleric": ("temple", "shrine", "chapel"),
        "monk": ("temple", "shrine", "stones"),
        "bard": ("tavern", "market", "inn", "village"),
    }

    def _named_goal(self, engine, char):
        """A class-flavoured destination: the nearest UNVISITED named place
        the hero's calling draws it to, else any unvisited place."""
        cls = getattr(getattr(char, "character_class", None), "value", "")
        draw = self._CLASS_DRAW.get(cls, ())
        px, py = char.position
        pref, other = [], []
        for loc in getattr(engine.world, "locations", []):
            if loc.name in self.visited:
                continue
            cx, cy = loc.center()
            d = (cx - px) ** 2 + (cy - py) ** 2
            low = loc.name.lower()
            (pref if any(k in low for k in draw) else other).append((d, loc))
        pool = pref or other
        if not pool:
            return None
        pool.sort(key=lambda t: t[0])
        loc = pool[0][1]
        self.goal_name = loc.name
        return loc.center()

    def _disposition(self, engine, char) -> str:
        """How the player asked the hero to behave in their absence."""
        try:
            from engine.settings import get_setting
            d = get_setting(char, "disposition")
            if d:
                return str(d).lower()
        except Exception:
            pass
        return (getattr(char, "metadata", {}) or {}).get("disposition",
                                                         "balanced")

    ROAM = 10                 # how far an idle away hero strikes out

    def _pick_goal(self, engine, char):
        # an away hero potters back toward home (M.3); otherwise strike
        # out on a wider foray so it visibly explores rather than jitter
        if self.home is not None and tuple(char.position) != tuple(self.home):
            return tuple(self.home)
        w = engine.world.map
        x, y = char.position
        r = self.ROAM
        return (max(0, min(w.width - 1, x + self.rng.randint(-r, r))),
                max(0, min(w.height - 1, y + self.rng.randint(-r, r))))

    # ---- policy (decide, no side effects) -----------------------

    def decide(self, engine, char):
        """A hero with a life: survive, fight when it must, but also chat,
        take and pursue quests, gather a party, and explore toward the
        places its calling draws it — weighted by the disposition the
        player set. Returns a plan; executes nothing."""
        hp = char.hp / max(1, char.max_hp)
        disp = self._disposition(engine, char)
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

        # a CAUTIOUS hero avoids a fight it hasn't been forced into
        avoid = disp == "cautious"

        # 3. engage a focused target — shoot if we can, else close
        target = self._focus(foes)
        if target is not None:
            d = _dist(char.position, target.position)
            if avoid and d > 1:          # a cautious hero keeps its distance
                return ("flee", _away(char.position, target.position))
            if d <= 1:
                return ("attack", target)
            if _can_shoot(char) and d <= RANGED:
                return ("shoot", target)
            self.goal = target.position
            return ("move", _toward(char.position, target.position))

        # grab loot right at our feet before wandering off to socialize
        if self._nearest_loot(engine, char, r=0) == tuple(char.position):
            return ("loot",)

        # 4. a life among people — talk, take quests, gather a party
        social = self._social_plan(engine, char, disp)
        if social is not None:
            return social

        # 5. pursue a quest we've taken on — go where it wants us
        if disp != "explorer":
            qgoal = self._quest_goal(engine, char)
            if qgoal is not None and tuple(char.position) != tuple(qgoal):
                return ("move", _toward(char.position, qgoal))

        # 6. grab loot off the ground (a GREEDY hero looks wider)
        loot = self._nearest_loot(engine, char, r=8 if disp == "greedy" else 5)
        if loot is not None:
            if loot == tuple(char.position):
                return ("loot",)
            return ("move", _toward(char.position, loot))

        # 7. explore toward a class-flavoured place (mark it visited on arrival)
        if self.goal is None or char.position == self.goal:
            if self.goal_name and self.goal is not None:
                self.visited.add(self.goal_name)
                self.goal_name = None
            self.goal = self._named_goal(engine, char) \
                or self._pick_goal(engine, char)
        step = _toward(char.position, self.goal)
        return ("move", step) if step != (0, 0) else ("wait",)

    def _social_plan(self, engine, char, disp):
        """Near someone? Take their quest, recruit them, or say hello —
        biased by disposition (a SOCIABLE hero seeks people out)."""
        reach = 8 if disp == "sociable" else 4
        friend = self._friendly_near(engine, char, r=reach)
        if friend is None:
            return None
        adjacent = _dist(char.position, friend.position) <= 1
        if adjacent:
            qm = getattr(engine, "quest_manager", None)
            offered = qm.offered_by(friend.id) if qm else []
            if offered:
                return ("accept_quest", offered[0], friend)
            if self._room_in_party(engine):
                try:
                    if engine.companion_manager.can_recruit(friend) == "":
                        return ("recruit", friend)
                except Exception:
                    pass
            if friend.id not in self.greeted:
                return ("talk", friend)
            return None
        # walk over to a new face worth meeting
        if friend.id not in self.greeted or disp == "sociable":
            return ("move", _toward(char.position, friend.position))
        return None

    # ---- act (execute through the real player-action route) -----

    def _deed(self, engine, char, text: str) -> None:
        """A line the away-hero writes into the record, so the player can
        see what it got up to (memory + the ledger they review later)."""
        try:
            engine.memory_manager.add_event(f"[Away] {char.name} {text}")
        except Exception:
            pass

    def take_turn(self, engine, char) -> str:
        plan = self.decide(engine, char)
        # keep the hero's current aim visible to the player (reviewable)
        char.metadata["agent_goal"] = self.goal_name or (
            "heading somewhere" if plan[0] == "move" else plan[0])
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
            elif k == "talk":
                npc = plan[1]
                self.greeted.add(npc.id)
                try:
                    engine.dialog_system.player_to_npc(npc.id)
                    self._deed(engine, char, f"fell to talking with {npc.name}.")
                except Exception:
                    pass
            elif k == "accept_quest":
                quest, npc = plan[1], plan[2]
                if engine.quest_manager.accept_quest(quest.id):
                    self._deed(engine, char,
                               f"took up \"{quest.title}\" from {npc.name}.")
            elif k == "recruit":
                npc = plan[1]
                try:
                    engine.recruit(npc.id)
                    if npc.id in engine.companion_manager.party:
                        self._deed(engine, char,
                                   f"recruited {npc.name} to the party.")
                except Exception:
                    pass
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
