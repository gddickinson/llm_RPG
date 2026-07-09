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
        # "play" | "dialog" | "menu" | "death" | "inventory" | "shop"
        self.mode = "play"
        self.overlay = None              # Title, lines tuple for overlays

        # Dialog state
        self.dialog_npc_id: Optional[str] = None
        self.dialog_history: list = []   # list of strings (NPC last reply)
        self.dialog_input: str = ""
        self.dialog_pending_reply: Optional[str] = None

        # Inventory + shop + crafting panels (lazy)
        self.inventory_panel = None
        self.shop_panel = None
        self.crafting_panel = None

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
        # Mark engine so combat_system knows there's a GUI to show death popup
        self.engine._has_gui = True
        self.engine.start_game()
        self.running = True
        self._loop()
        self.shutdown()

    def _loop(self) -> None:
        while self.running and self.engine.running:
            # Auto-enter death mode when the player has been defeated
            if getattr(self.engine, "player_dead", False) and self.mode != "death":
                self.mode = "death"
            for event in pygame.event.get():
                self.input_handler.handle_event(event)
            # Drive NPC processes only while alive
            if self.mode != "death":
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

        if self.mode == "inventory" and self.inventory_panel is not None:
            self.inventory_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "shop" and self.shop_panel is not None:
            self.shop_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "crafting" and self.crafting_panel is not None:
            self.crafting_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "death":
            self._draw_death_popup()

        pygame.display.flip()

    def _draw_death_popup(self) -> None:
        """Centered popup with Restart / Quit options."""
        screen_rect = self.screen.get_rect()
        # Dim the world behind the popup
        veil = pygame.Surface(screen_rect.size, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        self.screen.blit(veil, (0, 0))

        # Popup box
        w, h = 460, 220
        box = pygame.Rect((screen_rect.width - w) // 2,
                          (screen_rect.height - h) // 2, w, h)
        pygame.draw.rect(self.screen, (25, 10, 12), box)
        pygame.draw.rect(self.screen, (200, 60, 60), box, 3)

        # Title
        if self.hud.big_font:
            title_surf = self.hud.big_font.render(
                "You have been defeated!", True, (255, 90, 90))
            self.screen.blit(
                title_surf,
                (box.centerx - title_surf.get_width() // 2, box.y + 28),
            )
        if self.hud.font:
            xp = (self.engine.player.metadata or {}).get("xp", 0)
            level = self.engine.player.level
            sub = self.hud.font.render(
                f"Final level: {level}    XP: {xp}    Turn: {self.engine.turn_counter}",
                True, (220, 220, 220))
            self.screen.blit(
                sub,
                (box.centerx - sub.get_width() // 2, box.y + 72),
            )
            opt1 = self.hud.font.render(
                "[R] Restart", True, (160, 230, 160))
            self.screen.blit(
                opt1,
                (box.centerx - opt1.get_width() // 2, box.y + 120),
            )
            opt2 = self.hud.font.render(
                "[Q] Quit", True, (230, 160, 160))
            self.screen.blit(
                opt2,
                (box.centerx - opt2.get_width() // 2, box.y + 150),
            )
            hint = self.hud.font.render(
                "(or press ESC to quit)", True, (160, 160, 180))
            self.screen.blit(
                hint,
                (box.centerx - hint.get_width() // 2, box.y + 184),
            )

    def restart(self) -> None:
        """Rebuild the engine and resume play. Called from the death popup."""
        old = self.engine
        provider = old.llm_interface.provider_name
        model = old.llm_interface.model_name
        try:
            old.end_game()
        except Exception:
            pass
        from engine.game_engine import GameEngine
        self.engine = GameEngine(
            llm_model=model,
            llm_provider=provider,
            enable_npc_processes=False,
            enable_quests=True,
        )
        self.engine._has_gui = True
        self.engine.start_game()
        self.input_handler.engine = self.engine
        self.mode = "play"
        self.overlay = None
        self.dialog_npc_id = None
        self.dialog_pending_reply = None
        self.dialog_input = ""

    # ---- overlays ---------------------------------------------------

    def show_inventory(self) -> None:
        from ui.inventory_panel import InventoryPanel
        if self.inventory_panel is None:
            self.inventory_panel = InventoryPanel(self.engine)
        self.mode = "inventory"

    def show_shop(self, merchant_npc) -> None:
        from ui.shop_panel import ShopPanel
        self.shop_panel = ShopPanel(self.engine, merchant_npc)
        self.mode = "shop"

    def show_crafting(self) -> None:
        from ui.crafting_panel import CraftingPanel
        if self.crafting_panel is None:
            self.crafting_panel = CraftingPanel(self.engine)
        self.mode = "crafting"

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
            "MOVEMENT",
            "  WASD / Arrows : move (off-edge = enter a new region)",
            "  TAB           : enter / exit building or cave-dungeon",
            "  L             : look around (describe what you see)",
            "",
            "COMBAT",
            "  SPACE / F     : melee attack (uses equipped weapon)",
            "  R             : ranged attack (needs equipped bow/sling/etc.)",
            "  X             : cast Fireball at nearest hostile",
            "  V             : cast Heal on self",
            "",
            "ITEMS & WORLD",
            "  G / E         : pick up item on the ground",
            "  H             : drink potion",
            "  Z             : forage (forest / grass)",
            "  T             : talk to adjacent NPC",
            "",
            "INTERACTIVE OVERLAYS",
            "  I             : inventory + equipment slots",
            "                  (E equip/unequip, Q use, D drop)",
            "  B             : barter — shop with adjacent merchant",
            "                  (Left/Right column, Enter buy/sell)",
            "  K             : crafting — browse + craft recipes",
            "                  (forge recipes need Durgan's Forge)",
            "  Q             : quest log",
            "  C             : character sheet",
            "",
            "BANKING",
            "  N             : deposit all gold (at temple/shop)",
            "  M             : withdraw all bank gold",
            "",
            "SYSTEM",
            "  F5 / F9       : save / load",
            "  F1 or /       : this help",
            "  ESC           : close menu / quit",
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
