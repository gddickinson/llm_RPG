"""
Memory Manager module for LLM-RPG
Handles tracking game events, history, and memory management
"""

import time
import logging
from typing import List, Dict, Any
import config

logger = logging.getLogger("llm_rpg.memory")

class MemoryManager:
    """Manages game events, history, and character memories"""
    
    def __init__(self, max_history=config.MAX_HISTORY_ITEMS):
        self.game_history = []
        self.max_history = max_history
        logger.info(f"Memory Manager initialized with max history: {max_history}")
    
    def add_event(self, event: str):
        """Add an event to the game history"""
        # Add timestamp
        timestamped_event = {
            "timestamp": time.time(),
            "game_time": None,  # Could be populated from game engine if needed
            "event": event
        }
        
        self.game_history.append(timestamped_event)
        logger.debug(f"Added event: {event}")
        
        # Trim history if needed
        if len(self.game_history) > self.max_history:
            self.game_history = self.game_history[-self.max_history:]
            logger.debug(f"Trimmed history to {self.max_history} items")
    
    def get_recent_history(self, count=10) -> List[str]:
        """Get a list of recent events"""
        events = self.game_history[-count:] if len(self.game_history) >= count else self.game_history
        return [e["event"] for e in events]
    
    def get_history_summary(self) -> str:
        """Generate a summary of the game history"""
        if not self.game_history:
            return "No events have occurred yet."
        
        # For simplicity, we'll just return the last 10 events
        # In a more sophisticated system, you could use LLM to summarize
        recent = self.get_recent_history(10)
        return "Recent events:\n" + "\n".join([f"- {event}" for event in recent])
    
    def get_location_history(self, location_name: str, count=5) -> List[str]:
        """Get events that occurred at a specific location"""
        location_events = []
        
        for event in reversed(self.game_history):
            if location_name.lower() in event["event"].lower():
                location_events.append(event["event"])
                if len(location_events) >= count:
                    break
        
        return location_events
    
    def get_character_history(self, character_name: str, count=5) -> List[str]:
        """Get events related to a specific character"""
        character_events = []
        
        for event in reversed(self.game_history):
            if character_name.lower() in event["event"].lower():
                character_events.append(event["event"])
                if len(character_events) >= count:
                    break
        
        return character_events
    
    def clear_history(self):
        """Clear all history"""
        self.game_history = []
        logger.info("Game history cleared")
    
    def save_history(self, filename: str):
        """Save history to a file"""
        try:
            import json
            with open(filename, 'w') as f:
                json.dump(self.game_history, f, indent=2)
            logger.info(f"Game history saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving history: {str(e)}")
            return False
    
    def load_history(self, filename: str):
        """Load history from a file"""
        try:
            import json
            with open(filename, 'r') as f:
                self.game_history = json.load(f)
            logger.info(f"Game history loaded from {filename}")
            return True
        except Exception as e:
            logger.error(f"Error loading history: {str(e)}")
            return False
