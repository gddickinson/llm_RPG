"""
Core Game Engine module for LLM-RPG
Coordinates all game components and manages game state
"""

import logging
import time
from typing import Dict, Any, List, Optional

from world.world import World
from characters.npc_manager import NPCManager
from characters.character import Character
from llm.llm_interface import LLMInterface
from engine.memory_manager import MemoryManager
import config

logger = logging.getLogger("llm_rpg.engine")

class GameEngine:
    """Main game engine that coordinates all game modules"""

    def __init__(self, llm_model=config.DEFAULT_MODEL):
        """Initialize the game engine with all necessary components"""
        self.world = World()
        self.npc_manager = NPCManager()
        self.memory_manager = MemoryManager()

        # Use the threaded LLM interface instead of the basic one
        try:
            from llm.threaded_llm_interface import ThreadedLLMInterface
            self.llm_interface = ThreadedLLMInterface(model_name=llm_model, num_threads=2)
            logger.info("Using threaded LLM interface")
        except ImportError:
            # Fallback to basic interface if threaded version is not available
            from llm.llm_interface import LLMInterface
            self.llm_interface = LLMInterface(model_name=llm_model)
            logger.info("Using basic LLM interface (threaded version not found)")

        self.player = None
        self.running = False
        self.turn_counter = 0
        self.processing_npcs = set()  # Track NPCs being processed

        # Initialize simple demo world
        self.initialize_demo_game()

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
        """Process an NPC's action based on LLM response"""
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
        if action == "move" or "move" in action:
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
                                break

                        if not alt_result:
                            logger.debug(f"NPC {npc.name} failed to move to ({new_x}, {new_y}) and all alternates")
                else:
                    logger.debug(f"NPC {npc.name} wants to move but direction unclear: {target}")

            except Exception as e:
                logger.error(f"Error processing move action for {npc.name}: {str(e)}")


        # Handle other action types
        elif action == "talk":
            # Find the target character
            target_character = None

            if target.lower() == "player":
                target_character = self.player
            else:
                # Check if target is a nearby NPC by name
                for _, other_npc in self.npc_manager.npcs.items():
                    if other_npc.name.lower() == target.lower():
                        target_character = other_npc
                        break

            if target_character:
                # Check if within talking distance
                npc_x, npc_y = npc.position
                target_x, target_y = target_character.position
                distance = ((npc_x - target_x) ** 2 + (npc_y - target_y) ** 2) ** 0.5

                if distance <= 1.5:  # Adjacent or diagonal
                    # Dialog should have been processed above
                    pass
                else:
                    # Character is too far away
                    event = f"{npc.name} tries to talk to {target_character.name}, but they're too far away."
                    self.memory_manager.add_event(event)
                    npc.add_memory(f"I tried to talk to {target_character.name}, but they were too far away", 1)

        elif action == "wait":
            event = f"{npc.name} {target}."
            self.memory_manager.add_event(event)
            npc.add_memory(f"I waited and {target}", 1)

        # Additional action types can be added here

        # Log the action for debugging
        logger.debug(f"NPC {npc.name} action processed: {action} {target}")

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

            # Have NPC respond using the LLM
            # This would be a more complex version of get_npc_action specialized for dialog
            response = self._get_npc_dialog_response(npc, message)

            # Add NPC's response to history
            self.memory_manager.add_event(f"{npc.name} says: \"{response}\"")

            # Add to NPC's memory
            npc.add_memory(f"Player said: \"{message}\". I replied: \"{response}\"", 2)

            # Advance turn
            self.advance_turn()

            return response
        else:
            # Just a basic interaction without dialog
            self.memory_manager.add_event(f"You approach {npc.name}.")

            # Add to NPC's memory
            npc.add_memory(f"Player approached me", 1)

            # Get initial greeting from NPC
            greeting = self._get_npc_greeting(npc)

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
        """Process NPC actions asynchronously"""
        # Only process NPC turns periodically to reduce LLM calls
        if self.turn_counter % config.NPC_ACTION_INTERVAL != 0:
            return

        # Check if we're using the threaded interface
        if not hasattr(self.llm_interface, 'get_response'):
            # Fallback to synchronous processing if we don't have a threaded interface
            return self.process_npc_turns()

        logger.debug("Processing NPC turns asynchronously")

        # Process each NPC
        for npc_id, npc in self.npc_manager.npcs.items():
            # Skip if this NPC is already being processed
            if npc_id in self.processing_npcs:
                continue

            try:
                # Skip NPCs that are too far from the player (optimization)
                npc_x, npc_y = npc.position
                player_x, player_y = self.player.position
                distance = ((npc_x - player_x) ** 2 + (npc_y - player_y) ** 2) ** 0.5

                # Only process NPCs within a certain range of the player
                if distance > config.DEFAULT_VISIBILITY_RANGE * 2:
                    continue

                # Add this NPC to processing set
                self.processing_npcs.add(npc_id)

                # Get visible environment for the NPC
                visible_map = self.world.map.get_visible_description(npc_x, npc_y)

                # Get game state information
                world_state = {
                    "current_location": self.world.get_location_at(npc_x, npc_y).name if self.world.get_location_at(npc_x, npc_y) else "wilderness",
                    "time_of_day": self.world.get_time_of_day()
                }

                # Get recent history
                game_history = self.memory_manager.get_recent_history()

                # Define callback for when NPC action is ready
                def on_npc_action_ready(action_data, npc_id=npc_id):
                    try:
                        # Process the action
                        npc = self.npc_manager.get_npc(npc_id)
                        if npc:
                            self._process_npc_action(npc, action_data)
                    except Exception as e:
                        logger.error(f"Error processing async NPC action for {npc_id}: {str(e)}")
                    finally:
                        # Always remove from processing set
                        self.processing_npcs.discard(npc_id)

                # Get NPC action from LLM asynchronously
                try:
                    self.llm_interface.get_npc_action(
                        npc,
                        world_state,
                        game_history,
                        visible_map,
                        callback=on_npc_action_ready
                    )
                except TypeError as e:
                    # In case the LLM interface doesn't support callbacks
                    logger.warning(f"Async NPC processing not supported: {str(e)}")
                    self.processing_npcs.discard(npc_id)
                    return self.process_npc_turns()

            except Exception as e:
                logger.error(f"Error processing NPC {npc_id}: {str(e)}")
                self.processing_npcs.discard(npc_id)

    # Update the shutdown method to clean up the threaded LLM interface
    def end_game(self):
        """End the game"""
        self.running = False

        # Add game end event
        self.memory_manager.add_event("The adventure has ended.")

        # Shutdown the threaded LLM interface if available
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
