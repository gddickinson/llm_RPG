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
        self.npcs[npc.id] = npc
        logger.info(f"Added NPC: {npc.name} (ID: {npc.id})")

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

    def _create_original_npcs(self):
        """Create the original set of NPCs from the previous implementation"""
        # Tavern keeper
        tavern_keeper = Character(
            id="tavernkeeper_01",
            name="Goren",
            character_class=CharacterClass.MERCHANT,
            race=CharacterRace.HUMAN,
            level=3,
            strength=12,
            dexterity=10,
            constitution=14,
            intelligence=12,
            wisdom=14,
            charisma=16,
            hp=20,
            max_hp=20,
            position=(13, 7),
            inventory=["ale", "mead", "bread"],
            gold=100,
            symbol="T",
            description="A jovial tavern keeper with a hearty laugh",
            personality={
                "traits": ["friendly", "gregarious", "opportunistic"],
                "likes": ["gold", "stories", "ale"],
                "dislikes": ["thieves", "troublemakers"]
            },
            goals=["Make a profit", "Keep customers happy", "Gather interesting stories"],
            relationships={}
        )
        tavern_keeper.add_memory("Served a group of adventurers who talked about a dragon in the mountains", 3)
        tavern_keeper.add_memory("Heard rumors of bandits on the east road", 2)
        tavern_keeper.add_memory("There's a troll that has been causing trouble for travelers", 3)
        tavern_keeper.home_location = "Oakvale Tavern"
        self.add_npc(tavern_keeper)

        # Blacksmith
        blacksmith = Character(
            id="blacksmith_01",
            name="Durgan",
            character_class=CharacterClass.MERCHANT,
            race=CharacterRace.DWARF,
            level=5,
            strength=16,
            dexterity=14,
            constitution=16,
            intelligence=12,
            wisdom=12,
            charisma=10,
            hp=30,
            max_hp=30,
            position=(17, 7),
            inventory=["sword", "shield", "armor"],
            gold=200,
            symbol="B",
            description="A stout dwarf with muscular arms and a thick beard",
            personality={
                "traits": ["hardworking", "honest", "gruff"],
                "likes": ["craftsmanship", "ale", "honesty"],
                "dislikes": ["haggling", "shoddy work", "elves"]
            },
            goals=["Craft masterwork items", "Earn enough to expand the forge"],
            relationships={"tavernkeeper_01": 60}
        )
        blacksmith.add_memory("A strange traveler commissioned an unusual silver blade", 3)
        blacksmith.add_memory("The mines in the mountains have gone quiet", 2)
        blacksmith.add_memory("I've been making stronger weapons since the troll attacks started", 2)
        blacksmith.home_location = "Durgan's Forge"
        self.add_npc(blacksmith)

        # Wandering minstrel
        minstrel = Character(
            id="minstrel_01",
            name="Melody",
            character_class=CharacterClass.BARD,
            race=CharacterRace.HUMAN,
            level=2,
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=12,
            wisdom=10,
            charisma=16,
            hp=15,
            max_hp=15,
            position=(15, 8),
            inventory=["lute", "flute", "wine"],
            gold=30,
            symbol="M",
            description="A cheerful young woman with a beautiful voice and colorful clothes",
            personality={
                "traits": ["cheerful", "curious", "flirtatious"],
                "likes": ["music", "stories", "attractive people"],
                "dislikes": ["silence", "boredom", "violence"]
            },
            goals=["Collect stories for songs", "Earn fame", "Find romance"],
            relationships={"tavernkeeper_01": 50, "blacksmith_01": 30}
        )
        minstrel.add_memory("Heard a haunting melody from the forest at night", 3)
        minstrel.add_memory("A noble from the capital is supposedly traveling incognito", 2)
        minstrel.add_memory("I'm composing a song about a fearsome troll terrorizing the countryside", 2)
        minstrel.home_location = "Oakvale Tavern"
        self.add_npc(minstrel)

        # Guard
        guard = Character(
            id="guard_01",
            name="Karim",
            character_class=CharacterClass.GUARD,
            race=CharacterRace.HUMAN,
            level=3,
            strength=14,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10,
            hp=25,
            max_hp=25,
            position=(10, 7),
            inventory=["sword", "shield", "jerky"],
            gold=15,
            symbol="G",
            description="A stern-looking guard with a weathered face",
            personality={
                "traits": ["dutiful", "suspicious", "brave"],
                "likes": ["order", "discipline", "recognition"],
                "dislikes": ["troublemakers", "monsters", "laziness"]
            },
            goals=["Protect the village", "Advance in rank", "Enforce the laws", "Hunt down the troll brigand"],
            relationships={"tavernkeeper_01": 40, "blacksmith_01": 60, "minstrel_01": 20}
        )
        guard.add_memory("Spotted strange lights in the mountains three nights ago", 3)
        guard.add_memory("Merchants reported missing goods on the east road", 2)
        guard.add_memory("I've been ordered to organize a hunt for the troll that's been attacking travelers", 3)
        guard.home_location = "Oakvale Village"
        self.add_npc(guard)

        return [tavern_keeper, blacksmith, minstrel, guard]



    def create_simple_npcs(self):
        """Create NPCs for the demo world"""
        # Create the original NPCs first
        npcs = self._create_original_npcs()

        # Add the troll brigand
        troll = self.create_troll_brigand()
        npcs.append(troll)

        logger.info(f"Created {len(npcs)} NPCs for the demo world")
        return npcs

    def create_troll_brigand(self, position=(25, 10)):
        """Create a troll brigand NPC"""
        troll = Character(
            id="troll_brigand_01",
            name="Gorkash",
            character_class=CharacterClass.BRIGAND,
            race=CharacterRace.TROLL,
            level=5,
            strength=18,
            dexterity=10,
            constitution=16,
            intelligence=8,
            wisdom=8,
            charisma=6,
            hp=40,
            max_hp=40,
            position=position,
            inventory=["crude axe", "tattered armor", "stolen jewelry"],
            gold=50,
            symbol="X",
            description="A massive troll with greenish skin and a menacing grin, wielding a crude axe",
            personality={
                "traits": ["aggressive", "greedy", "territorial"],
                "likes": ["gold", "food", "fighting"],
                "dislikes": ["knights", "villagers", "being outnumbered"]
            },
            goals=["Rob travelers on the road", "Collect valuable items", "Establish dominance in the area"],
            relationships={}
        )

        # Add some memories
        troll.add_memory("I ambushed a merchant caravan last week and got some shiny things", 3)
        troll.add_memory("Villagers tried to drive me away with torches and pitchforks", 2)
        troll.add_memory("I've been watching the road for easy prey", 1)

        # Set negative relationships with villagers
        troll.relationships["tavernkeeper_01"] = -60
        troll.relationships["blacksmith_01"] = -70
        troll.relationships["guard_01"] = -80

        # Add to NPC manager
        self.add_npc(troll)

        logger.info(f"Created troll brigand: {troll.name}")
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
