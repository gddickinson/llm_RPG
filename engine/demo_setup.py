"""Demo game world setup — player + initial quest offerings.

Extracted from GameEngine to keep that file under the 500-line budget.
"""

import logging
from typing import Any

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item, item_by_name

logger = logging.getLogger("llm_rpg.demo_setup")


def upgrade_item_string(item_or_str: Any) -> Any:
    """Convert a bare string inventory entry to a real Item where possible."""
    if not isinstance(item_or_str, str):
        return item_or_str
    item = create_item(item_or_str)
    if item:
        return item
    item = create_item(item_or_str.replace(" ", "_").lower())
    if item:
        return item
    item = item_by_name(item_or_str)
    return item if item else item_or_str


def create_default_player() -> Character:
    """Build the default starting player character."""
    player = Character(
        id="player",
        name="Player",
        character_class=CharacterClass.WARRIOR,
        race=CharacterRace.HUMAN,
        level=1,
        strength=14, dexterity=12, constitution=14,
        intelligence=10, wisdom=10, charisma=12,
        hp=25, max_hp=25,
        position=(15, 5),
        inventory=[
            create_item("sword"),
            create_item("shield"),
            create_item("potion", quantity=2),
        ],
        gold=50,
        symbol="@",
        description="A brave adventurer",
        personality={"traits": ["brave", "curious"]},
        goals=["Explore the world", "Find adventure"],
    )
    player.metadata = {
        "xp": 0,
        "faction_rep": {
            "villagers": 0, "guards": 0, "merchants": 0,
            "brigands": -10, "monsters": -10, "temple": 0,
        },
        "bank": 0,
    }
    return player


def initialize_demo_world(engine) -> None:
    """Populate `engine` with world terrain, NPCs, player, and starter quests."""
    # World generation
    try:
        from world.world_generator import WorldGenerator
        WorldGenerator(engine.world).generate()
    except Exception as e:
        logger.warning(f"Procedural worldgen failed ({e}); using legacy.")
        engine.world.create_simple_world()

    # Revival shrine + back-references
    try:
        engine.world.add_revival_shrine(2, 12, radius=2)
    except Exception:
        pass
    engine.world.npc_manager = engine.npc_manager
    engine.world.memory_manager = engine.memory_manager

    # NPCs
    npcs = engine.npc_manager.create_simple_npcs()
    for npc in npcs:
        npc.inventory = [upgrade_item_string(it) for it in npc.inventory]
        engine.world.map.place_character(npc, *npc.position)

    # Player
    engine.player = create_default_player()
    engine.world.map.place_character(engine.player, *engine.player.position)

    engine.memory_manager.add_event(
        "You arrive at the outskirts of Oakvale Village.")

    # Offer starter quests
    if engine.quest_manager:
        for qid in ("tavern_intro", "troll_hunt", "herb_gathering",
                    "cave_exploration", "deliver_sword", "survive_night"):
            engine.quest_manager.offer_quest(qid)

    # Build interiors for every building
    try:
        from world.interiors import build_interiors_for_world
        engine.interiors = build_interiors_for_world(engine.world)
    except Exception as e:
        logger.warning(f"Interior build failed: {e}")
