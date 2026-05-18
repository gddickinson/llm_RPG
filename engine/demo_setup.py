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


def create_default_player(spec=None) -> Character:
    """Build the starting player character.

    Parameters
    ----------
    spec : CharacterSpec | dict | None
        Optional spec from the character creator. If None, builds the
        legacy default warrior.
    """
    if spec is None:
        name = "Player"
        race = CharacterRace.HUMAN
        klass = CharacterClass.WARRIOR
        stats = {"strength": 14, "dexterity": 12, "constitution": 14,
                 "intelligence": 10, "wisdom": 10, "charisma": 12}
        starters = ["sword", "shield", "potion"]
        gold = 50
    else:
        # Spec may be a CharacterSpec dataclass or a dict
        name = getattr(spec, "name", None) or spec.get("name", "Player")
        race = getattr(spec, "race", None) or CharacterRace(spec.get("race", "human"))
        klass = getattr(spec, "character_class", None) or \
                CharacterClass(spec.get("class", "warrior"))
        stats = getattr(spec, "stats", None) or spec.get("stats", {})
        # Starting items by class
        try:
            from ui.character_creator import CLASS_STARTERS
            starter_ids, _ = CLASS_STARTERS.get(klass, (["sword"], "@"))
        except Exception:
            starter_ids = ["sword"]
        starters = starter_ids
        gold = 50

    # Build inventory from item ids
    inventory = []
    for item_id in starters:
        item = create_item(item_id, quantity=2 if item_id == "potion" else 1)
        if item:
            inventory.append(item)

    # HP from CON
    con = stats.get("constitution", 10)
    max_hp = 18 + 2 * max(0, (con - 10) // 2) + 5  # baseline 23-31

    player = Character(
        id="player",
        name=name,
        character_class=klass,
        race=race,
        level=1,
        strength=stats.get("strength", 10),
        dexterity=stats.get("dexterity", 10),
        constitution=con,
        intelligence=stats.get("intelligence", 10),
        wisdom=stats.get("wisdom", 10),
        charisma=stats.get("charisma", 10),
        hp=max_hp, max_hp=max_hp,
        position=(15, 5),
        inventory=inventory,
        gold=gold,
        symbol="@",
        description=f"A brave {race.value} {klass.value}",
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


def initialize_demo_world(engine, player_spec=None) -> None:
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
    engine.player = create_default_player(spec=player_spec)
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
