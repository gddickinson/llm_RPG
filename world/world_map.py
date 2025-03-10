"""
World Map module for LLM-RPG
Handles the map representation, terrain, and movement
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum

logger = logging.getLogger("llm_rpg.world_map")

class TerrainType(Enum):
    """Enum for different terrain types"""
    GRASS = "grass"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    WATER = "water"
    ROAD = "road"
    BUILDING = "building"
    CAVE = "cave"


class WorldMap:
    """Represents the game world map with terrain and objects"""

    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.terrain = [[TerrainType.GRASS for _ in range(width)] for _ in range(height)]
        self.objects = {}  # Key: (x, y), Value: Object at that location
        self.characters = {}  # Key: (x, y), Value: Character at that location
        logger.info(f"Map initialized with size {width}x{height}")

    def add_terrain_feature(self, terrain_type: TerrainType, start_x: int, start_y: int, width: int, height: int):
        """Add a terrain feature of specified type and dimensions"""
        for y in range(start_y, min(start_y + height, self.height)):
            for x in range(start_x, min(start_x + width, self.width)):
                self.terrain[y][x] = terrain_type

        logger.debug(f"Added terrain feature: {terrain_type.value} at ({start_x},{start_y}) size {width}x{height}")

    def add_object(self, obj: Any, x: int, y: int):
        """Add an object to the map at specified coordinates"""
        self.objects[(x, y)] = obj
        logger.debug(f"Added object at ({x},{y}): {obj}")

    def place_character(self, character: Any, x: int, y: int):
        """Place a character on the map"""
        # Remove character from previous position if any
        for pos, char in list(self.characters.items()):
            if char.id == character.id:
                del self.characters[pos]

        # Add character to new position
        self.characters[(x, y)] = character
        character.position = (x, y)
        logger.debug(f"Placed character {character.name} at ({x},{y})")

    def move_character(self, character, new_x, new_y):
        """Move a character to a new position if possible"""
        # Check if position is valid
        if not (0 <= new_x < self.width and 0 <= new_y < self.height):
            logger.debug(f"Move failed for {character.name}: Position ({new_x},{new_y}) is out of bounds")
            return False

        # Check if terrain is traversable
        if self.terrain[new_y][new_x] == TerrainType.WATER or self.terrain[new_y][new_x] == TerrainType.MOUNTAIN:
            logger.debug(f"Move failed for {character.name}: Terrain {self.terrain[new_y][new_x].value} is not traversable")
            return False

        # Check if position is occupied by another character
        if (new_x, new_y) in self.characters:
            occupant = self.characters[(new_x, new_y)]
            logger.debug(f"Move failed for {character.name}: Position ({new_x},{new_y}) is occupied by {occupant.name}")
            return False

        # Current position of the character
        old_pos = None
        for pos, char in self.characters.items():
            if char.id == character.id:
                old_pos = pos
                break

        # Move character
        if old_pos:
            logger.debug(f"Moving {character.name} from {old_pos} to ({new_x},{new_y})")
            del self.characters[old_pos]
        else:
            logger.debug(f"Adding {character.name} to map at ({new_x},{new_y})")

        # Update character position
        self.characters[(new_x, new_y)] = character
        character.position = (new_x, new_y)
        logger.debug(f"Character {character.name} is now at position {character.position}")

        return True

    def get_visible_area(self, x: int, y: int, visibility_range=5) -> List[Dict]:
        """Return a description of the area visible from position (x,y)"""
        visible_area = []

        for j in range(max(0, y - visibility_range), min(self.height, y + visibility_range + 1)):
            for i in range(max(0, x - visibility_range), min(self.width, x + visibility_range + 1)):
                # Skip center position (where the viewer is)
                if i == x and j == y:
                    continue

                distance = ((i - x) ** 2 + (j - y) ** 2) ** 0.5
                if distance <= visibility_range:
                    # Add terrain
                    terrain_type = self.terrain[j][i].value

                    # Add objects
                    obj = None
                    if (i, j) in self.objects:
                        obj = self.objects[(i, j)]

                    # Add characters
                    char = None
                    if (i, j) in self.characters:
                        char = self.characters[(i, j)]

                    visible_area.append({
                        "position": (i, j),
                        "direction": self._get_direction(x, y, i, j),
                        "distance": int(distance),
                        "terrain": terrain_type,
                        "object": obj.name if obj and hasattr(obj, "name") else str(obj) if obj else None,
                        "character": char.name if char else None
                    })

        return visible_area

    def get_visible_description(self, x: int, y: int, visibility_range=5) -> str:
        """Get a text description of the visible area"""
        visible_area = self.get_visible_area(x, y, visibility_range)
        description = []

        # Group by direction
        by_direction = {}
        for item in visible_area:
            direction = item["direction"]
            if direction not in by_direction:
                by_direction[direction] = []
            by_direction[direction].append(item)

        # Create descriptions for each direction
        for direction, items in by_direction.items():
            dir_desc = f"To the {direction}:"

            # Characters (most important)
            characters = [item for item in items if item["character"]]
            if characters:
                for char_item in characters:
                    dir_desc += f" {char_item['character']} ({char_item['distance']} tiles away on {char_item['terrain']}),"

            # Objects
            objects = [item for item in items if item["object"] and not item["character"]]
            if objects:
                for obj_item in objects:
                    dir_desc += f" {obj_item['object']} ({obj_item['distance']} tiles away),"

            # Terrain (summarize)
            terrain_counts = {}
            for item in items:
                if not item["character"] and not item["object"]:
                    terrain = item["terrain"]
                    terrain_counts[terrain] = terrain_counts.get(terrain, 0) + 1

            if terrain_counts:
                terrains = []
                for terrain, count in terrain_counts.items():
                    if count > 3:
                        terrains.append(f"mostly {terrain}")
                    else:
                        terrains.append(f"some {terrain}")

                dir_desc += " " + ", ".join(terrains)

            description.append(dir_desc)

        return "\n".join(description)

    def _get_direction(self, from_x: int, from_y: int, to_x: int, to_y: int) -> str:
        """Convert a target position to a cardinal direction"""
        dx = to_x - from_x
        dy = to_y - from_y

        # Handle cardinal directions
        if abs(dx) > abs(dy) * 2:
            return "east" if dx > 0 else "west"
        elif abs(dy) > abs(dx) * 2:
            return "south" if dy > 0 else "north"

        # Handle diagonal directions
        if dx > 0 and dy > 0:
            return "southeast"
        elif dx > 0 and dy < 0:
            return "northeast"
        elif dx < 0 and dy > 0:
            return "southwest"
        elif dx < 0 and dy < 0:
            return "northwest"

        # Default to cardinal directions
        if abs(dx) >= abs(dy):
            return "east" if dx > 0 else "west"
        else:
            return "south" if dy > 0 else "north"

    def get_character_at(self, x: int, y: int) -> Optional[Any]:
        """Get character at the specified position"""
        return self.characters.get((x, y))

    def get_object_at(self, x: int, y: int) -> Optional[Any]:
        """Get object at the specified position"""
        return self.objects.get((x, y))

    def get_terrain_at(self, x: int, y: int) -> TerrainType:
        """Get terrain at the specified position"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.terrain[y][x]
        return TerrainType.GRASS  # Default if out of bounds

    def to_string(self, highlight_pos=None, visibility_range=None) -> str:
        """Generate a string representation of the map"""
        result = ""

        # Create map with terrain and objects
        map_repr = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                # Check if position has a character
                if (x, y) in self.characters:
                    char = self.characters[(x, y)]
                    row.append(char.symbol)
                # Check if position has an object
                elif (x, y) in self.objects:
                    obj = self.objects[(x, y)]
                    row.append(obj.symbol if hasattr(obj, "symbol") else "O")
                # Otherwise show terrain
                else:
                    terrain = self.terrain[y][x]
                    if terrain == TerrainType.GRASS:
                        row.append(".")
                    elif terrain == TerrainType.FOREST:
                        row.append("T")
                    elif terrain == TerrainType.MOUNTAIN:
                        row.append("^")
                    elif terrain == TerrainType.WATER:
                        row.append("~")
                    elif terrain == TerrainType.ROAD:
                        row.append("=")
                    elif terrain == TerrainType.BUILDING:
                        row.append("#")
                    elif terrain == TerrainType.CAVE:
                        row.append("C")

            map_repr.append(row)

        # Handle visibility if specified
        if highlight_pos and visibility_range:
            px, py = highlight_pos

            # Create a new map with only visible areas
            visible_map = [["?" for _ in range(self.width)] for _ in range(self.height)]

            # Mark the visible area
            for j in range(max(0, py - visibility_range), min(self.height, py + visibility_range + 1)):
                for i in range(max(0, px - visibility_range), min(self.width, px + visibility_range + 1)):
                    distance = ((i - px) ** 2 + (j - py) ** 2) ** 0.5
                    if distance <= visibility_range:
                        visible_map[j][i] = map_repr[j][i]

            # Mark the player position
            visible_map[py][px] = "@"

            map_repr = visible_map

        # Convert to string
        for row in map_repr:
            result += "".join(row) + "\n"

        return result

    def remove_character(self, character):
        """Remove a character from the map without updating its position"""
        for pos, char in list(self.characters.items()):
            if char.id == character.id:
                del self.characters[pos]
                logger.debug(f"Removed character {character.name} from map at {pos}")
                return True

        return False
