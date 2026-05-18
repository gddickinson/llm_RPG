"""Preset NPCs for the demo world.

Extracted from npc_manager.py to keep that file under 500 LOC. The
NPCManager calls these factories from `create_simple_npcs()`.
"""

import logging
from typing import List

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace

logger = logging.getLogger("llm_rpg.npc_presets")


def make_tavern_keeper() -> Character:
    npc = Character(
        id="tavernkeeper_01",
        name="Goren",
        character_class=CharacterClass.MERCHANT,
        race=CharacterRace.HUMAN,
        level=3,
        strength=12, dexterity=10, constitution=14,
        intelligence=12, wisdom=14, charisma=16,
        hp=20, max_hp=20,
        position=(13, 7),
        inventory=["ale", "mead", "bread"],
        gold=100,
        symbol="T",
        description="A jovial tavern keeper with a hearty laugh",
        personality={
            "traits": ["friendly", "gregarious", "opportunistic"],
            "likes": ["gold", "stories", "ale"],
            "dislikes": ["thieves", "troublemakers"],
        },
        goals=["Make a profit", "Keep customers happy",
               "Gather interesting stories"],
        relationships={},
    )
    npc.add_memory("Served a group of adventurers who talked about a dragon", 3)
    npc.add_memory("Heard rumors of bandits on the east road", 2)
    npc.add_memory("A troll has been causing trouble for travelers", 3)
    npc.home_location = "Oakvale Tavern"
    return npc


def make_blacksmith() -> Character:
    npc = Character(
        id="blacksmith_01",
        name="Durgan",
        character_class=CharacterClass.MERCHANT,
        race=CharacterRace.DWARF,
        level=5,
        strength=16, dexterity=14, constitution=16,
        intelligence=12, wisdom=12, charisma=10,
        hp=30, max_hp=30,
        position=(17, 7),
        inventory=["sword", "shield", "armor"],
        gold=200,
        symbol="B",
        description="A stout dwarf with muscular arms and a thick beard",
        personality={
            "traits": ["hardworking", "honest", "gruff"],
            "likes": ["craftsmanship", "ale", "honesty"],
            "dislikes": ["haggling", "shoddy work", "elves"],
        },
        goals=["Craft masterwork items", "Earn enough to expand the forge"],
        relationships={"tavernkeeper_01": 60},
    )
    npc.add_memory("A strange traveler commissioned an unusual silver blade", 3)
    npc.add_memory("The mines in the mountains have gone quiet", 2)
    npc.add_memory("I've been making stronger weapons since troll attacks", 2)
    npc.home_location = "Durgan's Forge"
    return npc


def make_minstrel() -> Character:
    npc = Character(
        id="minstrel_01",
        name="Melody",
        character_class=CharacterClass.BARD,
        race=CharacterRace.HUMAN,
        level=2,
        strength=8, dexterity=14, constitution=10,
        intelligence=12, wisdom=10, charisma=16,
        hp=15, max_hp=15,
        position=(15, 8),
        inventory=["lute", "flute", "wine"],
        gold=30,
        symbol="M",
        description="A cheerful young woman with a beautiful voice and colorful clothes",
        personality={
            "traits": ["cheerful", "curious", "flirtatious"],
            "likes": ["music", "stories", "attractive people"],
            "dislikes": ["silence", "boredom", "violence"],
        },
        goals=["Collect stories for songs", "Earn fame", "Find romance"],
        relationships={"tavernkeeper_01": 50, "blacksmith_01": 30},
    )
    npc.add_memory("Heard a haunting melody from the forest at night", 3)
    npc.add_memory("A noble from the capital travels incognito", 2)
    npc.add_memory("I'm composing a song about a fearsome troll", 2)
    npc.home_location = "Oakvale Tavern"
    return npc


def make_guard() -> Character:
    npc = Character(
        id="guard_01",
        name="Karim",
        character_class=CharacterClass.GUARD,
        race=CharacterRace.HUMAN,
        level=3,
        strength=14, dexterity=12, constitution=14,
        intelligence=10, wisdom=12, charisma=10,
        hp=25, max_hp=25,
        position=(10, 7),
        inventory=["sword", "shield", "jerky"],
        gold=15,
        symbol="G",
        description="A stern-looking guard with a weathered face",
        personality={
            "traits": ["dutiful", "suspicious", "brave"],
            "likes": ["order", "discipline", "recognition"],
            "dislikes": ["troublemakers", "monsters", "laziness"],
        },
        goals=["Protect the village", "Advance in rank",
               "Enforce the laws", "Hunt down the troll brigand"],
        relationships={"tavernkeeper_01": 40, "blacksmith_01": 60,
                       "minstrel_01": 20},
    )
    npc.add_memory("Spotted strange lights in the mountains three nights ago", 3)
    npc.add_memory("Merchants reported missing goods on the east road", 2)
    npc.add_memory("I've been ordered to organize a hunt for the troll", 3)
    npc.home_location = "Oakvale Village"
    return npc


