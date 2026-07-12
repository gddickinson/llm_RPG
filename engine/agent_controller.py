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

`drive_agents(engine)` runs every agent hero once, from the turn
pipeline (advance_turn re-entrancy-guarded against nested ticks).
"""

import logging
import random
from contextlib import contextmanager

from engine import agent_nav as nav
from engine.agent_nav import _dist, _toward
from engine.agent_sense import (_is_hostile, _colocated, _healing_item,
                                _knows_heal, _can_shoot)

logger = logging.getLogger("llm_rpg.agent")

SIGHT = 8                                   # tiles an agent notices a foe
RANGED = 5                                  # tiles a bow can reach
LOW_HP = 0.4                                # heal / flee at or below this
SWARM_HP = 0.75                             # back off a pack below this


@contextmanager
def acting_as(engine, character):
    """Point `engine.player` at `character` for one action so the real
    player-action API operates on it, then restore the prior player.

    The building/dungeon a player is inside (`current_interior`/
    `current_dungeon`) is GLOBAL engine state, but a driven adventurer or
    away-hero stands on the OVERWORLD, not in that zone. Bug-fix
    2026-07-12c: when we drive someone who is NOT the owner of the current
    zone, neutralise the zone context for the duration so the whole action
    path (movement, the agent's `active_zone`, `_zone_plan`) treats them as
    being on the overworld they actually occupy — otherwise the driven
    character would `exit_building` the PLAYER out of their own interior,
    stranding them at the zone-local door tile (George: "entering a
    building keeps teleporting me")."""
    prev = engine.player
    engine.player = character
    swap = character is not prev and (
        getattr(engine, "current_interior", None) is not None
        or getattr(engine, "current_dungeon", None) is not None)
    if swap:
        saved_i = engine.current_interior
        saved_d = engine.current_dungeon
        engine.current_interior = None
        engine.current_dungeon = None
    try:
        yield
    finally:
        engine.player = prev
        if swap:
            engine.current_interior = saved_i
            engine.current_dungeon = saved_d


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
        self.recent = []          # a short trail of tiles (anti-oscillation)
        self._gd = None           # last distance to goal, to notice a stall
        self._stall = 0           # turns without getting closer to the goal
        self.social = True        # False for adventurer NPCs (no player state)

    # ---- perception --------------------------------------------

    def _foes_in_sight(self, engine, char):
        zone = nav.active_zone(engine)
        zname = getattr(zone, "name", None) if zone is not None else None
        out = []
        for npc in engine.npc_manager.npcs.values():
            if npc.id == char.id or not npc.is_active():
                continue
            if not _is_hostile(npc) or not _colocated(zname, npc):
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
        try:   # a full pack can't pick anything up — don't loop on it
            from engine.carry import can_carry
            if not can_carry(char):
                return None
        except Exception:
            pass
        x, y = char.position
        best, bd = None, r + 1
        try:
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    its = engine.world.get_items_at(x + dx, y + dy)
                    # real items only — a plain-string BODY MARKER is not
                    # loot (rob_body leaves it), so pursuing it loops forever
                    if its and any(hasattr(i, "id") for i in its):
                        d = max(abs(dx), abs(dy))
                        if d < bd:
                            best, bd = (x + dx, y + dy), d
        except Exception:
            return None
        return best

    def _friendly_near(self, engine, char, r: int = 7):
        """The nearest living, non-hostile, non-player soul ON OUR GRID —
        someone to talk to, take a quest from, or recruit (no chatting
        with folk sealed behind a building's walls)."""
        zone = nav.active_zone(engine)
        zname = getattr(zone, "name", None) if zone is not None else None
        best, bd = None, r + 1
        for npc in engine.npc_manager.npcs.values():
            if npc.id == char.id or not npc.is_active():
                continue
            if _is_hostile(npc) or (getattr(npc, "metadata", {})
                                    or {}).get("player_char"):
                continue
            if not _colocated(zname, npc):
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

    def _zone_plan(self, engine, char, zone):
        """Inside a building or dungeon. A BUILDING: make for the door and
        step back outside, so the away-hero resumes its life rather than
        freezing on unreachable overworld goals. A DUNGEON: prowl the
        walkable floor. Always a reachable step — never a frozen hero."""
        if getattr(engine, "current_interior", None) is not None:
            door = getattr(zone, "door", None) or \
                getattr(zone, "exit_pos", None)
            if door is None or tuple(char.position) == tuple(door):
                return ("exit_building",)
            step = nav.safe_step(engine, char, tuple(door), self.recent)
            return ("move", step) if step != (0, 0) else ("exit_building",)
        if self.goal is None or tuple(char.position) == tuple(self.goal) \
                or not nav.walkable(engine, char, self.goal):
            self.goal = nav.zone_roam(engine, char, zone, self.rng)
        step = nav.safe_step(engine, char, self.goal, self.recent)
        return ("move", step) if step != (0, 0) else ("wait",)

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
                step = nav.flee_step(engine, char, foes[0][0].position,
                                     self.recent)
                if step is not None:
                    return ("flee", step)
                # cornered with no heals — fall through and fight for it

        # 2. don't stand and trade blows when swarmed in melee
        if len(adj) >= 2 and hp < SWARM_HP:
            step = nav.flee_step(engine, char, adj[0].position, self.recent)
            if step is not None:
                return ("flee", step)

        # 2b. a PACK closing in (a lair/warband) — withdraw before it boxes
        # us in and butchers us; only a valiant hero at full health wades in
        pack = [f for f, d in foes if d <= 4]
        if len(pack) >= 3 and not (disp == "valiant" and hp > SWARM_HP):
            step = nav.flee_step(engine, char, pack[0].position, self.recent)
            if step is not None:
                return ("flee", step)

        # a CAUTIOUS hero avoids a fight it hasn't been forced into
        avoid = disp == "cautious"

        # 3. engage a focused target — shoot if we can, else close
        target = self._focus(foes)
        if target is not None:
            d = _dist(char.position, target.position)
            if avoid and d > 1:          # a cautious hero keeps its distance
                step = nav.flee_step(engine, char, target.position,
                                     self.recent)
                if step is not None:
                    return ("flee", step)
                # backed into a corner — a cautious hero still defends itself
            if d <= 1:
                return ("attack", target)
            if _can_shoot(char) and d <= RANGED:
                return ("shoot", target)
            self.goal = target.position
            return ("move", nav.safe_step(engine, char, target.position,
                                          self.recent))

        # grab loot right at our feet before wandering off to socialize
        if self._nearest_loot(engine, char, r=0) == tuple(char.position):
            return ("loot",)

        # inside a building/dungeon: leave or prowl, never freeze on an
        # unreachable overworld goal
        zone = nav.active_zone(engine)
        if zone is not None:
            return self._zone_plan(engine, char, zone)

        # 4. a life among people — talk, take quests, gather a party.
        # (adventurer NPCs run social=False: they don't touch the PLAYER's
        # quest log or party — they fight, loot and roam on their own)
        if self.social:
            social = self._social_plan(engine, char, disp)
            if social is not None:
                return social

        # 5. pursue a quest we've taken on — go where it wants us
        if self.social and disp != "explorer":
            qgoal = self._quest_goal(engine, char)
            if qgoal is not None and tuple(char.position) != tuple(qgoal):
                return ("move", nav.safe_step(engine, char, qgoal,
                                              self.recent))

        # 6. grab loot off the ground (a GREEDY hero looks wider)
        loot = self._nearest_loot(engine, char, r=8 if disp == "greedy" else 5)
        if loot is not None:
            if loot == tuple(char.position):
                return ("loot",)
            return ("move", nav.safe_step(engine, char, loot, self.recent))

        # 7. explore a class-flavoured place; abandon one we can't close on
        if self.goal is None or char.position == self.goal or self._stall > 8:
            if self.goal_name is not None:
                self.visited.add(self.goal_name)
            self.goal_name, self._stall, self._gd = None, 0, None
            self.goal = self._named_goal(engine, char) \
                or self._pick_goal(engine, char)
        gd = _dist(char.position, self.goal)
        self._stall = self._stall + 1 if self._gd is not None and gd >= self._gd else 0
        self._gd = gd
        step = nav.safe_step(engine, char, self.goal, self.recent)
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
        # walk over to a NEW face worth meeting — but once greeted, leave
        # them be (re-approaching a greeted friend forever oscillated)
        if friend.id not in self.greeted or self._offers(engine, friend):
            return ("move", nav.safe_step(engine, char, friend.position,
                                          self.recent))
        return None

    def _offers(self, engine, friend) -> bool:
        """Still a reason to walk over — an untaken quest or a recruitable
        ally — even if we've already said hello."""
        qm = getattr(engine, "quest_manager", None)
        if qm and qm.offered_by(friend.id):
            return True
        try:
            return self._room_in_party(engine) and \
                engine.companion_manager.can_recruit(friend) == ""
        except Exception:
            return False

    # ---- act (execute through the real player-action route) -----

    def _deed(self, engine, char, text: str) -> None:
        """A line the away-hero writes into the record, so the player can
        see what it got up to (memory + the ledger they review later)."""
        try:
            engine.memory_manager.add_event(f"[Away] {char.name} {text}")
        except Exception:
            pass

    def take_turn(self, engine, char) -> str:
        self.recent = (self.recent + [tuple(char.position)])[-3:]
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
            elif k == "exit_building":
                try:
                    engine.exit_building()
                    if self.goal_name:            # don't head straight back
                        self.visited.add(self.goal_name)
                    self.goal = self.goal_name = None
                    self._deed(engine, char, "stepped back outside.")
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
