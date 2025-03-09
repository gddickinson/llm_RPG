"""
Threaded LLM Interface module for LLM-RPG
Handles communication with the local LLM (Llama3 via Ollama) using background threads
"""

import logging
import json
import requests
import threading
import queue
import time
from typing import Dict, List, Any, Optional, Callable

import config

logger = logging.getLogger("llm_rpg.threaded_llm")

class ThreadedLLMInterface:
    """Threaded version of LLM Interface that processes requests in background threads"""

    def __init__(self, model_name=config.DEFAULT_MODEL, api_url=config.LLM_API_URL, num_threads=2):
        self.model_name = model_name
        self.api_url = api_url
        self.request_queue = queue.Queue()
        self.result_cache = {}  # Cache responses to avoid duplicate calls
        self.cache_lock = threading.Lock()  # Lock for thread-safe cache access
        self.num_threads = num_threads
        self.workers = []
        self.running = True

        # Start worker threads
        for i in range(num_threads):
            thread = threading.Thread(target=self._worker_thread, daemon=True)
            thread.start()
            self.workers.append(thread)

        logger.info(f"Threaded LLM Interface initialized with {num_threads} worker threads using model: {model_name}")

    def _worker_thread(self):
        """Worker thread that processes LLM requests from the queue"""
        while self.running:
            try:
                # Get request from queue with timeout to allow checking self.running
                request_id, prompt, system_prompt, max_tokens, temperature, callback = self.request_queue.get(timeout=0.5)

                # Generate response
                response = self._generate_response_direct(prompt, system_prompt, max_tokens, temperature)

                # Store result in cache
                with self.cache_lock:
                    self.result_cache[request_id] = response

                # Call callback if provided
                if callback:
                    callback(response)

                # Mark task as done
                self.request_queue.task_done()

            except queue.Empty:
                # Queue is empty, just continue
                pass
            except Exception as e:
                logger.error(f"Error in LLM worker thread: {str(e)}")

    def _generate_response_direct(self, prompt, system_prompt="", max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE):
        """Send a prompt to the LLM and get a response (direct, non-queued version)"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            logger.debug(f"Sending prompt to LLM (length: {len(prompt)})")
            response = requests.post(self.api_url, json=payload)

            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Received response from LLM (length: {len(result.get('response', ''))})")
                return result.get("response", "")
            else:
                error_msg = f"Error from LLM API: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return f"Error: Failed to get response from LLM. Status code: {response.status_code}"

        except Exception as e:
            error_msg = f"Exception in LLM interface: {str(e)}"
            logger.error(error_msg)
            return f"Error: {str(e)}"

    def generate_response(self, prompt, system_prompt="", max_tokens=config.DEFAULT_MAX_TOKENS, temperature=config.DEFAULT_TEMPERATURE, callback=None):
        """Queue a request to generate a response and return immediately"""
        # Generate a unique request ID
        request_id = f"{hash(prompt)}-{hash(system_prompt)}-{time.time()}"

        # Add request to queue
        self.request_queue.put((request_id, prompt, system_prompt, max_tokens, temperature, callback))

        return request_id

    def get_response(self, request_id, timeout=None):
        """Get the response for a queued request, waiting if necessary"""
        start_time = time.time()

        while timeout is None or time.time() - start_time < timeout:
            with self.cache_lock:
                if request_id in self.result_cache:
                    response = self.result_cache[request_id]
                    # Remove from cache to free memory
                    del self.result_cache[request_id]
                    return response

            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)

        # If we get here, the timeout has expired
        return "Error: LLM response timed out"

    def get_npc_action(self, character, world_state, game_history, visible_map, callback=None):
        """Generate NPC's next action based on character, world state and history"""
        # Create a prompt that gives the LLM all necessary context
        system_prompt = config.NPC_ACTION_SYSTEM_PROMPT

        # Combine all relevant information into a comprehensive prompt
        prompt = f"""
CHARACTER SHEET:
{json.dumps(character.to_dict(), indent=2)}

CURRENT LOCATION:
{world_state['current_location']}

TIME OF DAY:
{world_state['time_of_day']}

VISIBLE ENVIRONMENT:
{visible_map}

RECENT HISTORY:
{game_history[-5:] if len(game_history) > 5 else game_history}

MEMORIES:
{[memory['event'] for memory in character.memories[-10:]] if len(character.memories) > 10 else [memory['event'] for memory in character.memories]}

Based on this information, what does {character.name} do next?
"""

        def process_response(response):
            """Process the LLM response into a structured action"""
            action_data = self._parse_action_response(response)
            logger.info(f"Generated action for {character.name}: {action_data['action']} {action_data['target']}")

            return action_data

        # If we have a callback, use async processing
        if callback:
            request_id = self.generate_response(
                prompt,
                system_prompt,
                temperature=0.8,
                callback=lambda response: callback(process_response(response))
            )
            return None
        else:
            # Synchronous processing
            request_id = self.generate_response(prompt, system_prompt, temperature=0.8)
            response = self.get_response(request_id)
            return process_response(response)

    def _parse_action_response(self, response):
        """Parse the LLM's response into a structured action"""
        action_data = {
            "action": "",
            "target": "",
            "dialog": "",
            "thoughts": "",
            "emotion": "",
            "goal_update": ""
        }

        # Extract fields from response
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            if line.startswith("ACTION:"):
                action_data["action"] = line[len("ACTION:"):].strip()
            elif line.startswith("TARGET:"):
                action_data["target"] = line[len("TARGET:"):].strip()
            elif line.startswith("DIALOG:"):
                action_data["dialog"] = line[len("DIALOG:"):].strip()
            elif line.startswith("THOUGHTS:"):
                action_data["thoughts"] = line[len("THOUGHTS:"):].strip()
            elif line.startswith("EMOTION:"):
                action_data["emotion"] = line[len("EMOTION:"):].strip()
            elif line.startswith("GOAL_UPDATE:"):
                action_data["goal_update"] = line[len("GOAL_UPDATE:"):].strip()

        # Default handling for missing data
        if not action_data["action"]:
            action_data["action"] = "wait"
            action_data["target"] = "for something to happen"

        return action_data

    def generate_npc_dialog(self, character, player_message, recent_history):
        """Generate dialog response from an NPC to the player"""

        system_prompt = f"""You are roleplaying as {character.name}, a {character.race.value} {character.character_class.value} in a fantasy RPG.
Respond to the player in character, according to your personality, goals, and memories.
Keep your response brief and conversational."""

        prompt = f"""
CHARACTER SHEET:
{json.dumps(character.to_dict(), indent=2)}

RECENT CONVERSATION:
{recent_history[-3:] if len(recent_history) > 3 else recent_history}

PLAYER SAYS: "{player_message}"

How does {character.name} respond?
"""

        request_id = self.generate_response(prompt, system_prompt, temperature=0.7)
        response = self.get_response(request_id)

        # Clean up response if needed (remove quotes, etc.)
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]

        return response

    def shutdown(self):
        """Shutdown the threaded interface"""
        self.running = False
        for thread in self.workers:
            thread.join(timeout=1.0)
        logger.info("Threaded LLM Interface shutdown")
