"""
Character module for LLM-RPG
Defines the base Character class used for both player and NPCs
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from characters.character_types import CharacterClass, CharacterRace

logger = logging.getLogger("llm_rpg.character")

@dataclass
class Character:
    """Base class for all characters (PC and NPCs)"""

    id: str
    name: str
    character_class: CharacterClass
    race: CharacterRace
    level: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    hp: int
    max_hp: int
    position: Tuple[int, int] = field(default=(0, 0))
    inventory: List[Any] = field(default_factory=list)
    gold: int = field(default=0)
    symbol: str = field(default="C")
    description: str = field(default="")
    personality: Dict[str, Any] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, int] = field(default_factory=dict)
    memories: List[Dict[str, Any]] = field(default_factory=list)

    def add_memory(self, event: str, importance: int = 1) -> None:
        """Add a memory to the character's memory list"""
        memory = {
            "event": event,
            "importance": importance,
            "time": time.time()  # Real-world timestamp for easy tracking
        }
        self.memories.append(memory)

        # Sort memories by importance
        self.memories.sort(key=lambda m: m["importance"], reverse=True)

        logger.debug(f"Added memory to {self.name}: {event} (importance: {importance})")

    def modify_relationship(self, character_id: str, change: int) -> None:
        """Modify relationship with another character"""
        current = self.relationships.get(character_id, 0)
        self.relationships[character_id] = max(-100, min(100, current + change))

        logger.debug(f"Modified relationship: {self.name} -> {character_id} by {change} (now: {self.relationships[character_id]})")

    def get_relationship(self, character_id: str) -> int:
        """Get relationship value with another character"""
        return self.relationships.get(character_id, 0)

    def get_relationship_description(self, character_id: str) -> str:
        """Get description of relationship with another character"""
        value = self.get_relationship(character_id)

        if value >= 80:
            return "close friend"
        elif value >= 60:
            return "friend"
        elif value >= 30:
            return "acquaintance"
        elif value >= 0:
            return "neutral"
        elif value >= -30:
            return "dislikes"
        elif value >= -60:
            return "enemy"
        else:
            return "sworn enemy"

    def add_item(self, item: Any) -> None:
        """Add an item to the character's inventory"""
        self.inventory.append(item)

        item_name = item.name if hasattr(item, "name") else str(item)
        logger.debug(f"{self.name} added item to inventory: {item_name}")

    def remove_item(self, item: Any) -> bool:
        """Remove an item from the character's inventory"""
        item_name = item.name if hasattr(item, "name") else str(item)

        # Check if we have this exact item
        if item in self.inventory:
            self.inventory.remove(item)
            logger.debug(f"{self.name} removed item from inventory: {item_name}")
            return True

        # Check by name if we have a similar item
        for inv_item in list(self.inventory):
            inv_item_name = inv_item.name if hasattr(inv_item, "name") else str(inv_item)
            if inv_item_name == item_name:
                self.inventory.remove(inv_item)
                logger.debug(f"{self.name} removed item from inventory: {item_name}")
                return True

        logger.debug(f"{self.name} failed to remove item: {item_name} (not found)")
        return False

    def has_item(self, item_name: str) -> bool:
        """Check if character has an item by name"""
        for item in self.inventory:
            if (hasattr(item, "name") and item.name == item_name) or str(item) == item_name:
                return True
        return False

    def modify_gold(self, amount: int) -> int:
        """Add or remove gold, returns new amount"""
        self.gold += amount
        logger.debug(f"{self.name} gold modified by {amount} (now: {self.gold})")
        return self.gold

    def take_damage(self, amount: int) -> int:
        """Character takes damage, returns remaining HP"""
        self.hp = max(0, self.hp - amount)
        logger.debug(f"{self.name} took {amount} damage (now: {self.hp}/{self.max_hp})")
        return self.hp

    def heal(self, amount: int) -> int:
        """Character heals damage, returns new HP"""
        self.hp = min(self.max_hp, self.hp + amount)
        logger.debug(f"{self.name} healed {amount} HP (now: {self.hp}/{self.max_hp})")
        return self.hp

    def is_alive(self) -> bool:
        """Check if character is alive"""
        return self.hp > 0

    def add_goal(self, goal: str) -> None:
        """Add a goal to the character"""
        if goal not in self.goals:
            self.goals.append(goal)
            logger.debug(f"{self.name} added goal: {goal}")

    def remove_goal(self, goal: str) -> bool:
        """Remove a goal from the character"""
        if goal in self.goals:
            self.goals.remove(goal)
            logger.debug(f"{self.name} removed goal: {goal}")
            return True
        logger.debug(f"{self.name} failed to remove goal: {goal} (not found)")
        return False

    def get_stat_modifier(self, stat: str) -> int:
        """Get the modifier for a stat"""
        stat_value = getattr(self, stat.lower(), 10)
        return (stat_value - 10) // 2

    def to_dict(self) -> Dict:
        """Convert character to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "class": self.character_class.value,
            "race": self.race.value,
            "level": self.level,
            "stats": {
                "strength": self.strength,
                "dexterity": self.dexterity,
                "constitution": self.constitution,
                "intelligence": self.intelligence,
                "wisdom": self.wisdom,
                "charisma": self.charisma
            },
            "hp": self.hp,
            "max_hp": self.max_hp,
            "position": self.position,
            "inventory": [item.name if hasattr(item, "name") else str(item) for item in self.inventory],
            "gold": self.gold,
            "description": self.description,
            "personality": self.personality,
            "goals": self.goals,
            "relationships": self.relationships
        }

    def __str__(self) -> str:
        """String representation of the character"""
        return f"{self.name} (Level {self.level} {self.race.value} {self.character_class.value})"
