"""Subsystem construction (split from game_engine, P14.1).

`build_subsystems(engine)` wires every gameplay system onto the
engine in dependency order — moved verbatim from GameEngine.__init__
so the orchestrator stays under the 500-line rule. Adding a system?
Construct it here; tick it in engine/turn_pipeline.py; persist it in
engine/save_load.py.
"""

import logging

from engine.action_router import ActionRouter
from engine.combat_system import CombatSystem
from engine.dialog_system import DialogSystem
from engine.economy_system import EconomySystem
from engine.player_actions import PlayerActions

logger = logging.getLogger("llm_rpg.setup")


def build_subsystems(engine, llm_model=None,
                     enable_quests=True) -> None:
    self = engine   # body moved verbatim from __init__
    # Subsystems ---------------------------------------------------
    self.combat_system = CombatSystem(self)
    self.economy_system = EconomySystem(self)
    self.dialog_system = DialogSystem(self)
    self.action_router = ActionRouter(self)
    self.player_actions = PlayerActions(self)

    # Optional quest manager
    self.quest_manager = None
    if enable_quests:
        from quests.quest_manager import QuestManager
        self.quest_manager = QuestManager()
        self.quest_manager.engine = self   # bond gates (P15.5)

    # Encounter manager (wilderness monster spawns)
    from world.encounters import EncounterManager
    self.encounter_manager = EncounterManager(self)

    # Bank
    from engine.banking import Bank
    self.bank = Bank(self)

    # Shop manager (merchant catalogs)
    from engine.shop import ShopManager
    self.shop_manager = ShopManager(self)

    # Weather + foraging
    from world.weather import WeatherSystem
    from world.foraging import ForageManager
    from world.gathering import GatheringManager
    from engine.collection_log import CollectionLog
    from engine.pets import PetSystem
    from engine.diaries import DiaryManager
    from engine.travel import TravelSystem
    self.weather_system = WeatherSystem(self)
    self.forage_manager = ForageManager(self)
    self.gathering_manager = GatheringManager(self)
    self.collection_log = CollectionLog(self)
    self.pet_system = PetSystem(self)
    self.diary_manager = DiaryManager(self)
    self.travel_system = TravelSystem(self)
    from engine.persuasion import PersuasionSystem
    from engine.heart_events import HeartEventManager
    from engine.topics import TopicJournal
    from engine.director import WorldDirector
    self.persuasion = PersuasionSystem(self)
    self.heart_events = HeartEventManager(self)
    self.topic_journal = TopicJournal(self)
    self.memory_manager.on_event = self.topic_journal.scan
    self.world_director = WorldDirector(self)
    from quests.radiant import RadiantQuestGenerator
    from engine.guild import GuildSystem
    from engine.faction_ticker import FactionTicker
    from engine.dm_api import DMApi
    from engine.dm_autonomous import AutonomousDM
    self.radiant_quests = RadiantQuestGenerator(self)
    self.guild = GuildSystem(self)
    self.faction_ticker = FactionTicker(self)
    from engine.production_loop import ProductionSystem
    self.production = ProductionSystem(self)
    from world.resource_nodes import ResourceNodeSystem
    self.resource_nodes = ResourceNodeSystem(self)
    from engine.lairs import LairSystem
    self.lairs = LairSystem(self)
    from engine.monster_packs import MonsterPackSystem
    self.monster_packs = MonsterPackSystem(self)
    from engine.monster_tribes import MonsterTribeSystem
    self.monster_tribes = MonsterTribeSystem(self)
    from engine.nemesis import NemesisSystem
    self.nemesis = NemesisSystem(self)
    from engine.ambitions import AmbitionSystem
    self.ambitions = AmbitionSystem(self)
    from engine.social_graph import SocialGraph
    self.social_graph = SocialGraph(self)
    self.dm = DMApi(self)
    self.dm_autonomous = AutonomousDM(self)
    try:
        from engine.dm_library import load_into_registries
        load_into_registries()
    except Exception as e:
        logger.debug(f"Legendarium load skipped: {e}")

    # Ranged combat (projectiles)
    from engine.projectiles import ProjectileManager
    self.projectile_manager = ProjectileManager(self)

    # Combat visual effects (damage popups, hit flashes, particles)
    self.combat_effects = None
    try:
        from ui.combat_effects import CombatEffects
        self.combat_effects = CombatEffects(self)
    except Exception as e:
        logger.debug(f"Combat effects unavailable: {e}")

    # Dungeons (lazy — built when player enters a cave)
    self.dungeons = {}                # location_name -> Dungeon
    self.current_dungeon = None
    self.dungeon_return_pos = None

    # Chunked-world streamer (region transitions)
    self.world_streamer = None  # built lazily after world is initialized

    # Quest boards
    from quests.quest_board import QuestBoardManager
    self.quest_board_manager = QuestBoardManager(self)

    # Interiors (built after world generation in initialize_demo_game)
    self.interiors = {}
    self.current_interior = None
    self.exterior_return_pos = None

    # Companion / party
    from characters.companions import CompanionManager
    self.companion_manager = CompanionManager(self)

    # NPC-vs-NPC conflict (P7.1) + retaliation (P7.2)
    from engine.npc_conflict import NPCConflictSystem
    self.npc_conflict = NPCConflictSystem(self)
    from engine.retaliation import RetaliationSystem
    self.retaliation = RetaliationSystem(self)
    from engine.disease import DiseaseSystem
    self.disease = DiseaseSystem(self)
    from world.farming import FarmManager
    self.farm_manager = FarmManager(self)
    from engine.pantheon import PantheonSystem
    self.pantheon = PantheonSystem(self)
    from engine.market import MarketSystem
    self.market = MarketSystem(self)
    from engine.doors import DoorManager
    self.door_manager = DoorManager(self)
    from characters.homes import HomeSystem
    self.homes = HomeSystem(self)
    from engine.trespass import TrespassSystem
    self.trespass = TrespassSystem(self)
    from engine.targeting import TargetingSystem
    self.targeting = TargetingSystem(self)
    from world.structures import StructureBuilder
    self.structures = StructureBuilder(self)
    from engine.tile_damage import TileDamage
    self.tile_damage = TileDamage(self)
    from engine.surfaces import SurfaceLayer
    self.surfaces_layer = SurfaceLayer(self)
    from engine.flood import FloodSystem
    self.flood_system = FloodSystem(self)
    from engine.traversal import TraversalSystem
    self.traversal = TraversalSystem(self)
    from engine.law import LawSystem
    self.law = LawSystem(self)
    # M.1: the roster of controllable characters (self-seeds the active
    # player); the keystone for multiplayer + agent-driven heroes.
    from engine.player_roster import PlayerRoster
    self.roster = PlayerRoster(self)
