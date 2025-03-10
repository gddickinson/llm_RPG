"""
Character Types module for LLM-RPG
Defines enums and types for character classes, races, etc.
"""

from enum import Enum, auto

class CharacterClass(Enum):
    """Enumeration of character classes"""
    WARRIOR = "warrior"
    WIZARD = "wizard"
    ROGUE = "rogue"
    CLERIC = "cleric"
    BARD = "bard"
    MERCHANT = "merchant"
    VILLAGER = "villager"
    GUARD = "guard"
    MONSTER = "monster"
    NOBLE = "noble"
    RANGER = "ranger"
    DRUID = "druid"
    PALADIN = "paladin"
    MONK = "monk"
    SORCERER = "sorcerer"
    WARLOCK = "warlock"
    BARBARIAN = "barbarian"
    ARTIFICER = "artificer"
    TROLL = "troll"  # New class
    BRIGAND = "brigand"  # New class

# Update the CharacterRace enum
class CharacterRace(Enum):
    """Enumeration of character races"""
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"
    ORC = "orc"
    GOBLIN = "goblin"
    GNOME = "gnome"
    TIEFLING = "tiefling"
    DRAGONBORN = "dragonborn"
    HALF_ELF = "half-elf"
    HALF_ORC = "half-orc"
    TROLL = "troll"  # New race


class Alignment(Enum):
    """D&D-style character alignment"""
    LAWFUL_GOOD = "lawful good"
    NEUTRAL_GOOD = "neutral good"
    CHAOTIC_GOOD = "chaotic good"
    LAWFUL_NEUTRAL = "lawful neutral"
    TRUE_NEUTRAL = "true neutral"
    CHAOTIC_NEUTRAL = "chaotic neutral"
    LAWFUL_EVIL = "lawful evil"
    NEUTRAL_EVIL = "neutral evil"
    CHAOTIC_EVIL = "chaotic evil"


class CharacterTrait(Enum):
    """Character personality traits"""
    BRAVE = "brave"
    CAUTIOUS = "cautious"
    CHEERFUL = "cheerful"
    RECKLESS = "reckless"
    LOYAL = "loyal"
    GREEDY = "greedy"
    HONEST = "honest"
    DECEITFUL = "deceitful"
    CURIOUS = "curious"
    SUSPICIOUS = "suspicious"
    PROUD = "proud"
    HUMBLE = "humble"
    AGGRESSIVE = "aggressive"
    PEACEFUL = "peaceful"
    LAZY = "lazy"
    HARDWORKING = "hardworking"
    GENEROUS = "generous"
    SELFISH = "selfish"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"


class CharacterStatus(Enum):
    """Status effects that can affect characters"""
    NORMAL = auto()
    POISONED = auto()
    PARALYZED = auto()
    STUNNED = auto()
    BLINDED = auto()
    CHARMED = auto()
    FRIGHTENED = auto()
    EXHAUSTED = auto()
    INVISIBLE = auto()
    BLESSED = auto()
    CURSED = auto()
