"""Core game engine — thin orchestrator over modular subsystems.

The legacy 1566-line engine was split into:
- combat_system.py
- economy_system.py
- dialog_system.py
- action_router.py
- player_actions.py
- save_load.py
- skills.py
- memory_manager.py

This file binds them together and exposes the high-level API used by UIs.
"""

import logging
from typing import Any, Dict, List, Optional

import config
from world.world import World
from characters.npc_manager import NPCManager
from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item
from llm.llm_interface import LLMInterface
from engine.memory_manager import MemoryManager
from engine.combat_system import CombatSystem
from engine.economy_system import EconomySystem
from engine.dialog_system import DialogSystem
from engine.action_router import ActionRouter
from engine.player_actions import PlayerActions
from engine.game_api_mixin import GameAPIMixin

logger = logging.getLogger("llm_rpg.engine")


class GameEngine(GameAPIMixin):
    """High-level game engine. UIs interact through this object."""

    def __init__(self, llm_model: str = None, llm_provider: str = None,
                 enable_npc_processes: bool = True,
                 enable_quests: bool = True,
                 player_spec=None,
                 start_tutorial: bool = False,
                 enable_dm_bridge: bool = False):
        # Core systems --------------------------------------------------
        self.world = World()
        self.npc_manager = NPCManager()
        self.memory_manager = MemoryManager()
        self.llm_interface = LLMInterface(
            model_name=llm_model or config.DEFAULT_MODEL,
            provider=llm_provider or getattr(config, "DEFAULT_PROVIDER", "heuristic"),
        )

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

        # State --------------------------------------------------------
        self.player: Optional[Character] = None
        self.running = False
        self.turn_counter = 0
        self.processing_npcs = set()
        self.player_dead = False  # set by combat_system when player defeated

        # Initialize demo world
        from engine.tutorial import TutorialManager
        self.tutorial_manager = TutorialManager(self)
        self.initialize_demo_game(player_spec=player_spec)
        # Baseline for the nightly-reflection day-change detector
        self._last_reflection_day = self.world.time // (24 * 60)
        from engine.rest import snapshot
        self._day_metrics = snapshot(self)
        self.dm_bridge = None
        if enable_dm_bridge:
            try:
                from engine.dm_bridge import DMBridge
                self.dm_bridge = DMBridge(self)
                logger.info("DM bridge active at saves/dm/")
            except Exception as e:
                logger.warning(f"DM bridge unavailable: {e}")
        if start_tutorial:
            self.tutorial_manager.start()

        # NPC processes (optional) -------------------------------------
        self.process_manager = None
        if enable_npc_processes:
            try:
                from engine.npc_process_manager import NPCProcessManager
                npc_list = list(self.npc_manager.npcs.values())
                self.process_manager = NPCProcessManager(
                    npc_list, llm_model=llm_model or config.DEFAULT_MODEL)
                self.process_manager.start_processes()
                logger.info("NPC process manager started")
            except Exception as e:
                logger.warning(f"NPC process manager unavailable: {e}")

        logger.info(f"Game engine initialized "
                    f"(provider={self.llm_interface.provider.name})")

    # ====================================================================
    # World / state setup
    # ====================================================================

    def initialize_demo_game(self, player_spec=None) -> None:
        """Set up a starter world + NPCs + player + initial quests."""
        from engine.demo_setup import initialize_demo_world
        initialize_demo_world(self, player_spec=player_spec)
        # World streamer (needs the world built first)
        try:
            from world.chunked_world import WorldStreamer
            self.world_streamer = WorldStreamer(self)
        except Exception as e:
            logger.debug(f"World streamer unavailable: {e}")
        logger.info("Demo game initialized")

    # ====================================================================
    # Loop / turn
    # ====================================================================

    def start_game(self) -> None:
        self.running = True
        self.turn_counter = 0
        self.player_dead = False
        self.memory_manager.add_event("The adventure begins.")

    def end_game(self) -> None:
        self.running = False
        self.memory_manager.add_event("The adventure has ended.")
        if self.process_manager:
            self.process_manager.stop_processes()
        if hasattr(self.llm_interface, "shutdown"):
            self.llm_interface.shutdown()

    def advance_turn(self) -> None:
        self.turn_counter += 1
        self.world.advance_time(1)
        if self.quest_manager:
            self.quest_manager.on_turn_advanced()

        # Tick NPC needs (game minutes pass)
        try:
            from characters.needs import tick_needs
            for npc in self.npc_manager.npcs.values():
                if npc.is_active():
                    tick_needs(npc, elapsed_minutes=1)
        except Exception as e:
            logger.debug(f"Needs tick error: {e}")

        # Tick player hunger; starving drains HP (floored at 1 — hunger
        # weakens, it doesn't kill)
        try:
            from characters.needs import (tick_player_needs, get_hunger,
                                          HUNGER_STARVING, HUNGER_HUNGRY)
            before = get_hunger(self.player)
            tick_player_needs(self.player, elapsed_minutes=1)
            hunger = get_hunger(self.player)
            if hunger >= HUNGER_STARVING and self.world.time % 30 == 0:
                if self.player.hp > 1:
                    self.player.hp -= 1
                self.memory_manager.add_event(
                    "You are starving! Find something to eat.")
            elif before < HUNGER_HUNGRY <= hunger:
                self.memory_manager.add_event(
                    "Your stomach growls. You should eat soon.")
        except Exception as e:
            logger.debug(f"Player needs tick error: {e}")

        # Tick status effects on all active characters (player + NPCs)
        try:
            from characters.status_effects import tick_effects
            for char in [self.player] + list(self.npc_manager.npcs.values()):
                if char and char.is_active():
                    events = tick_effects(char, self)
                    for ev in events:
                        self.memory_manager.add_event(ev)
        except Exception as e:
            logger.debug(f"Status effects tick error: {e}")

        # Slow mana regen for the player (1/turn while not in combat — simplified)
        try:
            from engine.spells import rest_recover_mana, ensure_mana
            ensure_mana(self.player)
            if self.turn_counter % 5 == 0:
                rest_recover_mana(self.player, amount=1)
        except Exception as e:
            logger.debug(f"Mana regen error: {e}")

        # Random wilderness encounter
        try:
            msg = self.encounter_manager.maybe_spawn()
            if msg:
                self.memory_manager.add_event(msg)
        except Exception as e:
            logger.debug(f"Encounter spawn error: {e}")

        # Weather changes
        try:
            wmsg = self.weather_system.tick()
            if wmsg:
                self.memory_manager.add_event(wmsg)
        except Exception as e:
            logger.debug(f"Weather tick error: {e}")

        # Shops restock daily (checked every 30 turns; cheap)
        try:
            if self.turn_counter % 30 == 0:
                self.shop_manager.refresh_all_if_due()
        except Exception as e:
            logger.debug(f"Shop restock error: {e}")

        # Collection log scan (items in bag + current place)
        try:
            self.collection_log.tick()
        except Exception as e:
            logger.debug(f"Collection tick error: {e}")

        # Pet follower trails the player
        try:
            self.pet_system.update()
        except Exception as e:
            logger.debug(f"Pet update error: {e}")

        # Diary tiers auto-claim when their tasks are all done
        try:
            if self.turn_counter % 10 == 0:
                self.diary_manager.check_and_claim()
        except Exception as e:
            logger.debug(f"Diary check error: {e}")

        # Nightly: NPC reflection + the world director's overnight events
        try:
            day = self.world.time // (24 * 60)
            if day != getattr(self, "_last_reflection_day", day):
                from engine.npc_memory import nightly_reflection
                nightly_reflection(self)
                self.world_director.run_night()
                self.faction_ticker.run_day()
                self.radiant_quests.run_morning()
                self.dm.run_scheduled()
                try:
                    self.dm_autonomous.run_day()
                except Exception as e:
                    logger.debug(f"Autonomous DM error: {e}")
                if self.dm_bridge is not None:
                    self.dm_bridge.export_digest()
                from engine.rest import snapshot
                self._day_metrics = snapshot(self)
            self._last_reflection_day = day
        except Exception as e:
            logger.debug(f"Nightly systems error: {e}")

        # Advance in-flight projectiles
        try:
            results = self.projectile_manager.tick(dt=1.0)
            for r in results:
                if r.message:
                    self.memory_manager.add_event(r.message)
        except Exception as e:
            logger.debug(f"Projectile tick error: {e}")

        # Companions follow / fight
        try:
            self.companion_manager.update()
        except Exception as e:
            logger.debug(f"Companion update error: {e}")

        if self.turn_counter % config.NPC_ACTION_INTERVAL == 0:
            self.process_npc_turns_async()

    # ====================================================================
    # Player API (delegates to PlayerActions)
    # ====================================================================

    def move_player(self, dx: int, dy: int, careful: bool = False) -> bool:
        return self.player_actions.move(dx, dy, careful=careful)

    def pickup_item(self, item_name: str = None) -> str:
        return self.player_actions.pickup(item_name)

    def drop_item(self, item_name: str) -> str:
        return self.player_actions.drop(item_name)

    def use_item(self, item_name: str) -> str:
        return self.player_actions.use(item_name)

    def attack_character(self, target_name: str) -> str:
        return self.player_actions.attack(target_name)

    def interact_with_npc(self, npc_id: str, message: str = None) -> str:
        return self.dialog_system.player_to_npc(npc_id, message)

    # ---- quest API used by UI -----------------------------------------

    def quests_offered_by(self, npc_id: str):
        if not self.quest_manager:
            return []
        return self.quest_manager.offered_by(npc_id)

    def quests_to_turn_in_with(self, npc_id: str):
        if not self.quest_manager:
            return []
        return self.quest_manager.ready_for_turn_in(npc_id)

    def accept_quest(self, quest_id: str) -> bool:
        if not self.quest_manager:
            return False
        if not self.quest_manager.accept_quest(quest_id):
            return False
        quest = self.quest_manager.get(quest_id)
        if quest:
            self.memory_manager.add_event(f"Quest accepted: {quest.title}")
        return True

    # Party / interior / spell / equipment / banking / crafting APIs are
    # provided by GameAPIMixin (engine/game_api_mixin.py).

    def turn_in_quest(self, quest_id: str) -> bool:
        if not self.quest_manager:
            return False
        level_before = self.player.level
        ok = self.quest_manager.turn_in(quest_id, self.player)
        if ok:
            quest = self.quest_manager.get(quest_id)
            self.memory_manager.add_event(
                f"Quest turned in: {quest.title} (+{quest.reward_gold}g, "
                f"+{quest.reward_xp}xp)")
            try:
                from engine.player_deeds import record_deed
                record_deed(self, f"completed '{quest.title}'")
            except Exception:
                pass
            # Quest points + guild rank-ups
            try:
                qp = int(quest.metadata.get("quest_points", 0))
                for note in self.guild.award_points(qp):
                    self.memory_manager.add_event(note)
            except Exception:
                pass
            # Completing someone's quest earns real trust
            giver = self.npc_manager.get_npc(quest.giver_id) \
                if quest.giver_id else None
            if giver is not None:
                giver.modify_relationship(self.player.id, 15)
                try:
                    self.heart_events.maybe_trigger(giver)
                except Exception:
                    pass
            # Surface level-ups in the game event log
            if self.player.level > level_before:
                for lvl in range(level_before + 1, self.player.level + 1):
                    self.memory_manager.add_event(
                        f"** Level up! {self.player.name} is now level {lvl}. **")
        return ok

    # ====================================================================
    # NPC turn processing
    # ====================================================================

    def _npc_turns_due(self) -> bool:
        """NPCs act on the turn cadence — or a slow wall-clock tick while
        the player idles. The GUI calls processing every FRAME (30/s);
        without this guard a static turn counter resting on a multiple of
        NPC_ACTION_INTERVAL made every nearby NPC act 30x per second,
        flooding the log."""
        import time
        now = time.monotonic()
        last_turn = getattr(self, "_npc_last_turn", None)
        last_time = getattr(self, "_npc_last_time", 0.0)
        turn_due = (self.turn_counter != last_turn and
                    self.turn_counter % config.NPC_ACTION_INTERVAL == 0)
        idle_due = (now - last_time) >= 3.0
        if not (turn_due or idle_due):
            return False
        self._npc_last_turn = self.turn_counter
        self._npc_last_time = now
        return True

    def process_npc_turns(self) -> None:
        """Synchronous NPC turn (kept for terminal mode)."""
        if not self._npc_turns_due():
            return
        for npc_id, npc in list(self.npc_manager.npcs.items()):
            if hasattr(npc, "is_active") and not npc.is_active():
                continue
            if npc_id.startswith("tut_"):
                continue  # tutorial cast stands still
            try:
                npc_x, npc_y = npc.position
                if self._distance_to_player(npc_x, npc_y) > \
                        self.effective_visibility() * 2:
                    continue
                visible_map = self.world.map.get_visible_description(npc_x, npc_y)
                world_state = self._world_state_for(npc_x, npc_y)
                history = self.memory_manager.get_recent_history()
                # Budget: monsters + cooling-down NPCs act heuristically
                from engine.llm_budget import (llm_action_allowed,
                                               heuristic_provider)
                if llm_action_allowed(self, npc):
                    action = self.llm_interface.get_npc_action(
                        npc, world_state, history, visible_map)
                else:
                    action = heuristic_provider(self).get_npc_action(
                        npc, world_state, history, visible_map)
                self.action_router.process(npc, action)
            except Exception as e:
                logger.error(f"NPC {npc_id} error: {e}")

    def process_npc_turns_async(self) -> None:
        """Async / multiprocess NPC processing — falls back to sync if PM absent."""
        if not self.process_manager:
            self.process_npc_turns()
            return

        # Shared state
        self.process_manager.update_shared_state("game_state", {
            "time_of_day": self.world.get_time_of_day(),
            "turn_counter": self.turn_counter,
            "player_position": self.player.position,
        })
        self.process_manager.check_process_health()

        # Collect responses
        for npc_id, resp in self.process_manager.get_responses().items():
            npc = self.npc_manager.get_npc(npc_id)
            if not npc or not npc.is_active():
                continue
            if resp.get("type") == "action":
                self.action_router.process(npc, resp["action_data"])
            elif resp.get("type") == "error":
                logger.error(f"NPC {npc_id}: {resp.get('error')}")
            self.processing_npcs.discard(npc_id)

        # Send new commands — on the NPC cadence, not per frame
        if not self._npc_turns_due():
            return
        from engine.llm_budget import llm_action_allowed, heuristic_provider
        for npc_id, npc in self.npc_manager.npcs.items():
            if not npc.is_active() or npc_id in self.processing_npcs:
                continue
            if npc_id.startswith("tut_"):
                continue  # tutorial cast stands still
            nx, ny = npc.position
            if self._distance_to_player(nx, ny) > \
                    self.effective_visibility() * 2:
                continue
            # Budget: only NPCs off cooldown burn a subprocess LLM call;
            # the rest act heuristically inline (cheap)
            if not llm_action_allowed(self, npc):
                try:
                    action = heuristic_provider(self).get_npc_action(
                        npc, self._world_state_for(nx, ny),
                        self.memory_manager.get_recent_history(),
                        self.world.map.get_visible_description(nx, ny))
                    self.action_router.process(npc, action)
                except Exception as e:
                    logger.debug(f"Heuristic fallback error: {e}")
                continue
            self.processing_npcs.add(npc_id)
            self.process_manager.send_command(npc_id, "get_action", {
                "world_state": self._world_state_for(nx, ny),
                "game_history": self.memory_manager.get_recent_history(),
                "visible_map": self.world.map.get_visible_description(nx, ny),
            })

    # ====================================================================
    # Game state
    # ====================================================================

    def get_game_state(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "map": self.world.map,
            "world": self.world,
            "npcs": list(self.npc_manager.npcs.values()),
            "visible_map": self.world.map.get_visible_description(
                *self.player.position) if self.player else "",
            "location": self.world.get_location_at(
                *self.player.position) if self.player else None,
            "time_of_day": self.world.get_time_of_day(),
            "formatted_time": self.world.get_formatted_time(),
            "recent_events": self.memory_manager.get_recent_history(8),
            "turn": self.turn_counter,
            "quests": self.quest_manager.summary() if self.quest_manager else "",
            "xp": (self.player.metadata or {}).get("xp", 0) if self.player else 0,
        }

    # ====================================================================
    # Save / load
    # ====================================================================

    def save_game(self, name: str = None, label: str = "") -> str:
        from engine.save_load import SaveManager
        return SaveManager().save(self, name, label)

    def load_game(self, name: str = None) -> bool:
        from engine.save_load import SaveManager
        return SaveManager().load(self, name)

    # ====================================================================
    # Internals
    # ====================================================================

    def find_character(self, name_or_id: str):
        if not name_or_id:
            return None
        text = name_or_id.lower()
        # Player keywords
        if any(t in text for t in ("player", "adventurer", "traveler",
                                   "stranger", "newcomer")):
            return self.player
        # By id
        if name_or_id in self.npc_manager.npcs:
            return self.npc_manager.npcs[name_or_id]
        # By name
        for npc in self.npc_manager.npcs.values():
            if npc.name.lower() == text:
                return npc
        # Substring match
        for npc in self.npc_manager.npcs.values():
            if npc.name.lower() in text or text in npc.name.lower():
                return npc
        # Symbol
        if len(name_or_id) == 1:
            for npc in self.npc_manager.npcs.values():
                if npc.symbol.lower() == text:
                    return npc
        return None

    def _distance_to_player(self, x: int, y: int) -> float:
        px, py = self.player.position
        return ((px - x) ** 2 + (py - y) ** 2) ** 0.5

    def _world_state_for(self, x: int, y: int) -> Dict[str, Any]:
        loc = self.world.get_location_at(x, y)
        return {
            "current_location": loc.name if loc else "wilderness",
            "time_of_day": self.world.get_time_of_day(),
            "player_position": tuple(self.player.position)
            if self.player else None,
        }
