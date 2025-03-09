"""
Location module for LLM-RPG
Defines the Location class for named areas in the game world
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("llm_rpg.location")

class Location:
    """Represents a named location in the world"""
    
    def __init__(self, name: str, description: str, x: int, y: int, width: int, height: int):
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = {}  # For additional location-specific properties
        self.npcs = []  # IDs of NPCs that belong to this location
        logger.debug(f"Created location: {name} at ({x},{y}) size {width}x{height}")
    
    def contains(self, x: int, y: int) -> bool:
        """Check if coordinates are within this location"""
        return (self.x <= x < self.x + self.width) and (self.y <= y < self.y + self.height)
    
    def center(self) -> tuple:
        """Get the center coordinates of the location"""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def add_property(self, key: str, value: Any) -> None:
        """Add a property to the location"""
        self.properties[key] = value
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property of the location"""
        return self.properties.get(key, default)
    
    def add_npc(self, npc_id: str) -> None:
        """Associate an NPC with this location"""
        if npc_id not in self.npcs:
            self.npcs.append(npc_id)
            logger.debug(f"Added NPC {npc_id} to location {self.name}")
    
    def remove_npc(self, npc_id: str) -> None:
        """Remove an NPC association from this location"""
        if npc_id in self.npcs:
            self.npcs.remove(npc_id)
            logger.debug(f"Removed NPC {npc_id} from location {self.name}")
    
    def to_dict(self) -> Dict:
        """Convert location to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "position": (self.x, self.y),
            "size": (self.width, self.height),
            "properties": self.properties,
            "npcs": self.npcs
        }
    
    def __str__(self) -> str:
        """String representation of the location"""
        return f"{self.name} ({self.x},{self.y})"


class LocationFactory:
    """Factory for creating common location types"""
    
    @staticmethod
    def create_tavern(name: str, x: int, y: int) -> Location:
        """Create a tavern location"""
        tavern = Location(name, f"A cozy tavern with a warm hearth", x, y, 2, 2)
        tavern.add_property("type", "tavern")
        tavern.add_property("serves_food", True)
        tavern.add_property("serves_drink", True)
        tavern.add_property("has_rooms", True)
        return tavern
    
    @staticmethod
    def create_shop(name: str, shop_type: str, x: int, y: int) -> Location:
        """Create a shop location"""
        descriptions = {
            "general": "A shop with various goods and supplies",
            "blacksmith": "A busy blacksmith shop with the sound of hammering",
            "apothecary": "A shop filled with herbs and potions",
            "magic": "A mysterious shop with magical items",
            "armor": "A shop specializing in armor and shields",
            "weapons": "A shop with weapons displayed on the walls"
        }
        
        description = descriptions.get(shop_type, "A small shop")
        shop = Location(name, description, x, y, 2, 2)
        shop.add_property("type", "shop")
        shop.add_property("shop_type", shop_type)
        return shop
    
    @staticmethod
    def create_temple(name: str, deity: str, x: int, y: int) -> Location:
        """Create a temple location"""
        temple = Location(name, f"A temple dedicated to {deity}", x, y, 2, 2)
        temple.add_property("type", "temple")
        temple.add_property("deity", deity)
        temple.add_property("offers_healing", True)
        return temple
    
    @staticmethod
    def create_cave(name: str, x: int, y: int) -> Location:
        """Create a cave location"""
        cave = Location(name, "A dark cave entrance", x, y, 1, 1)
        cave.add_property("type", "cave")
        cave.add_property("explored", False)
        cave.add_property("danger_level", 3)
        return cave
