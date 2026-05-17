"""Game GUI (pygame) — thin orchestrator over renderer/hud/input.

The legacy monolithic gui.py is preserved as `gui_legacy.py`.
"""

import logging
import os
from typing import Optional

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

from ui.renderer import MapRenderer
from ui.hud import HUD
from ui.input_handler import InputHandler

logger = logging.getLogger("llm_rpg.gui")


class GameGUI:
    """Pygame GUI — wraps engine state in a windowed application."""

    def __init__(self, engine, width: int = 1280, height: int = 800,
                 tile_size: int = 32, title: str = "LLM-RPG"):
        if not PYGAME_OK:
            raise RuntimeError("pygame is not installed")
        self.engine = engine
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.running = False
        self.mode = "play"               # "play" | "dialog" | "menu"
        self.overlay = None              # Title, lines tuple for overlays

        # Dialog state
        self.dialog_npc_id: Optional[str] = None
        self.dialog_history: list = []   # list of strings (NPC last reply)
        self.dialog_input: str = ""
        self.dialog_pending_reply: Optional[str] = None

        # Init pygame
        pygame.init()
        pygame.display.set_caption(title)
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()

        # Subsystems
        self.renderer = MapRenderer(tile_size=tile_size)
        self.hud = HUD()
        self.input_handler = InputHandler(engine, self)

        # Layout
        self._compute_layout()

    # ---- layout ------------------------------------------------------

    def _compute_layout(self) -> None:
        side = 320
        bottom = 200
        self.layout = {
            "map": pygame.Rect(0, 0, self.width - side, self.height - bottom),
            "status": pygame.Rect(self.width - side, 0,
                                  side, self.height // 2),
            "quests": pygame.Rect(self.width - side, self.height // 2,
                                  side, self.height // 2 - bottom),
            "events": pygame.Rect(0, self.height - bottom,
                                  (self.width - side) // 2 + 100, bottom),
            "minimap": pygame.Rect((self.width - side) // 2 + 100,
                                   self.height - bottom,
                                   self.width - side -
                                   ((self.width - side) // 2 + 100),
                                   bottom),
        }

    # ---- main loop ---------------------------------------------------

    def start(self) -> None:
        self.engine.start_game()
        self.running = True
        self._loop()
        self.shutdown()

    def _loop(self) -> None:
        while self.running and self.engine.running:
            for event in pygame.event.get():
                self.input_handler.handle_event(event)
            # Drive NPC processes (non-blocking)
            try:
                self.engine.process_npc_turns_async()
            except Exception as e:
                logger.warning(f"NPC async tick error: {e}")
            self._render()
            self.clock.tick(30)

    def update(self) -> None:
        """Compat shim for terminal-style loops."""
        pass

    def shutdown(self) -> None:
        try:
            self.engine.end_game()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass

    # ---- rendering ---------------------------------------------------

    def _render(self) -> None:
        self.screen.fill((15, 15, 20))
        self.renderer.render(self.screen, self.engine, self.layout["map"])
        self.hud.draw(self.screen, self.engine, self.layout)

        if self.mode == "dialog":
            npc = self.engine.npc_manager.get_npc(self.dialog_npc_id)
            name = npc.name if npc else "???"
            self.hud.draw_dialog_box(
                self.screen, self.screen.get_rect(),
                name,
                self.dialog_pending_reply or "",
                prompt=f"> {self.dialog_input}_   (Enter to send, Esc to leave)",
            )

        if self.mode == "menu" and self.overlay:
            title, lines = self.overlay
            self.hud.draw_text_overlay(
                self.screen, self.screen.get_rect(), title, lines)

        pygame.display.flip()

    # ---- overlays ---------------------------------------------------

    def show_inventory(self) -> None:
        p = self.engine.player
        lines = [f"Gold: {p.gold}",
                 f"HP: {p.hp}/{p.max_hp}",
                 "", "Items:"]
        for it in p.inventory:
            name = it.name if hasattr(it, "name") else str(it)
            qty = getattr(it, "quantity", 1)
            extras = []
            if getattr(it, "damage", 0):
                extras.append(f"dmg {it.damage}")
            if getattr(it, "armor", 0):
                extras.append(f"arm {it.armor}")
            if getattr(it, "heal_amount", 0):
                extras.append(f"heal {it.heal_amount}")
            tag = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"  - {name}" +
                         (f" x{qty}" if qty > 1 else "") + tag)
        if not p.inventory:
            lines.append("  (empty)")
        self.overlay = ("Inventory", lines)
        self.mode = "menu"

    def show_quests(self) -> None:
        qm = self.engine.quest_manager
        if not qm:
            self.overlay = ("Quests", ["Quest system disabled."])
        else:
            self.overlay = ("Quests", qm.summary().split("\n"))
        self.mode = "menu"

    def show_character_sheet(self) -> None:
        p = self.engine.player
        lines = [
            f"{p.name} (Level {p.level} {p.race.value} {p.character_class.value})",
            "",
            f"STR {p.strength}   DEX {p.dexterity}   CON {p.constitution}",
            f"INT {p.intelligence}   WIS {p.wisdom}   CHA {p.charisma}",
            "",
            f"HP: {p.hp}/{p.max_hp}",
            f"Gold: {p.gold}",
            f"XP: {(p.metadata or {}).get('xp', 0)}",
            "",
            "Goals:",
        ]
        for g in p.goals:
            lines.append(f"  * {g}")
        self.overlay = ("Character Sheet", lines)
        self.mode = "menu"

    def show_help(self) -> None:
        lines = [
            "Movement: WASD or Arrow keys",
            "Attack adjacent: SPACE or F",
            "Talk to NPC: T",
            "Pick up item: G or E",
            "Use potion: H",
            "Inventory: I",
            "Quests: Q",
            "Character sheet: C",
            "Save / Load: F5 / F9",
            "Help: F1 or /",
            "Quit: ESC",
        ]
        self.overlay = ("Controls", lines)
        self.mode = "menu"

    # ---- dialog -----------------------------------------------------

    def start_dialog(self, npc_id: str) -> None:
        self.dialog_npc_id = npc_id
        self.dialog_input = ""
        # Initial greeting
        try:
            self.dialog_pending_reply = self.engine.interact_with_npc(npc_id)
        except Exception as e:
            logger.warning(f"Dialog start error: {e}")
            self.dialog_pending_reply = "..."
        self.mode = "dialog"

    def submit_dialog(self) -> None:
        if not self.dialog_npc_id:
            self.end_dialog()
            return
        msg = self.dialog_input.strip()
        self.dialog_input = ""
        if not msg:
            return
        try:
            self.dialog_pending_reply = self.engine.interact_with_npc(
                self.dialog_npc_id, msg)
        except Exception as e:
            logger.warning(f"Dialog submit error: {e}")
            self.dialog_pending_reply = "..."

    def end_dialog(self) -> None:
        self.dialog_npc_id = None
        self.dialog_pending_reply = None
        self.dialog_input = ""
        self.mode = "play"

    def dialog_quest_action(self, idx: int) -> None:
        """Handle 1-9 hotkeys in dialog mode for accepting/turning in quests."""
        if not self.dialog_npc_id:
            return
        offered = self.engine.quests_offered_by(self.dialog_npc_id)
        ready = self.engine.quests_to_turn_in_with(self.dialog_npc_id)
        combined = list(offered) + list(ready)
        if idx >= len(combined):
            return
        quest = combined[idx]
        if quest in offered:
            self.engine.accept_quest(quest.id)
            self.dialog_pending_reply = (
                f"(Quest accepted: {quest.title})"
            )
        else:
            self.engine.turn_in_quest(quest.id)
            self.dialog_pending_reply = (
                f"(Quest turned in: {quest.title}. "
                f"Reward: {quest.reward_gold}g, {quest.reward_xp}xp)"
            )
