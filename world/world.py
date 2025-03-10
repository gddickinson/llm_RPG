"""
World module for LLM-RPG
Manages the game world, including locations and time
"""

import logging
from typing import List, Optional
from world.world_map import WorldMap, TerrainType
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

    def add_item_to_ground(self, item, x, y):
        """Add an item to the ground at the specified location"""
        if not hasattr(self, 'ground_items'):
            self.ground_items = {}  # Initialize if not exists

        pos = (x, y)
        if pos not in self.ground_items:
            self.ground_items[pos] = []

        self.ground_items[pos].append(item)
        logger.debug(f"Added item {item} to ground at {pos}")

    def remove_item_from_ground(self, item, x, y):
        """Remove an item from the ground at the specified location"""
        if not hasattr(self, 'ground_items'):
            return False

        pos = (x, y)
        if pos in self.ground_items and item in self.ground_items[pos]:
            self.ground_items[pos].remove(item)
            logger.debug(f"Removed item {item} from ground at {pos}")

            # Clean up empty lists
            if not self.ground_items[pos]:
                del self.ground_items[pos]

            return True

        return False

    def get_items_at(self, x, y):
        """Get all items at the specified location"""
        if not hasattr(self, 'ground_items'):
            self.ground_items = {}

        pos = (x, y)
        return self.ground_items.get(pos, [])

    def add_revival_shrine(self, x, y, radius=3):
        """Add a revival shrine that can revive defeated characters"""
        shrine = {
            "position": (x, y),
            "radius": radius,
            "type": "revival_shrine",
            "name": "Revival Shrine",
            "description": "A mystical shrine that can bring the defeated back to life."
        }

        if not hasattr(self, 'special_locations'):
            self.special_locations = []

        self.special_locations.append(shrine)

        # Add visual marker on the map
        self.map.add_terrain_feature(TerrainType.SHRINE, x, y, 1, 1)

        # Add as a named location
        self.add_location(Location(shrine["name"], shrine["description"], x, y, 1, 1))

        logger.info(f"Added revival shrine at ({x}, {y})")
        return shrine

    def check_revival_shrines(self):
        """Check if any defeated characters are near revival shrines and revive them"""
        if not hasattr(self, 'special_locations'):
            return

        # Find all revival shrines
        shrines = [loc for loc in self.special_locations if loc["type"] == "revival_shrine"]

        # Check for body items near shrines
        for shrine in shrines:
            x, y = shrine["position"]
            radius = shrine["radius"]

            # Check all positions within radius
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    check_x, check_y = x + dx, y + dy

                    # Skip out of bounds
                    if not (0 <= check_x < self.map.width and 0 <= check_y < self.map.height):
                        continue

                    # Check for body items
                    items = self.get_items_at(check_x, check_y)
                    for item in list(items):  # Use list to allow removal during iteration
                        item_str = item if isinstance(item, str) else item.name if hasattr(item, 'name') else str(item)

                        # Check if it's a body
                        if "'s body" in item_str:
                            # Extract character name
                            npc_name = item_str.split("'s body")[0]

                            # Find the corresponding NPC
                            npc_id = None
                            for id, npc in self.npc_manager.npcs.items():
                                if npc.name == npc_name:
                                    npc_id = id
                                    break

                            if npc_id:
                                # Attempt to revive
                                if self.npc_manager.revive_npc(npc_id, position=(check_x, check_y)):
                                    # Remove the body if revived
                                    self.remove_item_from_ground(item, check_x, check_y)

                                    # Add revival event
                                    self.memory_manager.add_event(f"{npc_name} has been revived at the {shrine['name']}!")
