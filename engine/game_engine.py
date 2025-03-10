"""
Core Game Engine module for LLM-RPG
Coordinates all game components and manages game state
"""

import logging
import time
from typing import Dict, Any, List, Optional
import config
import random

from world.world import World
from characters.npc_manager import NPCManager
from characters.character import Character
from characters.character_types import CharacterClass
from llm.llm_interface import LLMInterface
from engine.memory_manager import MemoryManager
from engine.npc_process_manager import NPCProcessManager


logger = logging.getLogger("llm_rpg.engine")

class GameEngine:
    """Main game engine that coordinates all game modules"""

    def __init__(self, llm_model=config.DEFAULT_MODEL):
        """Initialize the game engine with all necessary components"""
        self.world = World()
        self.npc_manager = NPCManager()
        self.memory_manager = MemoryManager()

        # Regular LLM interface for player interactions
        self.llm_interface = LLMInterface(model_name=llm_model)

        self.player = None
        self.running = False
        self.turn_counter = 0
        self.processing_npcs = set()  # Track NPCs being processed

        # Initialize simple demo world
        self.initialize_demo_game()

        # Start NPC processes after the world is created
        npc_list = list(self.npc_manager.npcs.values())
        self.process_manager = NPCProcessManager(npc_list, llm_model=llm_model)
        self.process_manager.start_processes()

        logger.info("Game Engine initialized with Process Manager")

    def initialize_demo_game(self):
        """Set up a simple demo game"""
        # Create world
        self.world.create_simple_world()

        # Create NPCs
        npcs = self.npc_manager.create_simple_npcs()

        # Place NPCs on the map
        for npc in npcs:
            self.world.map.place_character(npc, npc.position[0], npc.position[1])

        # Create player character
        self.create_default_player()

        # Add initial event
        self.memory_manager.add_event("You arrive at the outskirts of Oakvale Village.")

        logger.info("Demo game initialized")

    def create_default_player(self):
        """Create a default player character"""
        from characters.character_types import CharacterClass, CharacterRace

        self.player = Character(
            id="player",
            name="Player",
            character_class=CharacterClass.WARRIOR,
            race=CharacterRace.HUMAN,
            level=1,
            strength=14,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=12,
            hp=20,
            max_hp=20,
            position=(15, 5),
            inventory=["sword", "shield", "potion"],
            gold=50,
            symbol="@",
            description="A brave adventurer",
            personality={},
            goals=["Explore the world", "Find adventure"]
        )

        # Place player on map
        self.world.map.place_character(self.player, self.player.position[0], self.player.position[1])

    def start_game(self):
        """Start the game"""
        self.running = True
        self.turn_counter = 0

        # Add game start event
        self.memory_manager.add_event("The adventure begins.")

        logger.info("Game started")

    # def end_game(self):
    #     """End the game"""
    #     self.running = False

    #     # Add game end event
    #     self.memory_manager.add_event("The adventure has ended.")

    #     logger.info("Game ended")

    def move_player(self, dx, dy):
        """Move the player character"""
        if not self.running:
            return False

        new_x = self.player.position[0] + dx
        new_y = self.player.position[1] + dy

        result = self.world.map.move_character(self.player, new_x, new_y)

        if result:
            # Get the current location name
            location = self.world.get_location_at(new_x, new_y)
            location_name = location.name if location else "wilderness"

            # Add event to the memory
            self.memory_manager.add_event(f"Player moved to {location_name} at position ({new_x}, {new_y}).")

            # Increment turn counter
            self.advance_turn()

        return result

    def process_npc_turns(self):
        """Process NPC actions"""
        # Only process NPC turns periodically to reduce LLM calls
        if self.turn_counter % config.NPC_ACTION_INTERVAL != 0:
            return

        logger.debug("Processing NPC turns")

        # Process each NPC
        for npc_id, npc in self.npc_manager.npcs.items():
            try:
                # Skip NPCs that are too far from the player (optimization)
                npc_x, npc_y = npc.position
                player_x, player_y = self.player.position
                distance = ((npc_x - player_x) ** 2 + (npc_y - player_y) ** 2) ** 0.5

                # Only process NPCs within a certain range of the player
                if distance > config.DEFAULT_VISIBILITY_RANGE * 2:
                    continue

                # Get visible environment for the NPC
                visible_map = self.world.map.get_visible_description(npc_x, npc_y)

                # Get game state information
                world_state = {
                    "current_location": self.world.get_location_at(npc_x, npc_y).name if self.world.get_location_at(npc_x, npc_y) else "wilderness",
                    "time_of_day": self.world.get_time_of_day()
                }

                # Get recent history
                game_history = self.memory_manager.get_recent_history()

                # Get NPC action from LLM
                action_data = self.llm_interface.get_npc_action(npc, world_state, game_history, visible_map)

                # Process the action
                self._process_npc_action(npc, action_data)

            except Exception as e:
                logger.error(f"Error processing NPC {npc_id}: {str(e)}")

    def _process_npc_action(self, npc, action_data):
        """Process an NPC's action based on LLM response with enhanced capabilities"""
        action = action_data.get("action", "").lower()
        target = action_data.get("target", "")
        dialog = action_data.get("dialog", "")
        thoughts = action_data.get("thoughts", "")
        emotion = action_data.get("emotion", "")
        goal_update = action_data.get("goal_update", "")

        # Log NPC thoughts (not visible to player)
        logger.debug(f"NPC {npc.name} thinks: {thoughts}")

        # Update NPC emotion if provided
        if emotion:
            npc.personality["current_emotion"] = emotion

        # Update NPC goals if provided
        if goal_update and goal_update != "None":
            # Check if it's updating an existing goal or adding a new one
            if any(goal in goal_update for goal in npc.goals):
                # Update existing goal
                for i, goal in enumerate(npc.goals):
                    if goal in goal_update:
                        npc.goals[i] = goal_update
                        break
            else:
                # Add as a new goal
                npc.goals.append(goal_update)

        # Process dialog
        if dialog and dialog != "None":
            event = f"{npc.name} says: \"{dialog}\""
            self.memory_manager.add_event(event)
            # Add to NPC's own memory
            npc.add_memory(f"I said: \"{dialog}\"", 1)

        # Process actions
        result = False

        # ===== MOVEMENT ACTIONS =====
        if action in ["move", "walk", "run", "approach", "go"]:
            result = self._handle_movement_action(npc, target)

        # ===== COMBAT ACTIONS =====
        elif action in ["attack", "fight", "strike", "slash", "stab", "shoot", "cast"]:
            result = self._handle_combat_action(npc, target, action)

        # ===== ECONOMIC ACTIONS =====
        elif action in ["buy", "sell", "trade", "offer", "pay", "gift", "give"]:
            result = self._handle_economic_action(npc, target, action)

        # ===== WORLD INTERACTION ACTIONS =====
        elif action in ["open", "close", "examine", "search", "take", "drop", "use", "activate", "deactivate"]:
            result = self._handle_interaction_action(npc, target, action)

        # ===== SOCIAL ACTIONS =====
        elif action in ["talk", "greet", "threaten", "compliment", "insult", "befriend", "persuade"]:
            result = self._handle_social_action(npc, target, action)

        # ===== REST ACTIONS =====
        elif action in ["wait", "rest", "sleep", "sit", "stand"]:
            result = self._handle_rest_action(npc, target, action)  # Pass action as the action_type

        # ===== WORK ACTIONS =====
        elif action in ["craft", "forge", "brew", "cook", "build", "repair", "work"]:
            result = self._handle_work_action(npc, target, action)

        # ===== DEFAULT ACTION =====
        else:
            event = f"{npc.name} {action} {target}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I {action} {target}", 1)
            result = True

        # Log the action result
        action_status = "completed" if result else "failed"
        logger.debug(f"NPC {npc.name} action '{action} {target}' {action_status}")
        return result

    def advance_turn(self):
        """Advance the game by one turn"""
        self.turn_counter += 1
        self.world.advance_time(1)  # Advance game time by 1 minute

        # Process NPC actions if needed
        if self.turn_counter % config.NPC_ACTION_INTERVAL == 0:
            self.process_npc_turns()

    def get_game_state(self):
        """Get the current game state for UI rendering"""
        # Gather all relevant state information for the UI
        return {
            "player": self.player,
            "map": self.world.map,
            "visible_map": self.world.map.get_visible_description(
                self.player.position[0],
                self.player.position[1]
            ),
            "location": self.world.get_location_at(
                self.player.position[0],
                self.player.position[1]
            ),
            "time_of_day": self.world.get_time_of_day(),
            "recent_events": self.memory_manager.get_recent_history(5),
            "turn": self.turn_counter
        }

    def interact_with_npc(self, npc_id, message=None):
        """Player interacts with an NPC"""
        npc = self.npc_manager.get_npc(npc_id)
        if not npc:
            return f"NPC with ID {npc_id} not found."

        # Check if player is close enough to interact
        player_x, player_y = self.player.position
        npc_x, npc_y = npc.position
        distance = ((player_x - npc_x) ** 2 + (player_y - npc_y) ** 2) ** 0.5

        if distance > 1.5:  # Not adjacent or diagonal
            return f"{npc.name} is too far away to interact with."

        # If player sent a message, handle the conversation
        if message:
            # Add the player's message to history
            self.memory_manager.add_event(f"You say to {npc.name}: \"{message}\"")

            # Get recent conversation history
            recent_history = self.memory_manager.get_character_history(npc.name, count=5)

            # Send dialog request to NPC's process
            self.process_manager.send_command(npc_id, "get_dialog", {
                "message": message,
                "recent_history": recent_history
            })

            # Wait for response with timeout
            response_data = self.process_manager.get_response(npc_id, timeout=5.0)

            # Default response if no response received
            if not response_data or response_data.get("type") != "dialog":
                response = f"Hmm... {npc.name} seems lost in thought."
            else:
                response = response_data["response"]

            # Add NPC's response to history
            self.memory_manager.add_event(f"{npc.name} says: \"{response}\"")

            # Add to NPC's memory
            npc.add_memory(f"Player said: \"{message}\". I replied: \"{response}\"", 2)

            # Update the NPC data in its process
            self.process_manager.send_command(npc_id, "update_npc", npc.to_dict())

            # Advance turn
            self.advance_turn()

            return response
        else:
            # For initial greeting, use the same approach but with no player message
            self.process_manager.send_command(npc_id, "get_dialog", {
                "message": "Hello",  # Simple greeting
                "recent_history": []
            })

            # Wait for response with timeout
            response_data = self.process_manager.get_response(npc_id, timeout=3.0)

            # Default greeting if no response received
            if not response_data or response_data.get("type") != "dialog":
                greeting = f"Hello there, traveler."
            else:
                greeting = response_data["response"]

            # Add greeting to history
            self.memory_manager.add_event(f"{npc.name} says: \"{greeting}\"")

            # Advance turn
            self.advance_turn()

            return greeting

    def _get_npc_dialog_response(self, npc, player_message):
        """Get an NPC's response to player dialog using the LLM"""
        # Create a system prompt for dialog
        system_prompt = f"""You are roleplaying as {npc.name}, a {npc.race.value} {npc.character_class.value} in a fantasy RPG game.
Respond to the player's message in character, based on your personality, goals, and memories.
Keep your response relatively brief and conversational."""

        # Create a prompt with all relevant context
        prompt = f"""
CHARACTER SHEET:
{npc.to_dict()}

PERSONALITY TRAITS:
{npc.personality.get('traits', [])}

CURRENT GOALS:
{npc.goals}

MEMORIES:
{npc.memories[-5:] if len(npc.memories) > 5 else npc.memories}

The player approaches you and says: "{player_message}"

How do you respond?
"""

        # Get response from LLM
        response = self.llm_interface.generate_response(prompt, system_prompt, temperature=0.7)

        # Clean up response if needed
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]

        return response

    def _get_npc_greeting(self, npc):
        """Get an initial greeting from an NPC using the LLM"""
        # Similar to dialog response but for initial greeting
        system_prompt = f"""You are roleplaying as {npc.name}, a {npc.race.value} {npc.character_class.value} in a fantasy RPG game.
The player has just approached you. Provide a brief greeting that fits your character's personality and current situation."""

        # Create a prompt with character context
        prompt = f"""
CHARACTER SHEET:
{npc.to_dict()}

PERSONALITY TRAITS:
{npc.personality.get('traits', [])}

CURRENT LOCATION:
{self.world.get_location_at(npc.position[0], npc.position[1]).name if self.world.get_location_at(npc.position[0], npc.position[1]) else "wilderness"}

TIME OF DAY:
{self.world.get_time_of_day()}

CURRENT GOALS:
{npc.goals}

MEMORIES:
{npc.memories[-5:] if len(npc.memories) > 5 else npc.memories}

The player approaches you. What's your initial greeting?
"""

        # Get response from LLM
        response = self.llm_interface.generate_response(prompt, system_prompt, temperature=0.7)

        # Clean up response if needed
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]

        return response


    def process_npc_turns_async(self):
        """Process NPC actions asynchronously using separate processes"""
        # At the beginning of the method, add explicit log of which NPCs are active:
        active_npcs = [npc for npc_id, npc in self.npc_manager.npcs.items()
                      if hasattr(npc, 'is_active') and npc.is_active()]
        logger.debug(f"Active NPCs this turn: {[npc.name for npc in active_npcs]}")

        # Only process NPC turns periodically
        if self.turn_counter % config.NPC_ACTION_INTERVAL != 0:
            return

        logger.debug("Processing NPC turns asynchronously")

        # Update shared game state
        game_state = {
            "time_of_day": self.world.get_time_of_day(),
            "turn_counter": self.turn_counter,
            "player_position": self.player.position
        }
        self.process_manager.update_shared_state("game_state", game_state)

        # Check process health and restart any dead processes
        self.process_manager.check_process_health()

        # Collect any existing responses from NPCs
        responses = self.process_manager.get_responses()
        for npc_id, response in responses.items():
            # Get the NPC
            npc = self.npc_manager.get_npc(npc_id)

            # Skip if NPC doesn't exist or isn't active
            if not npc or (hasattr(npc, 'is_active') and not npc.is_active()):
                logger.debug(f"Skipping action for inactive NPC {npc_id}")
                continue

            # Process response if it's an action and NPC is active
            if response["type"] == "action":
                self._process_npc_action(npc, response["action_data"])
            elif response["type"] == "error":
                logger.error(f"Error from NPC process {npc_id}: {response['error']}")


            # Update NPC statuses in processes
            if hasattr(self.process_manager, 'update_npc_statuses'):
                try:
                    self.process_manager.update_npc_statuses()
                except Exception as e:
                    logger.error(f"Error updating NPC statuses: {str(e)}")

            # And add a status check before sending action requests
            # Before sending command to NPC process, add:
            if not npc.is_active():
                logger.debug(f"Skipping action request for inactive NPC {npc.name}")
                continue

        # Send action requests to active NPCs only
        for npc_id, npc in self.npc_manager.npcs.items():
            # Skip if NPC is not active (defeated or dead)
            if hasattr(npc, 'is_active') and not npc.is_active():
                continue

            # Skip if NPC is too far from player
            npc_x, npc_y = npc.position
            player_x, player_y = self.player.position
            distance = ((npc_x - player_x) ** 2 + (npc_y - player_y) ** 2) ** 0.5

            if distance > config.DEFAULT_VISIBILITY_RANGE * 2:
                continue

            # Skip if this NPC is already being processed
            if npc_id in self.processing_npcs:
                continue

            # Add to processing set
            self.processing_npcs.add(npc_id)

            # Get data needed for NPC decision
            visible_map = self.world.map.get_visible_description(npc_x, npc_y)
            world_state = {
                "current_location": self.world.get_location_at(npc_x, npc_y).name if self.world.get_location_at(npc_x, npc_y) else "wilderness",
                "time_of_day": self.world.get_time_of_day()
            }
            game_history = self.memory_manager.get_recent_history()

            # Send command to NPC process
            self.process_manager.send_command(npc_id, "get_action", {
                "world_state": world_state,
                "game_history": game_history,
                "visible_map": visible_map
            })


    # Update the shutdown method to clean up the threaded LLM interface
    def end_game(self):
        """End the game"""
        self.running = False

        # Add game end event
        self.memory_manager.add_event("The adventure has ended.")

        # Shutdown NPC processes
        if hasattr(self, 'process_manager'):
            self.process_manager.stop_processes()

        # Shutdown any threaded resources
        if hasattr(self.llm_interface, 'shutdown'):
            self.llm_interface.shutdown()

        logger.info("Game ended")

    def _interpret_movement_target(self, npc, target_text):
        """
        Interpret a movement target from natural language
        Returns a tuple (dx, dy) of the best direction to move
        """
        # Parse the target text to identify the target
        target_text = target_text.lower()
        target_object = None
        target_position = None

        # Check if target mentions a direction
        directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
            "northeast": (1, -1),
            "northwest": (-1, -1),
            "southeast": (1, 1),
            "southwest": (-1, 1),
            "up": (0, -1),
            "down": (0, 1),
            "right": (1, 0),
            "left": (-1, 0),
            "forward": (0, -1),  # Default forward to north
            "backward": (0, 1),  # Default backward to south
            "forwards": (0, -1),
            "backwards": (0, 1)
        }

        # Check for explicit directions first
        for direction, vector in directions.items():
            if direction in target_text:
                logger.debug(f"NPC {npc.name} is moving {direction} ({vector})")
                return vector

        # Target is the player
        player_terms = ["player", "adventurer", "traveler", "traveller", "stranger", "newcomer"]
        if any(term in target_text for term in player_terms):
            target_object = self.player
            target_position = self.player.position
            logger.debug(f"NPC {npc.name} is targeting the player at {target_position}")

        # Target is another NPC by name
        else:
            for other_npc_id, other_npc in self.npc_manager.npcs.items():
                if other_npc.id != npc.id and other_npc.name.lower() in target_text:
                    target_object = other_npc
                    target_position = other_npc.position
                    logger.debug(f"NPC {npc.name} is targeting {other_npc.name} at {target_position}")
                    break

        # Target is a location
        if not target_position:
            for location in self.world.locations:
                if location.name.lower() in target_text:
                    target_position = location.center()
                    logger.debug(f"NPC {npc.name} is targeting location {location.name} at {target_position}")
                    break

        # If we found a target position, calculate the best direction to move
        if target_position:
            # Calculate vector to target
            dx = target_position[0] - npc.position[0]
            dy = target_position[1] - npc.position[1]

            # Normalize to a single step
            if dx != 0:
                dx = 1 if dx > 0 else -1
            if dy != 0:
                dy = 1 if dy > 0 else -1

            # If diagonal, prioritize horizontal or vertical based on which is larger
            if dx != 0 and dy != 0:
                # If target is closer horizontally, move horizontally first
                if abs(target_position[0] - npc.position[0]) > abs(target_position[1] - npc.position[1]):
                    dy = 0
                else:
                    dx = 0

            logger.debug(f"NPC {npc.name} movement vector towards {target_position}: ({dx}, {dy})")
            return (dx, dy)

        # Default to no movement if we can't determine a target
        logger.debug(f"NPC {npc.name} has no clear movement target")
        return (0, 0)


    def _handle_movement_action(self, npc, target):
        """Handle NPC movement actions"""
        try:
            # First attempt to find an explicit direction in the target text
            direction = self._interpret_movement_target(npc, target)

            # If we got a valid direction, move the NPC
            if direction != (0, 0):
                current_x, current_y = npc.position
                new_x, new_y = current_x + direction[0], current_y + direction[1]

                # Attempt to move the character on the map
                move_result = self.world.map.move_character(npc, new_x, new_y)

                if move_result:
                    event = f"{npc.name} moves {target}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I moved {target}", 1)
                    logger.debug(f"NPC {npc.name} moved to ({new_x}, {new_y})")
                    return True
                else:
                    # If movement is blocked, try alternate directions
                    alternates = [(direction[0], 0), (0, direction[1])]
                    for alt_dir in alternates:
                        if alt_dir == (0, 0):
                            continue

                        alt_x, alt_y = current_x + alt_dir[0], current_y + alt_dir[1]
                        alt_result = self.world.map.move_character(npc, alt_x, alt_y)

                        if alt_result:
                            event = f"{npc.name} moves in alternate direction."
                            self.memory_manager.add_event(event)
                            npc.add_memory(f"I had to take a detour", 1)
                            logger.debug(f"NPC {npc.name} moved to alternate position ({alt_x}, {alt_y})")
                            return True

                    logger.debug(f"NPC {npc.name} failed to move to ({new_x}, {new_y}) and all alternates")
                    return False
            else:
                logger.debug(f"NPC {npc.name} wants to move but direction unclear: {target}")
                return False

        except Exception as e:
            logger.error(f"Error processing move action for {npc.name}: {str(e)}")
            return False

    def _handle_combat_action(self, npc, target, action_type):
        """Enhanced combat action that allows NPCs to attack any character"""
        # Find the target character
        target_character = self._find_target_character(target)

        if not target_character:
            logger.debug(f"NPC {npc.name} tried to {action_type} {target}, but couldn't find the target")
            return False

        # Check if within attack range
        npc_x, npc_y = npc.position
        target_x, target_y = target_character.position
        distance = ((npc_x - target_x) ** 2 + (npc_y - target_y) ** 2) ** 0.5

        # Most combat needs adjacent positions
        attack_range = 1.5

        # Ranged attacks have longer range
        if action_type in ["shoot", "cast"]:
            attack_range = 5.0

        if distance <= attack_range:
            # Determine attack success chance based on stats
            # Simple formula: attacker's relevant stat vs defender's relevant stat
            if action_type in ["cast"]:
                # Magic attack
                attack_stat = npc.intelligence
                defense_stat = target_character.wisdom
            elif action_type in ["shoot"]:
                # Ranged attack
                attack_stat = npc.dexterity
                defense_stat = target_character.dexterity
            else:
                # Melee attack
                attack_stat = npc.strength
                defense_stat = target_character.constitution

            # Base 50% chance +/- 5% per stat point difference
            hit_chance = 0.5 + 0.05 * (attack_stat - defense_stat)
            hit_chance = max(0.1, min(0.9, hit_chance))  # Clamp between 10% and 90%

            # Roll for hit
            hit_roll = random.random()
            hit_success = hit_roll <= hit_chance

            if hit_success:
                # Calculate damage
                base_damage = max(1, attack_stat // 3)
                damage_variation = random.randint(-1, 1)
                damage = max(1, base_damage + damage_variation)

                # Apply damage to target
                target_character.take_damage(damage)

                # Create event message
                attack_verbs = {
                    "attack": "attacks",
                    "fight": "fights",
                    "strike": "strikes",
                    "slash": "slashes",
                    "stab": "stabs",
                    "shoot": "shoots at",
                    "cast": "casts a spell at"
                }
                verb = attack_verbs.get(action_type, "attacks")

                event = f"{npc.name} {verb} {target_character.name} for {damage} damage!"
                self.memory_manager.add_event(event)
                npc.add_memory(f"I attacked {target_character.name} and hit for {damage} damage", 2)

                # Update relationship - attacking always worsens relationships
                if target_character.id != npc.id:  # Skip self-relationships
                    current_relation = target_character.get_relationship(npc.id)
                    target_character.modify_relationship(npc.id, -20)  # Significant negative change
                    npc.modify_relationship(target_character.id, -10)  # Attacking someone affects your view of them too

                # Check if target was defeated
                if not target_character.is_alive():
                    # Properly mark character as defeated
                    target_character.defeat()

                    # Create defeat event
                    defeat_event = f"{target_character.name} has been defeated!"
                    self.memory_manager.add_event(defeat_event)
                    npc.add_memory(f"I defeated {target_character.name}", 3)

                    # Update the NPC process about the defeat
                    if hasattr(self, 'process_manager') and hasattr(target_character, 'id'):
                        # Send updated character data to the process
                        self.process_manager.send_command(target_character.id, "update_npc", target_character.to_dict())

                        # Also send a specific status update command
                        self.process_manager.send_command(target_character.id, "set_status", "defeated")
                        logger.debug(f"Sent defeat status to NPC process for {target_character.name}")

                    # Store body location before removing from map
                    body_position = target_character.position

                    # Store body position in character for potential revival
                    target_character.last_position = body_position

                    # If the player was defeated, trigger game over
                    if target_character.id == self.player.id:
                        self.memory_manager.add_event("You have been defeated!")
                        # We could end the game here or implement a respawn mechanic
                        self.end_game()

                    # Remove the defeated character from the map
                    self.world.map.remove_character(target_character)

                    # Add memory
                    target_character.add_memory(f"I was defeated by {npc.name}", 3)

                    # Drop items if applicable
                    if hasattr(target_character, 'inventory') and target_character.inventory:
                        # Drop a random item or all items based on game design
                        item = random.choice(target_character.inventory)
                        self.world.add_item_to_ground(item, body_position[0], body_position[1])
                        target_character.inventory.remove(item)
                        drop_event = f"{target_character.name} drops {item}!"
                        self.memory_manager.add_event(drop_event)

                    # Create a "body" object on the ground at the defeat location
                    body_item = f"{target_character.name}'s body"
                    self.world.add_item_to_ground(body_item, body_position[0], body_position[1])

                return True
            else:
                # Attack missed
                miss_event = f"{npc.name} tries to attack {target_character.name} but misses!"
                self.memory_manager.add_event(miss_event)
                npc.add_memory(f"I tried to attack {target_character.name} but missed", 1)
                return True  # Action completed, even though attack missed
        else:
            # Target out of range, try to approach
            approach_event = f"{npc.name} tries to approach {target_character.name} to attack."
            self.memory_manager.add_event(approach_event)

            # Move towards target
            direction = self._calculate_direction_to_target(npc.position, target_character.position)
            current_x, current_y = npc.position
            new_x, new_y = current_x + direction[0], current_y + direction[1]

            move_result = self.world.map.move_character(npc, new_x, new_y)
            if move_result:
                npc.add_memory(f"I moved toward {target_character.name} to attack", 1)
                return True
            else:
                npc.add_memory(f"I tried to move toward {target_character.name} but couldn't", 1)
                return False

    def _handle_economic_action(self, npc, target, action_type):
        """Handle economic interactions like buying/selling/trading"""
        # Parse target to identify item and trade partner
        target_parts = target.split(" from " if "from" in target else " to " if "to" in target else " with ")

        item_name = target_parts[0].strip()
        partner_name = target_parts[1].strip() if len(target_parts) > 1 else None

        # Find trade partner
        trade_partner = None
        if partner_name:
            trade_partner = self._find_target_character(partner_name)
        else:
            # Look for nearby characters as potential trade partners
            nearby_chars = self._find_nearby_characters(npc, distance=2.0)
            if nearby_chars:
                trade_partner = nearby_chars[0]

        if not trade_partner:
            logger.debug(f"NPC {npc.name} tried to {action_type} {item_name}, but couldn't find a trade partner")
            return False

        # Check if within interaction distance
        npc_x, npc_y = npc.position
        partner_x, partner_y = trade_partner.position
        distance = ((npc_x - partner_x) ** 2 + (npc_y - partner_y) ** 2) ** 0.5

        if distance > 1.5:  # Must be adjacent
            approach_event = f"{npc.name} tries to approach {trade_partner.name} to trade."
            self.memory_manager.add_event(approach_event)

            # Move towards trade partner
            direction = self._calculate_direction_to_target(npc.position, trade_partner.position)
            current_x, current_y = npc.position
            new_x, new_y = current_x + direction[0], current_y + direction[1]

            move_result = self.world.map.move_character(npc, new_x, new_y)
            if move_result:
                npc.add_memory(f"I moved toward {trade_partner.name} to trade", 1)
                return True
            else:
                npc.add_memory(f"I tried to move toward {trade_partner.name} but couldn't", 1)
                return False

        # Process specific economic actions
        if action_type == "buy":
            # NPC is buying from trade partner
            if not hasattr(trade_partner, 'inventory') or not trade_partner.inventory:
                event = f"{npc.name} tries to buy {item_name} from {trade_partner.name}, but they have nothing to sell."
                self.memory_manager.add_event(event)
                return False

            # Check if the item exists in partner's inventory
            item_found = False
            for item in trade_partner.inventory:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if item_name.lower() in item_str.lower():
                    item_found = True

                    # Determine price (simplified)
                    price = 10  # Default price
                    if hasattr(item, 'value'):
                        price = item.value

                    # Check if NPC has enough gold
                    if npc.gold >= price:
                        # Complete transaction
                        npc.gold -= price
                        trade_partner.gold += price
                        npc.inventory.append(item)
                        trade_partner.inventory.remove(item)

                        event = f"{npc.name} buys {item_str} from {trade_partner.name} for {price} gold."
                        self.memory_manager.add_event(event)
                        npc.add_memory(f"I bought {item_str} from {trade_partner.name} for {price} gold", 2)

                        if trade_partner.id == self.player.id:
                            # Add memory for player's side of transaction
                            trade_partner.add_memory(f"I sold {item_str} to {npc.name} for {price} gold", 2)

                        return True
                    else:
                        event = f"{npc.name} tries to buy {item_str} from {trade_partner.name} but doesn't have enough gold."
                        self.memory_manager.add_event(event)
                        npc.add_memory(f"I tried to buy {item_str} but didn't have enough gold", 1)
                        return False

            if not item_found:
                event = f"{npc.name} tries to buy {item_name} from {trade_partner.name}, but they don't have that item."
                self.memory_manager.add_event(event)
                return False

        elif action_type == "sell":
            # NPC is selling to trade partner
            if not hasattr(npc, 'inventory') or not npc.inventory:
                event = f"{npc.name} tries to sell to {trade_partner.name}, but has nothing to sell."
                self.memory_manager.add_event(event)
                return False

            # Check if the item exists in NPC's inventory
            item_found = False
            for item in npc.inventory:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if item_name.lower() in item_str.lower():
                    item_found = True

                    # Determine price (simplified)
                    price = 10  # Default price
                    if hasattr(item, 'value'):
                        price = item.value

                    # Check if trade partner has enough gold
                    if trade_partner.gold >= price:
                        # Complete transaction
                        trade_partner.gold -= price
                        npc.gold += price
                        trade_partner.inventory.append(item)
                        npc.inventory.remove(item)

                        event = f"{npc.name} sells {item_str} to {trade_partner.name} for {price} gold."
                        self.memory_manager.add_event(event)
                        npc.add_memory(f"I sold {item_str} to {trade_partner.name} for {price} gold", 2)

                        if trade_partner.id == self.player.id:
                            # Add memory for player's side of transaction
                            trade_partner.add_memory(f"I bought {item_str} from {npc.name} for {price} gold", 2)

                        return True
                    else:
                        event = f"{npc.name} tries to sell {item_str} to {trade_partner.name} but they don't have enough gold."
                        self.memory_manager.add_event(event)
                        npc.add_memory(f"I tried to sell {item_str} but {trade_partner.name} didn't have enough gold", 1)
                        return False

            if not item_found:
                event = f"{npc.name} tries to sell {item_name}, but doesn't have that item."
                self.memory_manager.add_event(event)
                return False

        elif action_type == "give":
            # NPC is giving something to trade partner
            if not hasattr(npc, 'inventory') or not npc.inventory:
                event = f"{npc.name} tries to give something to {trade_partner.name}, but has nothing to give."
                self.memory_manager.add_event(event)
                return False

            # Check for gold gifts
            if "gold" in item_name.lower() or "coin" in item_name.lower() or "money" in item_name.lower():
                # Parse amount
                amount = 1  # Default
                amount_words = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                               "ten": 10, "twenty": 20, "fifty": 50, "hundred": 100}

                for word, value in amount_words.items():
                    if word in item_name.lower():
                        amount = value
                        break

                # Try to extract numeric values
                import re
                numbers = re.findall(r'\d+', item_name)
                if numbers:
                    amount = int(numbers[0])

                # Check if NPC has enough
                if npc.gold >= amount:
                    npc.gold -= amount
                    trade_partner.gold += amount

                    event = f"{npc.name} gives {amount} gold to {trade_partner.name}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I gave {amount} gold to {trade_partner.name}", 2)

                    if trade_partner.id == self.player.id:
                        trade_partner.add_memory(f"{npc.name} gave me {amount} gold", 2)

                    return True
                else:
                    event = f"{npc.name} tries to give gold to {trade_partner.name} but doesn't have enough."
                    self.memory_manager.add_event(event)
                    return False

            # Otherwise, look for item in inventory
            item_found = False
            for item in npc.inventory:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if item_name.lower() in item_str.lower():
                    item_found = True

                    # Give item
                    trade_partner.inventory.append(item)
                    npc.inventory.remove(item)

                    event = f"{npc.name} gives {item_str} to {trade_partner.name}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I gave {item_str} to {trade_partner.name}", 2)

                    if trade_partner.id == self.player.id:
                        trade_partner.add_memory(f"{npc.name} gave me {item_str}", 2)

                    return True

            if not item_found:
                event = f"{npc.name} tries to give {item_name} to {trade_partner.name}, but doesn't have that item."
                self.memory_manager.add_event(event)
                return False

        return False

    def _handle_interaction_action(self, npc, target, action_type):
        """Handle interactions with objects in the world"""
        # Get NPC's current location
        npc_x, npc_y = npc.position

        # Check for items on the ground at NPC's position
        ground_items = self.world.get_items_at(npc_x, npc_y)

        # Handle pick up / take action
        if action_type in ["take", "pick up", "grab", "collect"]:
            if not ground_items:
                event = f"{npc.name} tries to take {target}, but there's nothing here."
                self.memory_manager.add_event(event)
                return False

            # Look for matching item
            for item in ground_items:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if target.lower() in item_str.lower() or target.lower() == "item":
                    # Add to inventory
                    npc.inventory.append(item)

                    # Remove from ground
                    self.world.remove_item_from_ground(item, npc_x, npc_y)

                    event = f"{npc.name} picks up {item_str}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I picked up {item_str}", 1)
                    return True

            event = f"{npc.name} tries to take {target}, but can't find it nearby."
            self.memory_manager.add_event(event)
            return False

        # Handle drop action
        elif action_type in ["drop", "discard", "place"]:
            if not hasattr(npc, 'inventory') or not npc.inventory:
                event = f"{npc.name} tries to drop {target}, but has nothing to drop."
                self.memory_manager.add_event(event)
                return False

            # Look for matching item in inventory
            for item in npc.inventory:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if target.lower() in item_str.lower():
                    # Remove from inventory
                    npc.inventory.remove(item)

                    # Add to ground
                    self.world.add_item_to_ground(item, npc_x, npc_y)

                    event = f"{npc.name} drops {item_str}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I dropped {item_str}", 1)
                    return True

            event = f"{npc.name} tries to drop {target}, but doesn't have that item."
            self.memory_manager.add_event(event)
            return False

        # Handle use action
        elif action_type == "use":
            if not hasattr(npc, 'inventory') or not npc.inventory:
                event = f"{npc.name} tries to use {target}, but has nothing to use."
                self.memory_manager.add_event(event)
                return False

            # Look for matching item in inventory
            for item in npc.inventory:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if target.lower() in item_str.lower():
                    # Handle different types of usable items

                    # Healing items
                    if "potion" in item_str.lower() or "healing" in item_str.lower() or "bandage" in item_str.lower():
                        if npc.hp < npc.max_hp:
                            # Heal the NPC
                            heal_amount = min(10, npc.max_hp - npc.hp)  # Default heal amount
                            npc.hp += heal_amount

                            # Remove from inventory
                            npc.inventory.remove(item)

                            event = f"{npc.name} uses {item_str} and heals {heal_amount} HP."
                            self.memory_manager.add_event(event)
                            npc.add_memory(f"I used {item_str} and healed {heal_amount} HP", 2)
                            return True
                        else:
                            event = f"{npc.name} considers using {item_str}, but is already at full health."
                            self.memory_manager.add_event(event)
                            return False

                    # Generic item use
                    event = f"{npc.name} uses {item_str}."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I used {item_str}", 1)
                    return True

            event = f"{npc.name} tries to use {target}, but doesn't have that item."
            self.memory_manager.add_event(event)
            return False

        # Handle examine action
        elif action_type in ["examine", "inspect", "look at"]:
            # This is mostly for flavor and information gathering
            event = f"{npc.name} examines {target} carefully."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I examined {target}", 1)
            return True

        return False

    def _handle_social_action(self, npc, target, action_type):
        """Handle social interactions with other characters"""
        # Find target character
        target_character = self._find_target_character(target)

        if not target_character:
            logger.debug(f"NPC {npc.name} tried to {action_type} {target}, but couldn't find the target")
            return False

        # Check if within interaction distance
        npc_x, npc_y = npc.position
        target_x, target_y = target_character.position
        distance = ((npc_x - target_x) ** 2 + (npc_y - target_y) ** 2) ** 0.5

        if distance > 1.5:  # Must be adjacent for social interaction
            approach_event = f"{npc.name} tries to approach {target_character.name}."
            self.memory_manager.add_event(approach_event)

            # Move towards target
            direction = self._calculate_direction_to_target(npc.position, target_character.position)
            current_x, current_y = npc.position
            new_x, new_y = current_x + direction[0], current_y + direction[1]

            move_result = self.world.map.move_character(npc, new_x, new_y)
            if move_result:
                npc.add_memory(f"I moved toward {target_character.name}", 1)
                return True
            else:
                npc.add_memory(f"I tried to move toward {target_character.name} but couldn't", 1)
                return False

        # Handle specific social actions
        if action_type == "talk" or action_type == "greet":
            # Already handled by dialog system, just add an event
            event = f"{npc.name} greets {target_character.name}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I greeted {target_character.name}", 1)
            return True

        elif action_type == "befriend":
            # Improve relationship
            current_relation = npc.get_relationship(target_character.id)
            npc.modify_relationship(target_character.id, 10)

            # Reciprocal relationship change (smaller)
            target_character.modify_relationship(npc.id, 5)

            event = f"{npc.name} makes a friendly gesture toward {target_character.name}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I tried to befriend {target_character.name}", 2)
            return True

        elif action_type == "threaten":
            # Worsen relationship
            current_relation = npc.get_relationship(target_character.id)
            npc.modify_relationship(target_character.id, -5)

            # Reciprocal relationship change (larger negative)
            target_character.modify_relationship(npc.id, -15)

            event = f"{npc.name} threatens {target_character.name}!"
            self.memory_manager.add_event(event)
            npc.add_memory(f"I threatened {target_character.name}", 2)

            # Possible combat result
            target_relation = target_character.get_relationship(npc.id)
            if target_relation < -50 and random.random() < 0.5:
                # Target may attack back
                self._handle_combat_action(target_character, npc.name, "attack")

            return True

        elif action_type == "compliment":
            # Improve relationship
            npc.modify_relationship(target_character.id, 5)
            target_character.modify_relationship(npc.id, 5)

            event = f"{npc.name} compliments {target_character.name}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I complimented {target_character.name}", 1)
            return True

        elif action_type == "insult":
            # Worsen relationship
            npc.modify_relationship(target_character.id, -10)
            target_character.modify_relationship(npc.id, -10)

            event = f"{npc.name} insults {target_character.name}!"
            self.memory_manager.add_event(event)
            npc.add_memory(f"I insulted {target_character.name}", 1)
            return True

        return False

    def _handle_rest_action(self, npc, target, action_type="rest"):
        """Handle resting, waiting, and similar passive actions"""
        # These actions are mainly for flavor but could heal the NPC over time

        if "sleep" in target.lower() or action_type == "sleep":
            # NPCs that sleep heal a small amount
            if npc.hp < npc.max_hp:
                heal_amount = min(2, npc.max_hp - npc.hp)
                npc.hp += heal_amount
                event = f"{npc.name} sleeps and recovers {heal_amount} HP."
            else:
                event = f"{npc.name} sleeps peacefully."

            self.memory_manager.add_event(event)
            npc.add_memory("I slept for a while", 1)
            return True

        else:  # Generic waiting/resting
            event = f"{npc.name} {action_type}s {target}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I {action_type}ed {target}", 1)
            return True

    def _handle_work_action(self, npc, target, action_type):
        """Handle crafting, building, and other work actions"""
        # These actions could create items or modify the world

        # Check for smithing/crafting actions
        if action_type in ["forge", "craft", "smith"] and npc.character_class == CharacterClass.MERCHANT:
            # Blacksmith creating an item
            if "sword" in target.lower() or "blade" in target.lower() or "weapon" in target.lower():
                # Add sword to inventory
                new_item = "sword"
                npc.inventory.append(new_item)

                event = f"{npc.name} forges a new {new_item}."
                self.memory_manager.add_event(event)
                npc.add_memory(f"I forged a {new_item}", 2)
                return True

            elif "armor" in target.lower() or "shield" in target.lower():
                # Add armor to inventory
                new_item = "shield" if "shield" in target.lower() else "armor"
                npc.inventory.append(new_item)

                event = f"{npc.name} crafts a new {new_item}."
                self.memory_manager.add_event(event)
                npc.add_memory(f"I crafted a {new_item}", 2)
                return True

        # Generic work action
        event = f"{npc.name} works on {target}."
        self.memory_manager.add_event(event)
        npc.add_memory(f"I worked on {target}", 1)
        return True

    def _find_target_character(self, target_name):
        """Enhanced method to find a character by name or description"""
        # Check for common player references
        player_terms = ["player", "adventurer", "traveler", "traveller", "stranger", "newcomer", "hero"]

        # Check for the player
        if any(term in target_name.lower() for term in player_terms):
            return self.player

        # Check for specific character names
        for npc_id, npc in self.npc_manager.npcs.items():
            if npc.name.lower() in target_name.lower():
                return npc

            # Also check by the first letter of name (common in the UI)
            if npc.name[0].lower() == target_name.lower():
                return npc

        # Try by class if no name match
        for npc_id, npc in self.npc_manager.npcs.items():
            if npc.character_class.value.lower() in target_name.lower():
                return npc

            # Check race too
            if npc.race.value.lower() in target_name.lower():
                return npc

        # If still no match but target is a single character, it might be a character symbol
        if len(target_name) == 1:
            for npc_id, npc in self.npc_manager.npcs.items():
                if npc.symbol.lower() == target_name.lower():
                    return npc

        return None

    def _find_nearby_characters(self, character, distance=2.0):
        """Find characters near the given character"""
        nearby = []
        char_x, char_y = character.position

        # Check all characters including player
        for pos, other_char in self.world.map.characters.items():
            if other_char.id == character.id:  # Skip self
                continue

            other_x, other_y = pos
            dist = ((char_x - other_x) ** 2 + (char_y - other_y) ** 2) ** 0.5

            if dist <= distance:
                nearby.append(other_char)

        return nearby

    def _calculate_direction_to_target(self, start_pos, target_pos):
        """Calculate the best direction to move towards a target"""
        dx = target_pos[0] - start_pos[0]
        dy = target_pos[1] - start_pos[1]

        # Normalize to single step
        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1

        # If diagonal, prioritize horizontal or vertical based on which is larger
        if dx != 0 and dy != 0:
            if abs(target_pos[0] - start_pos[0]) > abs(target_pos[1] - start_pos[1]):
                dy = 0
            else:
                dx = 0

        return (dx, dy)

    def pickup_item(self, item_name=None):
        """Player picks up an item from the ground"""
        player_x, player_y = self.player.position
        ground_items = self.world.get_items_at(player_x, player_y)

        if not ground_items:
            return "There's nothing here to pick up."

        # If specific item name provided, look for it
        if item_name:
            for item in ground_items:
                item_str = item.name if hasattr(item, 'name') else str(item)
                if item_name.lower() in item_str.lower():
                    # Add to inventory
                    self.player.inventory.append(item)

                    # Remove from ground
                    self.world.remove_item_from_ground(item, player_x, player_y)

                    # Add event
                    event = f"You pick up {item_str}."
                    self.memory_manager.add_event(event)

                    # Advance turn
                    self.advance_turn()

                    return event

            return f"You can't find {item_name} here."

        # Otherwise, pick up the first item
        item = ground_items[0]
        item_str = item.name if hasattr(item, 'name') else str(item)

        # Add to inventory
        self.player.inventory.append(item)

        # Remove from ground
        self.world.remove_item_from_ground(item, player_x, player_y)

        # Add event
        event = f"You pick up {item_str}."
        self.memory_manager.add_event(event)

        # Advance turn
        self.advance_turn()

        return event

    def drop_item(self, item_name):
        """Player drops an item to the ground"""
        if not item_name:
            return "You need to specify which item to drop."

        # Check inventory
        if not self.player.inventory:
            return "You don't have anything to drop."

        # Find matching item
        for item in self.player.inventory:
            item_str = item.name if hasattr(item, 'name') else str(item)
            if item_name.lower() in item_str.lower():
                # Remove from inventory
                self.player.inventory.remove(item)

                # Add to ground
                player_x, player_y = self.player.position
                self.world.add_item_to_ground(item, player_x, player_y)

                # Add event
                event = f"You drop {item_str}."
                self.memory_manager.add_event(event)

                # Advance turn
                self.advance_turn()

                return event

        return f"You don't have {item_name} in your inventory."

    def use_item(self, item_name):
        """Player uses an item from inventory"""
        if not item_name:
            return "You need to specify which item to use."

        # Check inventory
        if not self.player.inventory:
            return "You don't have anything to use."

        # Find matching item
        for item in self.player.inventory:
            item_str = item.name if hasattr(item, 'name') else str(item)
            if item_name.lower() in item_str.lower():
                # Handle different types of usable items

                # Healing items
                if "potion" in item_str.lower() or "healing" in item_str.lower() or "bandage" in item_str.lower():
                    if self.player.hp < self.player.max_hp:
                        # Heal the player
                        heal_amount = min(10, self.player.max_hp - self.player.hp)  # Default heal amount
                        self.player.hp += heal_amount

                        # Remove from inventory
                        self.player.inventory.remove(item)

                        # Add event
                        event = f"You use {item_str} and heal {heal_amount} HP."
                        self.memory_manager.add_event(event)

                        # Advance turn
                        self.advance_turn()

                        return event
                    else:
                        return f"You're already at full health."

                # Generic item use
                event = f"You use {item_str}."
                self.memory_manager.add_event(event)

                # Advance turn
                self.advance_turn()

                return event

        return f"You don't have {item_name} in your inventory."

    def attack_character(self, target_name):
        """Player attacks a character"""
        # Find the target character
        target_character = None

        # Check all NPCs
        for npc_id, npc in self.npc_manager.npcs.items():
            if npc.name.lower() == target_name.lower():
                target_character = npc
                break

        if not target_character:
            return f"You don't see {target_name} here."

        # Check if within attack range
        player_x, player_y = self.player.position
        target_x, target_y = target_character.position
        distance = ((player_x - target_x) ** 2 + (player_y - target_y) ** 2) ** 0.5

        if distance > 1.5:  # Not adjacent
            return f"{target_character.name} is too far away to attack."

        # Calculate hit chance and damage
        hit_chance = 0.7  # 70% base chance to hit
        damage = random.randint(5, 10)  # Random damage

        # Roll for hit
        if random.random() <= hit_chance:
            # Hit
            target_character.take_damage(damage)
            event = f"You attack {target_character.name} for {damage} damage!"
            self.memory_manager.add_event(event)

            # Update relationship
            target_character.modify_relationship(self.player.id, -20)

            # Check if enemy defeated
            if target_character.hp <= 0:
                defeat_event = f"You have defeated {target_character.name}!"
                self.memory_manager.add_event(defeat_event)

                # Remove from map
                self.world.map.remove_character(target_character)

                # Maybe drop an item
                if hasattr(target_character, 'inventory') and target_character.inventory:
                    item = random.choice(target_character.inventory)
                    self.world.add_item_to_ground(item, target_character.position[0], target_character.position[1])
                    target_character.inventory.remove(item)
                    drop_event = f"{target_character.name} drops {item}!"
                    self.memory_manager.add_event(drop_event)

                return event + " " + defeat_event
        else:
            # Miss
            event = f"You attack {target_character.name} but miss!"
            self.memory_manager.add_event(event)

        # Advance turn (which will trigger possible counterattack)
        self.advance_turn()

        return event
