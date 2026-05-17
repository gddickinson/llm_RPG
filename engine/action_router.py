"""Action router — dispatches NPC actions to handlers.

Receives parsed action data from the LLM/heuristic provider and routes
to combat, economy, social, movement, interaction, rest, work handlers.
"""

import logging
import random
from typing import Dict, Optional, Tuple

logger = logging.getLogger("llm_rpg.action_router")


_DIRECTIONS = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "northeast": (1, -1), "northwest": (-1, -1),
    "southeast": (1, 1), "southwest": (-1, 1),
    "up": (0, -1), "down": (0, 1), "right": (1, 0), "left": (-1, 0),
    "forward": (0, -1), "backward": (0, 1),
    "forwards": (0, -1), "backwards": (0, 1),
}


class ActionRouter:
    """Route LLM-decided actions to the right handler."""

    def __init__(self, engine):
        self.engine = engine

    def process(self, npc, action_data: Dict[str, str]) -> bool:
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
            return self._handle_move(npc, target)
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

        # Default — log as flavor
        self.engine.memory_manager.add_event(f"{npc.name} {action} {target}.")
        npc.add_memory(f"I {action} {target}", 1)
        return True

    # --------------- movement ----------------------------------------

    def _handle_move(self, npc, target: str) -> bool:
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

        # Target is a location?
        if target_pos is None:
            for loc in self.engine.world.locations:
                if loc.name.lower() in text:
                    target_pos = loc.center()
                    break

        if target_pos is None:
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
                    npc.inventory.append(item)
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
        if "sleep" in (target.lower() + " " + action.lower()):
            heal = min(2, npc.max_hp - npc.hp)
            if heal > 0:
                npc.heal(heal)
            self.engine.memory_manager.add_event(
                f"{npc.name} sleeps {('and recovers ' + str(heal) + ' HP') if heal else 'peacefully'}."
            )
            return True
        self.engine.memory_manager.add_event(f"{npc.name} {action}s {target}.")
        return True

    # --------------- work --------------------------------------------

    def _handle_work(self, npc, target: str, action: str) -> bool:
        # Crafting: blacksmith forges items
        from items.item_registry import create_item
        klass = getattr(getattr(npc, "character_class", None), "value", "")
        if action in ("forge", "craft", "smith") and klass == "merchant":
            forge_targets = {
                "sword": "sword", "blade": "sword", "weapon": "dagger",
                "armor": "leather", "shield": "shield",
            }
            for keyword, item_id in forge_targets.items():
                if keyword in target.lower():
                    item = create_item(item_id)
                    if item:
                        npc.inventory.append(item)
                        self.engine.memory_manager.add_event(
                            f"{npc.name} forges a {item.name}.")
                        return True
        self.engine.memory_manager.add_event(f"{npc.name} works on {target}.")
        return True

    # --------------- internal helpers --------------------------------

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
