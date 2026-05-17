"""
NPC Manager module for LLM-RPG
Manages creation and tracking of NPC characters
"""

import logging
from typing import Dict, List, Optional, Any
import random
import uuid

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
import config

logger = logging.getLogger("llm_rpg.npc_manager")

class NPCManager:
    """Manages all NPC characters in the game"""

    def __init__(self):
        self.npcs = {}  # Key: NPC ID, Value: NPC Character
        logger.info("NPC Manager initialized")

    def add_npc(self, npc: Character) -> None:
        """Add an NPC to the manager"""
        # Auto-assign faction by class if not already set
        try:
            from characters.factions import faction_of_class
            if getattr(npc, "faction", "neutral") == "neutral":
                npc.faction = faction_of_class(npc.character_class.value).value
        except Exception:
            pass
        self.npcs[npc.id] = npc
        logger.info(f"Added NPC: {npc.name} (ID: {npc.id}, faction: {getattr(npc, 'faction', '?')})")

    def get_npc(self, npc_id: str) -> Optional[Character]:
        """Get an NPC by ID"""
        return self.npcs.get(npc_id)

    def get_npc_by_name(self, name: str) -> Optional[Character]:
        """Get an NPC by name (returns first match)"""
        for npc in self.npcs.values():
            if npc.name.lower() == name.lower():
                return npc
        return None

    def get_npcs_by_location(self, location_name: str) -> List[Character]:
        """Get all NPCs associated with a location"""
        return [npc for npc in self.npcs.values()
                if hasattr(npc, 'home_location') and npc.home_location == location_name]

    def get_npcs_by_class(self, character_class: CharacterClass) -> List[Character]:
        """Get all NPCs of a specific class"""
        return [npc for npc in self.npcs.values()
                if npc.character_class == character_class]

    def remove_npc(self, npc_id: str) -> bool:
        """Remove an NPC from the manager"""
        if npc_id in self.npcs:
            npc = self.npcs[npc_id]
            del self.npcs[npc_id]
            logger.info(f"Removed NPC: {npc.name} (ID: {npc_id})")
            return True
        logger.warning(f"Failed to remove NPC: ID {npc_id} not found")
        return False

    def create_random_npc(self, location=None, char_class=None, race=None) -> Character:
        """Create a random NPC with optional constraints"""
        # Generate a unique ID
        npc_id = f"npc_{uuid.uuid4().hex[:8]}"

        # Random name generation (simplified)
        human_names = ["Aldric", "Bran", "Cedric", "Dorn", "Eadric", "Fendrel", "Gavin",
                      "Hector", "Ivar", "Jorah", "Kade", "Leif", "Marek", "Nyles",
                      "Oswald", "Phelan", "Quincy", "Rowan", "Silas", "Tristan",
                      "Adela", "Brenna", "Cora", "Delia", "Eliza", "Faye", "Greta",
                      "Hilda", "Ida", "Jenna", "Kira", "Lyra", "Mira", "Nora",
                      "Ophelia", "Piper", "Quinn", "Rose", "Sylvia", "Thea"]

        dwarf_names = ["Balin", "Dwalin", "Thorin", "Dain", "Gimli", "Gloin", "Durin",
                      "Thrain", "Bombur", "Fili", "Kili", "Nori", "Ori", "Bifur",
                      "Bofur", "Dori", "Darva", "Helga", "Sigrid", "Thyra", "Britta"]

        elf_names = ["Legolas", "Elrond", "Thranduil", "Celeborn", "Haldir", "Aegnor",
                    "Finrod", "Orophin", "Galadriel", "Arwen", "Celebrian", "Tauriel",
                    "Luthien", "Nimrodel", "Elwing", "Maedhros", "Maglor", "Fingon"]

        # Select race if not provided
        if not race:
            race = random.choice(list(CharacterRace))

        # Select name based on race
        if race == CharacterRace.DWARF:
            name = random.choice(dwarf_names)
        elif race == CharacterRace.ELF:
            name = random.choice(elf_names)
        else:
            name = random.choice(human_names)

        # Select class if not provided
        if not char_class:
            common_classes = [CharacterClass.VILLAGER, CharacterClass.MERCHANT,
                             CharacterClass.GUARD, CharacterClass.WARRIOR]
            char_class = random.choice(common_classes)

        # Generate stats based on class
        base_stats = {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        }

        # Adjust stats based on class
        if char_class == CharacterClass.WARRIOR:
            base_stats["strength"] += 4
            base_stats["constitution"] += 2
        elif char_class == CharacterClass.WIZARD:
            base_stats["intelligence"] += 4
            base_stats["wisdom"] += 2
        elif char_class == CharacterClass.ROGUE:
            base_stats["dexterity"] += 4
            base_stats["charisma"] += 2
        elif char_class == CharacterClass.CLERIC:
            base_stats["wisdom"] += 4
            base_stats["charisma"] += 2
        elif char_class == CharacterClass.MERCHANT:
            base_stats["charisma"] += 4
            base_stats["intelligence"] += 2

        # Adjust stats based on race
        if race == CharacterRace.DWARF:
            base_stats["constitution"] += 2
            base_stats["wisdom"] += 1
        elif race == CharacterRace.ELF:
            base_stats["dexterity"] += 2
            base_stats["intelligence"] += 1
        elif race == CharacterRace.HALFLING:
            base_stats["dexterity"] += 2
            base_stats["charisma"] += 1

        # Add some randomness
        for stat in base_stats:
            base_stats[stat] += random.randint(-1, 2)

        # Set symbol based on class
        symbol_map = {
            CharacterClass.WARRIOR: "W",
            CharacterClass.WIZARD: "M",
            CharacterClass.ROGUE: "R",
            CharacterClass.CLERIC: "C",
            CharacterClass.BARD: "B",
            CharacterClass.MERCHANT: "T",
            CharacterClass.VILLAGER: "V",
            CharacterClass.GUARD: "G",
            CharacterClass.MONSTER: "X"
        }
        symbol = symbol_map.get(char_class, "N")

        # Create the NPC
        level = random.randint(1, 3)
        max_hp = base_stats["constitution"] + (level * 4)

        # Generate personality traits
        personality_traits = ["friendly", "curious", "cautious", "brave", "grumpy",
                             "cheerful", "suspicious", "honest", "clever", "stubborn"]
        likes = ["gold", "food", "music", "stories", "weapons", "animals", "art"]
        dislikes = ["thieves", "loud noises", "rudeness", "danger", "dirt", "monsters"]

        # Select random traits
        selected_traits = random.sample(personality_traits, 3)
        selected_likes = random.sample(likes, 2)
        selected_dislikes = random.sample(dislikes, 2)

        personality = {
            "traits": selected_traits,
            "likes": selected_likes,
            "dislikes": selected_dislikes
        }

        # Generate goals
        goal_templates = [
            "Make a living selling goods",
            "Protect the village from threats",
            "Find a rare ingredient for a special recipe",
            "Pay off debt to the local guild",
            "Discover information about family history",
            "Learn a new craft or skill",
            "Find romance or companionship",
            "Earn enough gold to retire comfortably",
            "Avenge a past wrong",
            "Escape a troubled past"
        ]

        # Select 1-3 goals
        goals = random.sample(goal_templates, random.randint(1, 3))

        # Create inventory based on class
        inventory = []

        if char_class == CharacterClass.MERCHANT:
            inventory.extend(["goods", "ledger", "coins"])
        elif char_class == CharacterClass.WARRIOR:
            inventory.extend(["sword", "shield"])
        elif char_class == CharacterClass.WIZARD:
            inventory.extend(["spellbook", "potion"])
        elif char_class == CharacterClass.ROGUE:
            inventory.extend(["dagger", "lockpicks"])
        elif char_class == CharacterClass.CLERIC:
            inventory.extend(["holy symbol", "healing potion"])
        elif char_class == CharacterClass.GUARD:
            inventory.extend(["sword", "whistle"])
        else:
            inventory.append("personal items")

        # Add some money
        gold = random.randint(5, 20) * level

        # Create basic description
        descriptions = {
            CharacterClass.MERCHANT: f"A {random.choice(['shrewd', 'friendly', 'busy', 'well-dressed'])} merchant",
            CharacterClass.WARRIOR: f"A {random.choice(['battle-worn', 'muscular', 'scarred', 'confident'])} warrior",
            CharacterClass.WIZARD: f"A {random.choice(['mysterious', 'elderly', 'eccentric', 'scholarly'])} wizard",
            CharacterClass.ROGUE: f"A {random.choice(['nimble', 'shadowy', 'quick-eyed', 'charming'])} rogue",
            CharacterClass.CLERIC: f"A {random.choice(['devout', 'serene', 'helpful', 'wise'])} cleric",
            CharacterClass.GUARD: f"A {random.choice(['vigilant', 'stern', 'dutiful', 'alert'])} guard",
            CharacterClass.VILLAGER: f"A {random.choice(['simple', 'hardworking', 'friendly', 'modest'])} villager"
        }

        description = descriptions.get(
            char_class,
            f"A {race.value} {char_class.value}"
        )

        # Create the NPC
        npc = Character(
            id=npc_id,
            name=name,
            character_class=char_class,
            race=race,
            level=level,
            strength=base_stats["strength"],
            dexterity=base_stats["dexterity"],
            constitution=base_stats["constitution"],
            intelligence=base_stats["intelligence"],
            wisdom=base_stats["wisdom"],
            charisma=base_stats["charisma"],
            hp=max_hp,
            max_hp=max_hp,
            inventory=inventory,
            gold=gold,
            symbol=symbol,
            description=description,
            personality=personality,
            goals=goals
        )

        # Add home location if provided
        if location:
            npc.home_location = location

        # Add initial memories
        npc.add_memory(f"I was born in a {random.choice(['small village', 'bustling town', 'quiet hamlet', 'busy city'])}", 2)
        npc.add_memory(f"I became a {char_class.value} because {random.choice(['I wanted to', 'my family tradition', 'I had a talent for it', 'it was my only option'])}", 2)

        # Add the NPC to our manager
        self.add_npc(npc)

        return npc

    def create_simple_npcs(self):
        """Create NPCs for the demo world (delegated to npc_presets)."""
        from characters.npc_presets import all_presets
        npcs = all_presets()
        for npc in npcs:
            self.add_npc(npc)
        logger.info(f"Created {len(npcs)} NPCs for the demo world")
        return npcs

    def create_troll_brigand(self, position=(25, 10)):
        from characters.npc_presets import make_troll_brigand
        troll = make_troll_brigand(position=position)
        self.add_npc(troll)
        return troll

    def revive_npc(self, npc_id, position=None, hp_percent=0.5):
        """Revive a defeated NPC and place them back on the map"""
        npc = self.get_npc(npc_id)
        if not npc:
            logger.warning(f"Cannot revive NPC {npc_id}: NPC not found")
            return False

        # Check if NPC can be revived
        if not hasattr(npc, 'revive') or not npc.revive(hp_percent):
            logger.warning(f"Cannot revive NPC {npc_id}: NPC is permanently dead")
            return False

        # Determine position to place the revived NPC
        if position is None:
            # Use last position if available
            if hasattr(npc, 'last_position'):
                position = npc.last_position
            else:
                # Use home location if available
                if hasattr(npc, 'home_location'):
                    for location in self.world.locations:
                        if location.name == npc.home_location:
                            position = location.center()
                            break

                # If still no position, use a default
                if position is None:
                    position = (10, 10)  # Default position

        # Place the NPC back on the map
        self.world.map.place_character(npc, position[0], position[1])

        logger.info(f"Revived NPC {npc.name} at position {position}")
        return True