def make_troll_brigand(position=(25, 10)) -> Character:
    troll = Character(
        id="troll_brigand_01",
        name="Gorkash",
        character_class=CharacterClass.BRIGAND,
        race=CharacterRace.TROLL,
        level=5,
        strength=18, dexterity=10, constitution=16,
        intelligence=8, wisdom=8, charisma=6,
        hp=40, max_hp=40,
        position=position,
        inventory=["crude axe", "tattered armor", "stolen jewelry"],
        gold=50,
        symbol="X",
        description="A massive troll with greenish skin and a menacing grin",
        personality={
            "traits": ["aggressive", "greedy", "territorial"],
            "likes": ["gold", "food", "fighting"],
            "dislikes": ["knights", "villagers", "being outnumbered"],
        },
        goals=["Rob travelers on the road", "Collect valuable items",
               "Establish dominance in the area"],
        relationships={
            "tavernkeeper_01": -60,
            "blacksmith_01": -70,
            "guard_01": -80,
        },
    )
    troll.add_memory("I ambushed a merchant caravan and got shiny things", 3)
    troll.add_memory("Villagers tried to drive me away with torches", 2)
    troll.add_memory("I've been watching the road for easy prey", 1)
    return troll


def make_hamlet_innkeeper() -> Character:
    npc = Character(
        id="hamlet_innkeeper_01",
        name="Esra",
        character_class=CharacterClass.MERCHANT,
        race=CharacterRace.HUMAN,
        level=2,
        strength=11, dexterity=12, constitution=13,
        intelligence=11, wisdom=13, charisma=14,
        hp=18, max_hp=18,
        position=(8, 28),
        inventory=["ale", "bread", "wine"],
        gold=60,
        symbol="I",
        description="The cheerful keeper of the Riverside Inn",
        personality={"traits": ["welcoming", "curious"],
                     "likes": ["travelers", "songs"],
                     "dislikes": ["bandits"]},
        goals=["Keep travelers fed", "Hear news from the road"],
    )
    npc.add_memory("A caravan from the east stopped here three nights ago", 2)
    npc.home_location = "Riverside Inn"
    return npc


def make_hamlet_priest() -> Character:
    npc = Character(
        id="hamlet_priest_01",
        name="Brother Anselm",
        character_class=CharacterClass.CLERIC,
        race=CharacterRace.HUMAN,
        level=3,
        strength=10, dexterity=10, constitution=12,
        intelligence=13, wisdom=15, charisma=13,
        hp=20, max_hp=20,
        position=(8, 30),
        inventory=["holy_symbol", "bandage"],
        gold=20,
        symbol="P",
        description="A gentle priest tending the small chapel",
        personality={"traits": ["devout", "patient"]},
        goals=["Tend the chapel", "Bless travelers", "Comfort the sick"],
    )
    npc.home_location = "Hamlet Chapel"
    return npc


def make_hamlet_wheelwright() -> Character:
    npc = Character(
        id="hamlet_wheelwright_01",
        name="Tova",
        character_class=CharacterClass.MERCHANT,
        race=CharacterRace.DWARF,
        level=2,
        strength=14, dexterity=12, constitution=14,
        intelligence=12, wisdom=11, charisma=10,
        hp=18, max_hp=18,
        position=(12, 28),
        inventory=["sword", "shield"],
        gold=80,
        symbol="H",
        description="A no-nonsense dwarven wheelwright",
        personality={"traits": ["practical", "stubborn"]},
        goals=["Make sturdy wheels", "Earn coin"],
    )
    npc.home_location = "Wheelwright's Shop"
    return npc


def all_presets() -> List[Character]:
    """Return all preset NPCs (peaceful first, then the troll)."""
    return [
        make_tavern_keeper(),
        make_blacksmith(),
        make_minstrel(),
        make_guard(),
        make_hamlet_innkeeper(),
        make_hamlet_priest(),
        make_hamlet_wheelwright(),
        make_troll_brigand(),
    ]
