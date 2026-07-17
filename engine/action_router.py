"""Action router — dispatches NPC actions to handlers.

Receives parsed action data from the LLM/heuristic provider and routes
to combat, economy, social, movement, interaction, rest, work handlers.
"""

import logging
import random
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger("llm_rpg.action_router")


_DIRECTIONS = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "northeast": (1, -1), "northwest": (-1, -1),
    "southeast": (1, 1), "southwest": (-1, 1),
    "up": (0, -1), "down": (0, 1), "right": (1, 0), "left": (-1, 0),
    "forward": (0, -1), "backward": (0, 1),
    "forwards": (0, -1), "backwards": (0, 1),
}

# When a scheduled NPC has arrived at its location it ambles around it (mills
# about) rather than freezing, so idle towns keep moving (George). Bounded so it
# never wanders off its post; an occasional pause keeps the amble natural.
LOITER_RADIUS = 3
LOITER_PAUSE_CHANCE = 0.15
_LOITER_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1),
                (1, 1), (-1, -1), (1, -1), (-1, 1)]


class ActionRouter:
    """Route LLM-decided actions to the right handler."""

    def __init__(self, engine):
        self.engine = engine

    def process(self, npc, action_data: Dict[str, str]) -> bool:
        # Skip the turn if paralyzed/stunned
        try:
            from characters.status_effects import can_act, has_effect
            if not can_act(npc):
                self.engine.memory_manager.add_event(
                    f"{npc.name} cannot move.")
                return False
            # Prone creatures spend the action standing up (P12.2)
            if has_effect(npc, "prone"):
                from characters.status_effects import remove_effect
                remove_effect(npc, "prone")
                self.engine.memory_manager.add_event(
                    f"{npc.name} scrambles back to their feet.")
                return False
            # Slowed creatures act every other turn (P11.4)
            if has_effect(npc, "slowed"):
                skip = not npc.metadata.get("slow_skip", False)
                npc.metadata["slow_skip"] = skip
                if skip:
                    return False
        except Exception:
            pass

        action = (action_data.get("action") or "").lower()
        target = action_data.get("target") or ""
        dialog = action_data.get("dialog") or ""
        thoughts = action_data.get("thoughts") or ""
        emotion = action_data.get("emotion") or ""
        goal_update = action_data.get("goal_update") or ""

        # Emotional / goal updates
        if emotion:
            npc.personality["current_emotion"] = emotion
        if goal_update and goal_update.lower() not in ("none", ""):
            self._update_goals(npc, goal_update)

        # Dialog comes through regardless of action
        if dialog and dialog.lower() != "none":
            self.engine.memory_manager.add_event(f"{npc.name} says: \"{dialog}\"")
            npc.add_memory(f"I said: \"{dialog}\"", 1)

        # Action dispatch
        if action in ("move", "walk", "run", "approach", "go", "patrol"):
            return self._handle_move(npc, target, action_data.get("activity", ""))
        if action in ("attack", "fight", "strike", "slash", "stab", "shoot", "cast"):
            return self.engine.combat_system.npc_attack(npc, target, action)
        if action in ("buy", "sell", "trade", "offer", "pay", "gift", "give"):
            return self.engine.economy_system.handle(npc, target, action)
        if action in ("open", "close", "examine", "search", "take",
                      "drop", "use", "activate", "deactivate", "pick"):
            return self._handle_interact(npc, target, action)
        if action in ("talk", "greet", "threaten", "compliment", "insult",
                      "befriend", "persuade"):
            return self._handle_social(npc, target, action)
        if action in ("wait", "rest", "sleep", "sit", "stand"):
            return self._handle_rest(npc, target, action)
        if action in ("craft", "forge", "brew", "cook", "build", "repair", "work"):
            return self._handle_work(npc, target, action)
        if action == "howl":
            return self._handle_howl(npc)

        # Default — log as flavor
        self.engine.memory_manager.add_event(f"{npc.name} {action} {target}.")
        npc.add_memory(f"I {action} {target}", 1)
        return True

    def _handle_howl(self, npc) -> bool:
        """Pack alert (P5.1): same-kind hostiles converge on the player."""
        player = self.engine.player
        if player is None:
            return False
        self.engine.memory_manager.add_event(
            f"{npc.name}'s howl echoes across the wilds!")
        px, py = player.position
        nx, ny = npc.position
        alerted = 0
        for other in self.engine.npc_manager.npcs.values():
            if other.id == npc.id or not other.is_active():
                continue
            if other.name != npc.name:
                continue
            ox, oy = other.position
            if abs(ox - nx) + abs(oy - ny) <= 10:
                other.metadata["alert"] = [px, py]
                alerted += 1
        logger.debug(f"{npc.name} alerted {alerted} packmates")
        return True

    # --------------- movement ----------------------------------------

    def _handle_move(self, npc, target: str, activity: str = "") -> bool:
        text = (target or "").lower()
        # A scheduled NPC that has REACHED its location keyword would otherwise
        # freeze on one tile (the "hangs around too long" George saw). On arrival
        # it either PERFORMS its scheduled activity (LIVING_WORLD A1 — a smith
        # hammers, a cleric prays) or, for a non-work activity, MILLS ABOUT.
        if not any(w in text for w in _DIRECTIONS):
            loc = self._resolve_location_target(npc, text)
            if loc is not None:
                d2 = (loc[0] - npc.position[0]) ** 2 + \
                     (loc[1] - npc.position[1]) ** 2
                acts = getattr(self.engine, "activities", None)
                # A2: a guard patrols a real beat — sticky once started (the beat
                # ranges past the loiter radius, so re-engage by its route, not d2)
                if activity == "patrol" and acts is not None and \
                        (npc.metadata.get("_patrol_center") == list(loc)
                         or d2 <= LOITER_RADIUS * LOITER_RADIUS):
                    return acts.patrol_step(npc, loc)
                if d2 <= LOITER_RADIUS * LOITER_RADIUS:
                    if activity and acts is not None and acts.is_perform(activity):
                        return acts.perform(npc, activity, loc)  # A1/A3: perform
                    return self._loiter_step(npc, loc)
        direction = self._interpret_direction(npc, target)
        if direction == (0, 0):
            return False
        nx, ny = npc.position[0] + direction[0], npc.position[1] + direction[1]
        if self.engine.world.map.move_character(npc, nx, ny):
            self.engine.memory_manager.add_event(f"{npc.name} moves {target}.")
            return True
        # try alternate
        for alt in [(direction[0], 0), (0, direction[1])]:
            if alt == (0, 0):
                continue
            ax, ay = npc.position[0] + alt[0], npc.position[1] + alt[1]
            if self.engine.world.map.move_character(npc, ax, ay):
                self.engine.memory_manager.add_event(
                    f"{npc.name} takes an alternate path.")
                return True
        return False

    def _loiter_step(self, npc, center) -> bool:
        """Stroll toward a wander POINT within LOITER_RADIUS of `center`, picking a
        fresh one on arrival — so an idle NPC continuously ambles around its spot
        (directed motion reads far livelier than random adjacent jitter) instead
        of standing frozen. An occasional pause keeps it natural."""
        meta = getattr(npc, "metadata", None)
        if meta is None:
            return False
        if random.random() < LOITER_PAUSE_CHANCE:
            return False                       # a natural pause between strolls
        pos = npc.position
        r2 = LOITER_RADIUS * LOITER_RADIUS
        last = meta.get("_loiter_prev")
        tgt = meta.get("_loiter_target")
        # (re)pick when there's no target, we've arrived, or it's a stale point
        # from another spot (outside this location's loiter area)
        if not tgt or tuple(pos) == tuple(tgt) or \
                (tgt[0] - center[0]) ** 2 + (tgt[1] - center[1]) ** 2 > r2:
            tgt = self._pick_loiter_target(center)
            meta["_loiter_target"] = tgt
        # try the directed step toward the wander point first (purposeful stroll),
        # then ANY in-radius neighbour (robust in crowded/tight spots), never
        # backtracking onto the tile just left (so it covers ground, not jitters)
        cands = []
        if tgt:
            dx = (tgt[0] > pos[0]) - (tgt[0] < pos[0])
            dy = (tgt[1] > pos[1]) - (tgt[1] < pos[1])
            cands = [(dx, dy), (dx, 0), (0, dy)]
        others = list(_LOITER_DIRS)
        random.shuffle(others)
        for sx, sy in cands + others:
            if (sx, sy) == (0, 0):
                continue
            nx, ny = pos[0] + sx, pos[1] + sy
            if (nx, ny) == last or \
                    (nx - center[0]) ** 2 + (ny - center[1]) ** 2 > r2:
                continue
            if self.engine.world.map.move_character(npc, nx, ny):
                meta["_loiter_prev"] = tuple(pos)
                return True
        meta["_loiter_target"] = None          # blocked → a fresh point next time
        return False

    @staticmethod
    def _pick_loiter_target(center):
        for _ in range(6):
            ox = random.randint(-LOITER_RADIUS, LOITER_RADIUS)
            oy = random.randint(-LOITER_RADIUS, LOITER_RADIUS)
            if (ox or oy) and ox * ox + oy * oy <= LOITER_RADIUS * LOITER_RADIUS:
                return (center[0] + ox, center[1] + oy)
        return None

    def _interpret_direction(self, npc, target: str) -> Tuple[int, int]:
        text = (target or "").lower()
        for word, vec in _DIRECTIONS.items():
            if word in text:
                return vec

        # Target is the player?
        player_terms = ("player", "adventurer", "traveler", "stranger", "newcomer")
        target_pos = None
        if any(t in text for t in player_terms):
            target_pos = self.engine.player.position

        # Target is an NPC by name?
        if target_pos is None:
            for other in self.engine.npc_manager.npcs.values():
                if other.id == npc.id:
                    continue
                if other.name.lower() in text:
                    target_pos = other.position
                    break

        # Target is a location? Try by direct name first, then by keyword.
        if target_pos is None:
            target_pos = self._resolve_location_target(npc, text)

        if target_pos is None:
            return (0, 0)

        # If already at the target, don't move
        if target_pos == npc.position:
            return (0, 0)

        dx = target_pos[0] - npc.position[0]
        dy = target_pos[1] - npc.position[1]
        dx = (dx > 0) - (dx < 0)
        dy = (dy > 0) - (dy < 0)
        if dx and dy:
            if abs(target_pos[0] - npc.position[0]) > \
                    abs(target_pos[1] - npc.position[1]):
                dy = 0
            else:
                dx = 0
        return (dx, dy)

    # --------------- social ------------------------------------------

    def _handle_social(self, npc, target: str, action: str) -> bool:
        char = self.engine.find_character(target)
        if not char:
            return False

        if not self._adjacent(npc, char):
            return self._step_toward(npc, char)

        if action in ("talk", "greet"):
            self.engine.memory_manager.add_event(f"{npc.name} greets {char.name}.")
            return True
        if action == "befriend":
            npc.modify_relationship(char.id, 10)
            char.modify_relationship(npc.id, 5)
            self.engine.memory_manager.add_event(
                f"{npc.name} makes a friendly gesture toward {char.name}.")
            return True
        if action == "threaten":
            npc.modify_relationship(char.id, -5)
            char.modify_relationship(npc.id, -15)
            self.engine.memory_manager.add_event(f"{npc.name} threatens {char.name}!")
            if char.get_relationship(npc.id) < -50 and random.random() < 0.5:
                self.engine.combat_system.npc_attack(char, npc.name)
            return True
        if action == "compliment":
            npc.modify_relationship(char.id, 5)
            char.modify_relationship(npc.id, 5)
            self.engine.memory_manager.add_event(
                f"{npc.name} compliments {char.name}.")
            return True
        if action == "insult":
            npc.modify_relationship(char.id, -10)
            char.modify_relationship(npc.id, -10)
            self.engine.memory_manager.add_event(
                f"{npc.name} insults {char.name}!")
            return True
        return False

    # --------------- interaction -------------------------------------

    def _handle_interact(self, npc, target: str, action: str) -> bool:
        nx, ny = npc.position
        ground = self.engine.world.get_items_at(nx, ny)

        if action in ("take", "pick"):
            for item in list(ground):
                item_name = item.name if hasattr(item, "name") else str(item)
                if target.lower() in item_name.lower() or target.lower() == "item":
                    npc.add_item(item)
                    self.engine.world.remove_item_from_ground(item, nx, ny)
                    self.engine.memory_manager.add_event(
                        f"{npc.name} picks up {item_name}.")
                    return True
            return False

        if action == "drop":
            for item in list(npc.inventory):
                item_name = item.name if hasattr(item, "name") else str(item)
                if target.lower() in item_name.lower():
                    npc.inventory.remove(item)
                    self.engine.world.add_item_to_ground(item, nx, ny)
                    self.engine.memory_manager.add_event(
                        f"{npc.name} drops {item_name}.")
                    return True
            return False

        if action == "use":
            for item in list(npc.inventory):
                item_name = item.name if hasattr(item, "name") else str(item)
                if target.lower() in item_name.lower():
                    heal = getattr(item, "heal_amount", 0)
                    if heal and npc.hp < npc.max_hp:
                        npc.heal(heal)
                        npc.inventory.remove(item)
                        self.engine.memory_manager.add_event(
                            f"{npc.name} uses {item_name} (+{heal} HP).")
                    else:
                        self.engine.memory_manager.add_event(
                            f"{npc.name} uses {item_name}.")
                    return True
            return False

        if action in ("examine", "search", "open", "close"):
            self.engine.memory_manager.add_event(
                f"{npc.name} {action}s {target}.")
            return True
        return False

    # --------------- rest --------------------------------------------

    def _handle_rest(self, npc, target: str, action: str) -> bool:
        try:
            from characters.needs import rest, feed
        except Exception:
            rest = feed = lambda *a, **k: None

        if "sleep" in (target.lower() + " " + action.lower()):
            rest(npc, amount=60)
            npc.metadata = getattr(npc, "metadata", None) or {}
            npc.metadata["activity"] = "sleep"
            heal = min(2, npc.max_hp - npc.hp)
            if heal > 0:
                npc.heal(heal)
            self.engine.memory_manager.add_event(
                f"{npc.name} sleeps {('and recovers ' + str(heal) + ' HP') if heal else 'peacefully'}."
            )
            return True
        if action in ("rest", "sit", "wait") and "tavern" in target.lower():
            # Probably eating
            feed(npc, amount=40)
            self.engine.memory_manager.add_event(
                f"{npc.name} eats at the {target}.")
            return True
        if "activity" in (getattr(npc, "metadata", None) or {}):
            # NPC was sleeping — wake up now
            npc.metadata.pop("activity", None)
        self.engine.memory_manager.add_event(f"{npc.name} {action}s {target}.")
        return True

    # --------------- work --------------------------------------------

    def _handle_work(self, npc, target: str, action: str) -> bool:
        # LIVING_WORLD A6: a craft/forge action (LLM backends) produces a good
        # gated on the worker's real PROFESSION, not the old `klass=="merchant"`;
        # the heuristic path performs work visibly via the ActivitySystem (A1).
        from items.item_registry import create_item
        acts = getattr(self.engine, "activities", None)
        prof = acts.profession_of(npc) if acts is not None else None
        forge = action in ("forge", "craft", "smith") or prof in ("smith",
                                                                   "carpenter")
        if forge:
            forge_targets = {
                "sword": "sword", "blade": "sword", "weapon": "dagger",
                "armor": "leather", "shield": "shield", "dagger": "dagger",
            }
            for keyword, item_id in forge_targets.items():
                if keyword in (target or "").lower():
                    item = create_item(item_id)
                    if item:
                        npc.add_item(item)
                        self.engine.memory_manager.add_event(
                            f"{npc.name} forges a {item.name}.")
                        return True
        self.engine.memory_manager.add_event(f"{npc.name} works on {target}.")
        return True

    # --------------- internal helpers --------------------------------

    def _resolve_location_target(self, npc, text: str) -> Optional[Tuple[int, int]]:
        """Resolve keywords like 'tavern' / 'home' / 'village' / a location name."""
        if not text:
            return None
        # Direct name match (exact or substring)
        for loc in self.engine.world.locations:
            if loc.name.lower() == text or loc.name.lower() in text or \
                    text in loc.name.lower():
                return loc.center()

        # Generic keywords -> by location type
        keyword_to_property = {
            "tavern": "tavern",
            "shop": "shop",
            "store": "shop",
            "forge": "forge",
            "smith": "forge",
            "temple": "temple",
            "chapel": "temple",
            "shrine": "temple",
            "inn": "tavern",
        }
        for keyword, prop in keyword_to_property.items():
            if keyword in text:
                # Prefer one matching the NPC's home_location if set
                home_name = getattr(npc, "home_location", "")
                for loc in self.engine.world.locations:
                    if loc.get_property("type", "") == prop and \
                            loc.name == home_name:
                        return loc.center()
                # Otherwise nearest matching location
                candidates = [
                    loc for loc in self.engine.world.locations
                    if loc.get_property("type", "") == prop]
                if candidates:
                    nearest = min(candidates,
                                  key=lambda l: self._dist_to(npc, l.center()))
                    return nearest.center()

        # "home" -> the NPC's home_location
        if "home" in text:
            home_name = getattr(npc, "home_location", "")
            if home_name:
                for loc in self.engine.world.locations:
                    if loc.name == home_name:
                        return loc.center()

        # "village" -> nearest village center
        if "village" in text or "town" in text or "hamlet" in text:
            for loc in self.engine.world.locations:
                lname = loc.name.lower()
                if "village" in lname or "hamlet" in lname:
                    return loc.center()
        return None

    def _dist_to(self, npc, pos) -> float:
        return ((npc.position[0] - pos[0]) ** 2 +
                (npc.position[1] - pos[1]) ** 2) ** 0.5

    def _adjacent(self, a, b) -> bool:
        return ((a.position[0] - b.position[0]) ** 2 +
                (a.position[1] - b.position[1]) ** 2) ** 0.5 <= 1.5

    def _step_toward(self, mover, target) -> bool:
        dx = target.position[0] - mover.position[0]
        dy = target.position[1] - mover.position[1]
        dx = (dx > 0) - (dx < 0)
        dy = (dy > 0) - (dy < 0)
        if dx and dy:
            if abs(target.position[0] - mover.position[0]) > \
                    abs(target.position[1] - mover.position[1]):
                dy = 0
            else:
                dx = 0
        nx, ny = mover.position[0] + dx, mover.position[1] + dy
        return self.engine.world.map.move_character(mover, nx, ny)

    def _update_goals(self, npc, goal_update: str) -> None:
        # Replace existing goal that overlaps, else append
        for i, goal in enumerate(npc.goals):
            if goal.lower() in goal_update.lower() or \
                    goal_update.lower() in goal.lower():
                npc.goals[i] = goal_update
                return
        npc.goals.append(goal_update)
