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
from llm.llm_interface import LLMInterface
from engine.memory_manager import MemoryManager
from engine.game_api_mixin import GameAPIMixin

logger = logging.getLogger("llm_rpg.engine")


class GameEngine(GameAPIMixin):
    """High-level game engine. UIs interact through this object."""

    def __init__(self, llm_model: str = None, llm_provider: str = None,
                 enable_npc_processes: bool = True,
                 enable_quests: bool = True,
                 player_spec=None,
                 start_tutorial: bool = False,
                 enable_dm_bridge: bool = False,
                 world_kind: str = "default"):
        # Core systems --------------------------------------------------
        # OAKVALE T5b: a big-town world gets a larger map so the whole town +
        # its countryside fit (the classic world stays its default size).
        try:
            from world.town_region import region_size
            _sz = region_size(world_kind)
        except Exception:
            _sz = None
        self.world = World(*_sz) if _sz else World()
        self.npc_manager = NPCManager()
        self.memory_manager = MemoryManager()
        self.llm_interface = LLMInterface(
            model_name=llm_model or config.DEFAULT_MODEL,
            provider=llm_provider or getattr(config, "DEFAULT_PROVIDER", "heuristic"),
        )

        from engine.engine_setup import build_subsystems
        build_subsystems(self, llm_model=llm_model,
                         enable_quests=enable_quests)

        # State --------------------------------------------------------
        self.player: Optional[Character] = None
        self.running = False
        self.turn_counter = 0
        self.processing_npcs = set()
        self.player_dead = False  # set by combat_system when player defeated

        # Initialize demo world
        from engine.tutorial import TutorialManager
        self.tutorial_manager = TutorialManager(self)
        self.initialize_demo_game(player_spec=player_spec,
                                  world_kind=world_kind)
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

    def initialize_demo_game(self, player_spec=None,
                             world_kind="default") -> None:
        """Set up a starter world + NPCs + player + initial quests."""
        from engine.demo_setup import initialize_demo_world
        initialize_demo_world(self, player_spec=player_spec,
                              world_kind=world_kind)
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
        try:   # walls are solid — install the movement guard (2026-07-12)
            from engine.movement import ensure_wall_guard
            ensure_wall_guard(self)
        except Exception as e:
            logger.debug(f"Wall guard: {e}")
        from engine.engine_setup import seed_world
        seed_world(self)

    def end_game(self) -> None:
        self.running = False
        self.memory_manager.add_event("The adventure has ended.")
        if self.process_manager:
            self.process_manager.stop_processes()
        if hasattr(self.llm_interface, "shutdown"):
            self.llm_interface.shutdown()

    def advance_turn(self) -> None:
        # Re-entrancy guard (M.2): an agent-driven hero acts through the
        # real player-action API mid-turn, which would otherwise cascade
        # a nested world tick. When already advancing, its action still
        # happens (position/attack resolve first) but the pipeline runs
        # once, not once per agent.
        if getattr(self, "_advancing", False):
            return
        self._advancing = True
        try:
            from engine.turn_pipeline import run_turn
            run_turn(self)
        finally:
            self._advancing = False

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
        idle_due = (now - last_time) >= config.NPC_IDLE_INTERVAL
        if not (turn_due or idle_due):
            return False
        self._npc_last_turn = self.turn_counter
        self._npc_last_time = now
        return True

    def process_npc_turns(self) -> None:
        """Synchronous NPC turn (kept for terminal mode)."""
        if not self._npc_turns_due():
            return
        try:   # re-assert after any map swap (streaming keeps it; a fresh
            from engine.movement import ensure_wall_guard  # map re-installs)
            ensure_wall_guard(self)
        except Exception:
            pass
        try:   # band nearby hostiles into packs before they act (P19.3)
            self.monster_packs.update()
        except Exception as e:
            logger.debug(f"Monster packs: {e}")
        for npc_id, npc in list(self.npc_manager.npcs.items()):
            if hasattr(npc, "is_active") and not npc.is_active():
                continue
            if npc_id.startswith("tut_"):
                continue  # tutorial cast stands still
            # Party members are the companion system's to move —
            # schedules were marching them home mid-adventure (PT3.3)
            try:
                if npc_id in self.companion_manager.party:
                    continue
            except Exception:
                pass
            # roster player-characters are driven by their controller
            # (human / M.2 agent), never the ambient NPC AI (M.1b); the same
            # goes for adventurer NPCs (driven by AdventurerSystem, P-M.6)
            meta = getattr(npc, "metadata", {}) or {}
            if meta.get("player_char") or meta.get("adventurer"):
                continue
            # neutral wildlife are driven by the WildlifeSystem (P32.3), never
            # the ambient hostile/social AI
            if meta.get("wildlife"):
                continue
            # P37.6b: a hostile that already bit via the per-turn AggressionSystem
            # this turn doesn't also swing here (no double attack)
            if meta.get("_aggro_turn") == self.turn_counter:
                continue
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
            # Party members are the companion system's to move —
            # schedules were marching them home mid-adventure (PT3.3)
            try:
                if npc_id in self.companion_manager.party:
                    continue
            except Exception:
                pass
            # roster player-characters are driven by their controller
            # (human / M.2 agent), never the ambient NPC AI (M.1b); the same
            # goes for adventurer NPCs (driven by AdventurerSystem, P-M.6)
            meta = getattr(npc, "metadata", {}) or {}
            if meta.get("player_char") or meta.get("adventurer"):
                continue
            # neutral wildlife are driven by the WildlifeSystem (P32.3), never
            # the ambient hostile/social AI
            if meta.get("wildlife"):
                continue
            # P37.6b: a hostile that already bit via the per-turn AggressionSystem
            # this turn doesn't also swing here (no double attack)
            if meta.get("_aggro_turn") == self.turn_counter:
                continue
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
        # By name — prefer the NEAREST active match. Names can collide now
        # (P19.2: a Wandering Troll in an overworld den and one in a crypt),
        # so "attack the Wandering Troll" must mean the one in front of you.
        exact = [n for n in self.npc_manager.npcs.values()
                 if n.name.lower() == text]
        if exact:
            return self._nearest_active(exact)
        # Substring match
        subs = [n for n in self.npc_manager.npcs.values()
                if n.name.lower() in text or text in n.name.lower()]
        if subs:
            return self._nearest_active(subs)
        # Symbol
        if len(name_or_id) == 1:
            for npc in self.npc_manager.npcs.values():
                if npc.symbol.lower() == text:
                    return npc
        return None

    def _nearest_active(self, candidates):
        """Of same-named characters, the nearest active one to the player
        (an inactive one only if nothing else matches)."""
        px, py = self.player.position

        def key(n):
            x, y = n.position
            return (0 if n.is_active() else 1,
                    (px - x) ** 2 + (py - y) ** 2)

        return min(candidates, key=key)

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
