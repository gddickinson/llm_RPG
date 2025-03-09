"""
LLM Interface module for LLM-RPG
Handles communication with the local LLM (Llama3 via Ollama)
"""

import logging
import json
import requests
from typing import Dict, List, Any, Optional

import config

logger = logging.getLogger("llm_rpg.llm")

class LLMInterface:
    """Handles communication with the LLM (Llama3 via Ollama)"""
    
    def __init__(self, model_name=config.DEFAULT_MODEL, api_url=config.LLM_API_URL):
        self.model_name = model_name
        self.api_url = api_url
        logger.info(f"LLM Interface initialized with model: {model_name}")
    
    def generate_response(self, prompt: str, system_prompt: str = "", 
                          max_tokens: int = config.DEFAULT_MAX_TOKENS, 
                          temperature: float = config.DEFAULT_TEMPERATURE) -> str:
        """Send a prompt to the LLM and get a response"""
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
    
    def get_npc_action(self, character: Any, world_state: Dict, 
                       game_history: List[str], visible_map: str) -> Dict:
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
        
        # Get response from LLM
        response = self.generate_response(prompt, system_prompt, temperature=0.8)
        
        # Parse the response into structured action data
        action_data = self._parse_action_response(response)
        logger.info(f"Generated action for {character.name}: {action_data['action']} {action_data['target']}")
        
        return action_data
    
    def _parse_action_response(self, response: str) -> Dict:
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
        
        # If the LLM didn't provide a structured response, try to extract info anyway
        if not action_data["action"] and "wait" in response.lower():
            action_data["action"] = "wait"
            action_data["target"] = "patiently"
        
        # Default to waiting if we couldn't parse any action
        if not action_data["action"]:
            action_data["action"] = "wait"
            action_data["target"] = "for something to happen"
            action_data["thoughts"] = "I'm not sure what to do right now"
            logger.warning(f"Failed to parse LLM response, defaulting to wait: {response[:100]}...")
        
        return action_data
    
    def generate_npc_dialog(self, character: Any, player_message: str, 
                           recent_history: List[str]) -> str:
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
        
        response = self.generate_response(prompt, system_prompt, temperature=0.7)
        
        # Clean up response if needed (remove quotes, etc.)
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        return response
