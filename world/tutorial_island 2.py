"""Tutorial Island — the starter isle (P4.4c, OSRS's Tutorial Island).

A small hand-built zone using the dungeon grid: a grass isle ringed by
water, a fishing shore, a rock face, a cook's fire, and a dock with the
one-way boat to the mainland. Three instructors (and one long-suffering
training dummy) teach each core verb by making you do it once.
"""

import logging
from typing import List, Tuple

from world.dungeon import Dungeon
from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.tutorial_island")

ISLAND_NAME = "Tutorial Island"
WIDTH, HEIGHT = 26, 16
SPAWN = (6, 8)
BOAT_TILE = (23, 8)          # end of the dock — TAB here departs
ROCK_TILES = [(4, 3), (5, 3)]
DOCK_Y = 8


def generate_island() -> Dungeon:
    isle = Dungeon(name=ISLAND_NAME, width=WIDTH, height=HEIGHT,
                   description="A sheltered isle where adventurers "
                               "take their first steps.")
    # Water everywhere, then carve the island
    isle.terrain = [[TerrainType.WATER for _ in range(WIDTH)]
                    for _ in range(HEIGHT)]
    for y in range(2, HEIGHT - 2):
        for x in range(2, 20):
            isle.terrain[y][x] = TerrainType.GRASS
    # Forest corner (flavor + forage)
    for x, y in ((16, 3), (17, 3), (16, 4), (17, 4), (18, 4)):
        isle.terrain[y][x] = TerrainType.FOREST
    # Rock face for the mining lesson (visual; blocked tiles)
    for x, y in ROCK_TILES:
        isle.terrain[y][x] = TerrainType.MOUNTAIN
    # Dock: a road strip running east over the water to the boat
    for x in range(19, BOAT_TILE[0] + 1):
        isle.terrain[DOCK_Y][x] = TerrainType.ROAD
    isle.exit_pos = SPAWN
    isle.spawned = True   # never auto-populate with monsters
    return isle


def build_instructors() -> List:
    """The island's cast. Ids start with `tut_` (zone-rendered,
    excluded from ambient NPC AI, removed on departure)."""
    from characters.character import Character
    from characters.character_types import CharacterClass, CharacterRace

    def make(nid, name, klass, pos, desc, traits, goals):
        npc = Character(
            id=nid, name=name, character_class=klass,
            race=CharacterRace.HUMAN, level=3,
            strength=12, dexterity=12, constitution=12,
            intelligence=12, wisdom=14, charisma=14,
            hp=25, max_hp=25, position=pos,
            description=desc,
            personality={"traits": traits},
            goals=goals, inventory=[],
        )
        npc.home_location = ISLAND_NAME
        return npc

    willem = make(
        "tut_willem", "Old Willem", CharacterClass.MERCHANT, (18, 8),
        "A weathered fisherman who greets every new arrival at the dock.",
        ["patient", "warm", "talkative"],
        ["Teach newcomers to fish and cook",
         "See them safely to the mainland"])
    bors = make(
        "tut_bors", "Sergeant Bors", CharacterClass.GUARD, (8, 5),
        "A drill sergeant with a parade voice and a battered dummy.",
        ["gruff", "encouraging"],
        ["Teach newcomers which end of a sword to hold"])

    dummy = Character(
        id="tut_dummy", name="Training Dummy",
        character_class=CharacterClass.MONSTER,
        race=CharacterRace.GOBLIN, level=1,
        strength=1, dexterity=1, constitution=1,
        intelligence=1, wisdom=1, charisma=1,
        hp=5, max_hp=5, position=(9, 4),
        symbol="d",
        description="Straw, sackcloth, and a painted scowl.",
        personality={"traits": ["inanimate"]},
        goals=["Stand there"], inventory=[],
    )
    return [willem, bors, dummy]
