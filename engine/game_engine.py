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

logger = logging.getLogger("llm_rpg.engine")


class GameEngine:
    """High-level game engine. UIs interact through this object."""

    def __init__(self, llm_model: str = None, llm_provider: str = None,
                 enable_npc_processes: bool = True,
                 enable_quests: bool = True):
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
        self.initialize_demo_game()

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

    def initialize_demo_game(self) -> None:
        """Set up a starter world + NPCs + player + initial quests."""
        from engine.demo_setup import initialize_demo_world
        initialize_demo_world(self)
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

        # Random wilderness encounter
        try:
            msg = self.encounter_manager.maybe_spawn()
            if msg:
                self.memory_manager.add_event(msg)
        except Exception as e:
            logger.debug(f"Encounter spawn error: {e}")

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

    def move_player(self, dx: int, dy: int) -> bool:
        return self.player_actions.move(dx, dy)

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

    # ---- party API ----------------------------------------------------

    def recruit(self, npc_id: str) -> str:
        return self.companion_manager.recruit(npc_id)

    def dismiss_companion(self, npc_id: str) -> str:
        return self.companion_manager.dismiss(npc_id)

    def party_members(self):
        return self.companion_manager.members()

    # ---- interiors API used by UI ------------------------------------

    def enter_building(self) -> str:
        """Step into a building interior at the player's current location."""
        if self.current_interior:
            return "You are already inside."
        loc = self.world.get_location_at(*self.player.position)
        if not loc:
            return "There's no building here."
        inter = self.interiors.get(loc.name)
        if not inter:
            return f"You can't enter the {loc.name}."
        self.exterior_return_pos = self.player.position
        self.current_interior = inter
        # Place player at the door
        self.player.position = inter.door
        msg = f"You enter the {loc.name}. {inter.description}"
        self.memory_manager.add_event(msg)
        return msg

    def exit_building(self) -> str:
        if not self.current_interior:
            return "You are already outside."
        name = self.current_interior.name
        self.current_interior = None
        if self.exterior_return_pos:
            self.player.position = self.exterior_return_pos
            self.world.map.place_character(self.player, *self.player.position)
            self.exterior_return_pos = None
        msg = f"You leave the {name}."
        self.memory_manager.add_event(msg)
        return msg

    # ---- quest board API ---------------------------------------------

    def quest_board_at_player(self):
        return self.quest_board_manager.board_at_player()

    def accept_quest_from_board(self, quest_id: str) -> bool:
        ok = self.quest_board_manager.accept_from_board(quest_id)
        if ok:
            self.memory_manager.add_event(f"Accepted quest from board: {quest_id}")
        return ok

    # ---- banking + crafting API used by UI ---------------------------

    def deposit_gold(self, amount: int) -> str:
        return self.bank.deposit(amount)

    def withdraw_gold(self, amount: int) -> str:
        return self.bank.withdraw(amount)

    def bank_balance(self) -> int:
        return self.bank.balance()

    def can_craft_at_player(self, output_id: str) -> str:
        from items.crafting import can_craft
        loc = self.world.get_location_at(*self.player.position)
        props = dict(loc.properties) if loc else {}
        return can_craft(self.player, output_id, props)

    def craft(self, output_id: str) -> str:
        from items.crafting import craft
        loc = self.world.get_location_at(*self.player.position)
        props = dict(loc.properties) if loc else {}
        msg = craft(self.player, output_id, props)
        self.memory_manager.add_event(msg)
        return msg

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
            # Surface level-ups in the game event log
            if self.player.level > level_before:
                for lvl in range(level_before + 1, self.player.level + 1):
                    self.memory_manager.add_event(
                        f"** Level up! {self.player.name} is now level {lvl}. **")
        return ok

    # ====================================================================
    # NPC turn processing
    # ====================================================================

    def process_npc_turns(self) -> None:
        """Synchronous NPC turn (kept for terminal mode)."""
        if self.turn_counter % config.NPC_ACTION_INTERVAL != 0:
            return
        for npc_id, npc in list(self.npc_manager.npcs.items()):
            if hasattr(npc, "is_active") and not npc.is_active():
                continue
            try:
                npc_x, npc_y = npc.position
                if self._distance_to_player(npc_x, npc_y) > \
                        config.DEFAULT_VISIBILITY_RANGE * 2:
                    continue
                visible_map = self.world.map.get_visible_description(npc_x, npc_y)
                world_state = self._world_state_for(npc_x, npc_y)
                history = self.memory_manager.get_recent_history()
                action = self.llm_interface.get_npc_action(
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

        # Send new commands
        for npc_id, npc in self.npc_manager.npcs.items():
            if not npc.is_active() or npc_id in self.processing_npcs:
                continue
            nx, ny = npc.position
            if self._distance_to_player(nx, ny) > \
                    config.DEFAULT_VISIBILITY_RANGE * 2:
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
        }
