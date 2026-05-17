"""Biome definitions used by procedural world generation."""

from enum import Enum
from world.world_map import TerrainType


class Biome(Enum):
    PLAINS = "plains"
    FOREST = "forest"
    DEEP_FOREST = "deep_forest"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    SWAMP = "swamp"
    DESERT = "desert"
    RIVER = "river"
    VILLAGE = "village"
    ROAD = "road"


# Biome -> dominant terrain
BIOME_TERRAIN = {
    Biome.PLAINS: TerrainType.GRASS,
    Biome.FOREST: TerrainType.FOREST,
    Biome.DEEP_FOREST: TerrainType.FOREST,
    Biome.HILLS: TerrainType.GRASS,
    Biome.MOUNTAINS: TerrainType.MOUNTAIN,
    Biome.SWAMP: TerrainType.WATER,
    Biome.DESERT: TerrainType.GRASS,
    Biome.RIVER: TerrainType.WATER,
    Biome.VILLAGE: TerrainType.BUILDING,
    Biome.ROAD: TerrainType.ROAD,
}


# Biome description shown to the player
BIOME_DESCRIPTION = {
    Biome.PLAINS: "Rolling grasslands stretch in all directions.",
    Biome.FOREST: "Tall trees rustle in the wind.",
    Biome.DEEP_FOREST: "Dense, ancient woods. The canopy blocks the sun.",
    Biome.HILLS: "Rolling hills dotted with stones.",
    Biome.MOUNTAINS: "Steep, rocky peaks loom overhead.",
    Biome.SWAMP: "Stagnant water and tangled roots.",
    Biome.DESERT: "Dry, cracked earth and rare scrub.",
    Biome.RIVER: "A flowing stream winds across the land.",
    Biome.VILLAGE: "The bustle of a settlement.",
    Biome.ROAD: "A well-worn trail.",
}
