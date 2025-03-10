# ===========================================================
# File: engine/npc_process.py
# ===========================================================

import logging
import time
import json
import os
import sys
from typing import Dict, Any

from config import NPC_ACTION_ENHANCED_PROMPT

# Configure logging for the NPC process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"npc_process_{os.getpid()}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(f"npc_process")

def npc_process_main(npc_id, command_queue, response_queue, shared_state, llm_model):
    """Main function for an NPC process"""
    try:
        # Initialize LLM for this process
        from llm.llm_interface import LLMInterface
        llm = LLMInterface(model_name=llm_model)

        logger.info(f"NPC process {npc_id} started with model {llm_model}")

        # Process initialization
        npc_data = None
        running = True

        while running and shared_state.get("game_running", True):
            try:
                # Check for commands
                if not command_queue.empty():
                    command = command_queue.get()

                    if command["command"] == "shutdown":
                        running = False
                        logger.info(f"NPC process {npc_id} shutting down")

                    elif command["command"] == "update_npc":
                        npc_data = command["data"]
                        logger.info(f"NPC {npc_id} data updated: {npc_data.get('name', 'unknown')}")


                    elif command["command"] == "set_status":
                        # Update character status directly
                        if npc_data:
                            npc_data["status"] = command["data"]
                            logger.info(f"NPC {npc_id} status updated to: {command['data']}")
                        else:
                            logger.warning(f"Cannot update status for NPC {npc_id}: No NPC data")


                    elif command["command"] == "get_action":
                        # Skip generating actions for non-active NPCs
                        if npc_data and npc_data.get("status") != "alive":
                            logger.debug(f"Skipping action generation for non-active NPC {npc_id} (status: {npc_data.get('status')})")
                            response_queue.put({
                                "type": "status",
                                "status": npc_data.get("status", "unknown")
                            })
                            continue


                    elif command["command"] == "get_action":
                        # Skip if we don't have NPC data yet
                        if not npc_data:
                            logger.warning(f"Cannot generate action for NPC {npc_id}: No NPC data")
                            continue

                        # Extract data needed for decision
                        world_state = command["data"]["world_state"]
                        game_history = command["data"]["game_history"]
                        visible_map = command["data"]["visible_map"]

                        logger.info(f"Generating action for NPC {npc_data.get('name', npc_id)}")

                        # Generate NPC action using LLM
                        try:
                            # Convert dict back to Character object (simplified)
                            from characters.character import Character
                            from characters.character_types import CharacterClass, CharacterRace

                            char = Character(
                                id=npc_data["id"],
                                name=npc_data["name"],
                                character_class=CharacterClass(npc_data["class"]),
                                race=CharacterRace(npc_data["race"]),
                                level=npc_data["level"],
                                strength=npc_data["stats"]["strength"],
                                dexterity=npc_data["stats"]["dexterity"],
                                constitution=npc_data["stats"]["constitution"],
                                intelligence=npc_data["stats"]["intelligence"],
                                wisdom=npc_data["stats"]["wisdom"],
                                charisma=npc_data["stats"]["charisma"],
                                hp=npc_data["hp"],
                                max_hp=npc_data["max_hp"],
                                position=npc_data["position"],
                                goals=npc_data["goals"],
                                personality=npc_data["personality"],
                                relationships=npc_data["relationships"]
                            )

                            # Get character memories
                            if "memories" in npc_data:
                                char.memories = npc_data["memories"]

                            # Generate action
                            try:
                                # First try with the enhanced prompt (for ThreadedLLMInterface which supports system_prompt)
                                action = llm.get_npc_action(char, world_state, game_history, visible_map, system_prompt=NPC_ACTION_ENHANCED_PROMPT)
                            except TypeError:
                                # Fallback to original method (for LLMInterface which doesn't support system_prompt)
                                action = llm.get_npc_action(char, world_state, game_history, visible_map)

                            # Send response back to main process
                            response_queue.put({
                                "type": "action",
                                "action_data": action
                            })

                            logger.info(f"Generated action for {char.name}: {action.get('action', 'unknown')} {action.get('target', '')}")

                        except Exception as e:
                            logger.error(f"Error generating action: {str(e)}")
                            # Send a default action
                            response_queue.put({
                                "type": "action",
                                "action_data": {
                                    "action": "wait",
                                    "target": "patiently",
                                    "thoughts": "I'm a bit confused right now.",
                                    "dialog": "",
                                    "emotion": "confused",
                                    "goal_update": ""
                                }
                            })

                    elif command["command"] == "get_dialog":
                        # Skip if we don't have NPC data yet
                        if not npc_data:
                            logger.warning(f"Cannot generate dialog for NPC {npc_id}: No NPC data")
                            continue

                        # Generate dialog response
                        player_message = command["data"]["message"]
                        recent_history = command["data"]["recent_history"]

                        logger.info(f"Generating dialog for NPC {npc_data.get('name', npc_id)}")

                        try:
                            # Convert dict back to Character object (simplified)
                            from characters.character import Character
                            from characters.character_types import CharacterClass, CharacterRace

                            char = Character(
                                id=npc_data["id"],
                                name=npc_data["name"],
                                character_class=CharacterClass(npc_data["class"]),
                                race=CharacterRace(npc_data["race"]),
                                level=npc_data["level"],
                                strength=npc_data["stats"]["strength"],
                                dexterity=npc_data["stats"]["dexterity"],
                                constitution=npc_data["stats"]["constitution"],
                                intelligence=npc_data["stats"]["intelligence"],
                                wisdom=npc_data["stats"]["wisdom"],
                                charisma=npc_data["stats"]["charisma"],
                                hp=npc_data["hp"],
                                max_hp=npc_data["max_hp"],
                                position=npc_data["position"],
                                goals=npc_data["goals"],
                                personality=npc_data["personality"],
                                relationships=npc_data["relationships"]
                            )

                            # Generate response
                            response = llm.generate_npc_dialog(char, player_message, recent_history)

                            # Send response back
                            response_queue.put({
                                "type": "dialog",
                                "response": response
                            })

                            logger.info(f"Generated dialog for {char.name}")

                        except Exception as e:
                            logger.error(f"Error generating dialog: {str(e)}")
                            # Send a default response
                            response_queue.put({
                                "type": "dialog",
                                "response": "Hmm... Let me think about that."
                            })


                    elif command["command"] == "suspend":
                        # Enter a low-activity state to save resources
                        # Just acknowledge the command and wait for further instructions
                        logger.info(f"NPC process {npc_id} suspended")
                        response_queue.put({
                            "type": "status",
                            "status": "suspended"
                        })

                        # Wait for unsuspend or shutdown command
                        suspended = True
                        while suspended and shared_state.get("game_running", True):
                            try:
                                if not command_queue.empty():
                                    cmd = command_queue.get()

                                    if cmd["command"] == "shutdown":
                                        # Exit suspend mode and terminate
                                        logger.info(f"NPC process {npc_id} shutdown while suspended")
                                        running = False
                                        suspended = False
                                    elif cmd["command"] == "unsuspend" or cmd["command"] == "update_npc":
                                        # Exit suspend mode and continue
                                        logger.info(f"NPC process {npc_id} resuming from suspension")
                                        suspended = False

                                        # If this was an update_npc command, process it
                                        if cmd["command"] == "update_npc":
                                            npc_data = cmd["data"]
                                            logger.info(f"NPC {npc_id} data updated during unsuspend")

                                    # Acknowledge the command
                                    response_queue.put({
                                        "type": "status",
                                        "status": "acknowledged"
                                    })
                            except Exception as e:
                                logger.error(f"Error during suspension for NPC {npc_id}: {str(e)}")

                            # Sleep longer while suspended to save resources
                            time.sleep(0.5)


                # Small delay to prevent CPU overuse
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in NPC process {npc_id}: {str(e)}")
                # Send error to main process
                response_queue.put({
                    "type": "error",
                    "error": str(e)
                })

        logger.info(f"NPC process {npc_id} terminated")

    except Exception as e:
        logger.error(f"Fatal error in NPC process {npc_id}: {str(e)}")
