"""
World module for LLM-RPG
Manages the game world, including locations and time
"""

import logging
from typing import List, Optional
from world.world_map import WorldMap
from world.location import Location
import config

logger = logging.getLogger("llm_rpg.world")

class World:
    """Manages the game world state"""
    
    def __init__(self, width=config.DEFAULT_MAP_WIDTH, height=config.DEFAULT_MAP_HEIGHT):
        self.map = WorldMap(width, height)
        self.locations = []
        self.time = 0  # Game time in minutes
        logger.info(f"World initialized with size {width}x{height}")
    
    def add_location(self, location: Location):
        """Add a named location to the world"""
        self.locations.append(location)
        logger.debug(f"Added location: {location.name}")
    
    def get_location_at(self, x: int, y: int) -> Optional[Location]:
        """Get the location at coordinates"""
        for location in self.locations:
            if location.contains(x, y):
                return location
        return None
    
    def advance_time(self, minutes: int):
        """Advance game time by specified minutes"""
        self.time += minutes
    
    def get_time_of_day(self) -> str:
        """Get the current time of day"""
        hours = (self.time // 60) % 24
        if 6 <= hours < 12:
            return "morning"
        elif 12 <= hours < 17:
            return "afternoon"
        elif 17 <= hours < 21:
            return "evening"
        else:
            return "night"
    
    def get_formatted_time(self) -> str:
        """Get a formatted string representing current time"""
        days = self.time // (24 * 60)
        hours = (self.time // 60) % 24
        minutes = self.time % 60
        return f"Day {days+1}, {hours:02d}:{minutes:02d} ({self.get_time_of_day()})"
    
    def create_simple_world(self):
        """Create a simple demo world"""
        # Create a village
        self.add_location(Location("Oakvale Village", "A small peaceful village surrounded by forests", 10, 5, 10, 10))
        
        # Add terrain features
        from world.world_map import TerrainType
        
        # Forest surrounding the village
        self.map.add_terrain_feature(TerrainType.FOREST, 5, 0, 20, 5)
        self.map.add_terrain_feature(TerrainType.FOREST, 5, 15, 20, 5)
        self.map.add_terrain_feature(TerrainType.FOREST, 5, 5, 5, 10)
        self.map.add_terrain_feature(TerrainType.FOREST, 20, 5, 5, 10)
        
        # River running through
        self.map.add_terrain_feature(TerrainType.WATER, 0, 10, 30, 2)
        
        # Road
        self.map.add_terrain_feature(TerrainType.ROAD, 0, 7, 30, 1)
        
        # Village buildings
        self.map.add_terrain_feature(TerrainType.BUILDING, 12, 6, 2, 2)  # Tavern
        self.add_location(Location("Oakvale Tavern", "A cozy tavern with a warm hearth", 12, 6, 2, 2))
        
        self.map.add_terrain_feature(TerrainType.BUILDING, 16, 6, 2, 2)  # Blacksmith
        self.add_location(Location("Durgan's Forge", "A busy blacksmith shop with the sound of hammering", 16, 6, 2, 2))
        
        self.map.add_terrain_feature(TerrainType.BUILDING, 12, 10, 2, 2)  # Shop
        self.add_location(Location("General Store", "A shop with various goods and supplies", 12, 10, 2, 2))
        
        self.map.add_terrain_feature(TerrainType.BUILDING, 16, 10, 2, 2)  # Temple
        self.add_location(Location("Temple of Light", "A small temple dedicated to the gods of light", 16, 10, 2, 2))
        
        # Mountain in the distance
        self.map.add_terrain_feature(TerrainType.MOUNTAIN, 25, 0, 5, 5)
        self.add_location(Location("Misty Mountains", "Tall mountains shrouded in mist", 25, 0, 5, 5))
        
        # Cave
        self.map.add_terrain_feature(TerrainType.CAVE, 27, 3, 1, 1)
        self.add_location(Location("Dark Cave", "A mysterious cave entrance in the mountainside", 27, 3, 1, 1))
        
        logger.info("Simple world created")
