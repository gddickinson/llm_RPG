"""World package for LLM-RPG.

Public API:
- World: top-level world state
- WorldMap, TerrainType: grid and terrain
- Location, LocationFactory: named regions
- Biome, BIOME_TERRAIN: biome enum and mapping
- WorldGenerator: procedural map gen
"""

from world.world import World
from world.world_map import WorldMap, TerrainType
from world.location import Location, LocationFactory
from world.biome import Biome, BIOME_TERRAIN, BIOME_DESCRIPTION
from world.world_generator import WorldGenerator
from world.calendar import (
    Date, Season, date_from_minutes, minutes_from_date,
    MONTH_NAMES, SEASON_TINT, apply_season_tint,
)

__all__ = [
    "World", "WorldMap", "TerrainType",
    "Location", "LocationFactory",
    "Biome", "BIOME_TERRAIN", "BIOME_DESCRIPTION",
    "WorldGenerator",
    "Date", "Season", "date_from_minutes", "minutes_from_date",
    "MONTH_NAMES", "SEASON_TINT", "apply_season_tint",
]
