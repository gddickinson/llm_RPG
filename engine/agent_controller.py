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
from engine import agent_goals as agoals
from engine import agent_trade as agtrade
from engine.agent_nav import _dist, _toward
from engine.agent_sense import (_is_hostile, _colocated, _healing_item,
                                _knows_heal, _can_shoot, _provisioned,
                                _attack_spell, _gatherable, _learn_item,
                                _can_pray, _can_stash, _claim_target,
                                _thirsty, _hungry, _tired, _drink_item,
                                _food_item, _adjacent_water, _water_toward)

logger = logging.getLogger("llm_rpg.agent")

SIGHT = 8                                   # tiles an agent notices a foe
RANGED = 5                                  # tiles a bow can reach
LOW_HP = 0.4                                # heal / flee at or below this
REST_HP = 0.55                              # top up / rest when safe below this
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
        self.indoor = None        # T4.1 an active enter→act→exit building task
        self._indoor_cd = 0       # cooldown so it never bounces in and out

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
        places its calling — or the AMBITION the player set (M.9d) — draws
        it, weighted by the disposition. Returns a plan; executes nothing."""
        hp = char.hp / max(1, char.max_hp)
        disp = agoals.disposition(char)
        foes = self._foes_in_sight(engine, char)
        adj = [f for f, d in foes if d <= 1]

        # T4.1: mid a building visit (rest/trade inside) — do it, then leave;
        # a hard cooldown ticks down so the hero never bounces in and out
        from engine import agent_building as abld
        abld.tick_cooldown(self)
        if self.indoor is not None and nav.active_zone(engine) is not None \
                and not adj:
            plan = abld.inside_plan(self, engine, char)
            if plan is not None:
                return plan

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
            # a caster fights with MAGIC (M.8c): the best damage spell it
            # knows, can pay for, and that reaches — before blade or bow
            spell = _attack_spell(char, d)
            if spell is not None:
                return ("cast", spell, target)
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

        # 3b. tend the body between fights (M.8a + M.10a needs) — a SAFE hero
        # acts on a NEED before it's dire: slake thirst (a drink, or step to
        # the river and drink), eat when hungry, mend HP, and camp when tired
        # — so it never dies of thirst/hunger/attrition untried.
        if not foes:
            # thirst is the fastest clock — deal with it first
            if _thirsty(char):
                drink = _drink_item(char)
                if drink is not None:
                    return ("drink", drink)
                if _adjacent_water(engine, char):
                    return ("drink", None)
                water = _water_toward(engine, char)
                if water is not None:
                    return ("move", nav.safe_step(engine, char, water,
                                                  self.recent))
            if _hungry(char):
                food = _food_item(char)
                if food is not None:
                    return ("eat", food)
            if hp < REST_HP:
                pot = _healing_item(char)
                if pot is not None:
                    return ("heal_potion", pot)
                if _knows_heal(char):
                    return ("heal_spell",)
                # a REAL camp needs provisions, else it's a fruitless doze
                # we'd repeat every night
                if self.social and hp < LOW_HP \
                        and nav.active_zone(engine) is None \
                        and _provisioned(char):
                    return ("rest",)
            # merely tired (not bleeding) — camp if it'll actually mend us
            if _tired(char) and self.social \
                    and nav.active_zone(engine) is None \
                    and _provisioned(char):
                return ("rest",)

        # T4.1: step into a nearby building for a proper indoor task — a
        # well-rested INN sleep when badly hurt, or selling junk to an INDOOR
        # merchant — that the building-skirting hero could never reach before
        if not foes:
            intent = abld.enter_intent(self, engine, char)
            if intent is not None:
                return ("enter_building", intent[0], intent[1])

        # 3c. gather from the land (M.8d) — a node or a rich forest/swamp we
        # stand on: raws, and from a forest FOOD for the M.8a camp
        if not foes and _gatherable(engine, char):
            return ("forage",)

        # 3d. worship & self-betterment (M.8e) — study a tome/manual we carry
        # (learn a spell / gain a stat), or pray at a shrine for a boon
        if not foes:
            tome = _learn_item(char)
            if tome is not None:
                return ("study", tome)
            if self.social and _can_pray(engine, char):
                return ("pray",)

        # 3e. homesteading (M.8f) — a full-packed hero with a home shelves its
        # surplus in the chest (frees the pack); at a claimable derelict it
        # can afford, it buys in
        if self.social and not foes:
            if _can_stash(engine, char):
                return ("stash",)
            if _claim_target(engine, char) is not None:
                return ("claim_home",)

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
        greedy = disp == "greedy" or agoals.ambition(char) == "wealth"
        loot = self._nearest_loot(engine, char, r=8 if greedy else 5)
        if loot is not None:
            if loot == tuple(char.position):
                return ("loot",)
            return ("move", nav.safe_step(engine, char, loot, self.recent))

        # 7. explore a class-flavoured place; abandon one we can't close on
        if self.goal is None or char.position == self.goal or self._stall > 8:
            if self.goal_name is not None:
                self.visited.add(self.goal_name)
            self.goal_name, self._stall, self._gd = None, 0, None
            self.goal = agoals.named_goal(self, engine, char) \
                or agoals.pick_goal(self, engine, char)
        gd = _dist(char.position, self.goal)
        self._stall = self._stall + 1 if self._gd is not None and gd >= self._gd else 0
        self._gd = gd
        step = nav.safe_step(engine, char, self.goal, self.recent)
        return ("move", step) if step != (0, 0) else ("wait",)

    def _social_plan(self, engine, char, disp):
        """Near someone? Take their quest, recruit them, or say hello —
        biased by disposition (a SOCIABLE hero seeks people out)."""
        outgoing = disp == "sociable" or agoals.ambition(char) == "fellowship"
        reach = 8 if outgoing else 4
        friend = self._friendly_near(engine, char, r=reach)
        if friend is None:
            return None
        adjacent = _dist(char.position, friend.position) <= 1
        if adjacent:
            # deal with a merchant we're standing by (M.8b): clear junk for
            # coin, buy the potion/ammo we're short of
            from engine.conversation import is_merchant
            if is_merchant(friend) \
                    and agtrade.wants_to_trade(engine, char, friend):
                return ("trade", friend)
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
        if friend.id not in self.greeted or self._offers(engine, char, friend):
            return ("move", nav.safe_step(engine, char, friend.position,
                                          self.recent))
        return None

    def _offers(self, engine, char, friend) -> bool:
        """Still a reason to walk over — an untaken quest, a recruitable
        ally, or a merchant we've goods to trade — even after we've said
        hello."""
        qm = getattr(engine, "quest_manager", None)
        if qm and qm.offered_by(friend.id):
            return True
        try:
            from engine.conversation import is_merchant
            if is_merchant(friend) \
                    and agtrade.wants_to_trade(engine, char, friend):
                return True
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
        from engine.agent_exec import execute
        execute(self, engine, char, plan)
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
