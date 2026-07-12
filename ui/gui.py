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

# below this the side/bottom panels stop leaving a usable map
MIN_W, MIN_H = 900, 640


def compute_layout(width: int, height: int) -> dict:
    """The screen regions for a given window size (PUX.4c) — RESPONSIVE:
    the side/bottom panels scale within sane clamps and the map fills
    whatever is left, so the layout works at any window size, not just
    the old hard-pinned 1280×800. Pure (no display) so it's unit-tested.
    """
    width = max(MIN_W, width)
    height = max(MIN_H, height)
    side = max(260, min(420, int(width * 0.26)))
    bottom = max(150, min(240, int(height * 0.24)))
    bottom = min(bottom, height // 2 - 60)     # keep the Quests panel room
    map_w = width - side
    ev_w = max(160, min(map_w - 140, map_w // 2 + 80))
    return {
        "map": pygame.Rect(0, 0, map_w, height - bottom),
        "status": pygame.Rect(width - side, 0, side, height // 2),
        "quests": pygame.Rect(width - side, height // 2,
                              side, height // 2 - bottom),
        "events": pygame.Rect(0, height - bottom, ev_w, bottom),
        "minimap": pygame.Rect(ev_w, height - bottom,
                               map_w - ev_w, bottom),
        # the party panel fills the bottom-right (PUX.4b)
        "party": pygame.Rect(width - side, height - bottom, side, bottom),
    }


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
        self.dialog_menu: list = []      # PUX.6 quick-pick options

        # Inventory + shop + crafting + spell panels (lazy)
        self.inventory_panel = None
        self.shop_panel = None
        self.crafting_panel = None
        self.spell_panel = None
        self.settings_panel = None

        # Init pygame
        pygame.init()
        pygame.display.set_caption(title)
        self.fullscreen = False
        self._windowed_size = (width, height)
        self.screen = pygame.display.set_mode((width, height),
                                              pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        # Subsystems
        self.renderer = MapRenderer(tile_size=tile_size)
        self.hud = HUD()
        self.input_handler = InputHandler(engine, self)
        # Procedural sound (SFX via event observer, weather ambience)
        try:
            from ui.sound import SoundManager
            self.sound = SoundManager()
            if self.sound.enabled:
                engine.memory_manager.add_observer(self.sound.on_event)
        except Exception as e:
            logger.debug(f"Sound unavailable: {e}")
            self.sound = None

        # Layout
        self._compute_layout()

    # ---- layout ------------------------------------------------------

    def _compute_layout(self) -> None:
        self.layout = compute_layout(self.width, self.height)

    def resize(self, w: int, h: int) -> None:
        """Re-lay the screen for a new window size (PUX.4c)."""
        self.width = max(MIN_W, w)
        self.height = max(MIN_H, h)
        self.screen = pygame.display.set_mode((self.width, self.height),
                                              pygame.RESIZABLE)
        self._compute_layout()

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.width = max(MIN_W, info.current_w)
            self.height = max(MIN_H, info.current_h)
            self.screen = pygame.display.set_mode(
                (self.width, self.height), pygame.FULLSCREEN)
        else:
            self.width, self.height = self._windowed_size
            self.screen = pygame.display.set_mode(
                (self.width, self.height), pygame.RESIZABLE)
        self._compute_layout()

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
                if event.type == pygame.VIDEORESIZE:
                    self.resize(event.w, event.h)
                    continue
                if event.type == pygame.KEYDOWN and \
                        event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue
                # M.3: any keypress in play hands control back to the human
                # (set_away also flips the autoplay setting so the overlay
                # stays honest)
                if event.type == pygame.KEYDOWN and self.mode == "play" \
                        and self.engine.roster.is_away(self.engine.player):
                    self.engine.roster.set_away(self.engine.player, False)
                self.input_handler.handle_event(event)
            from ui.away_mode import heartbeat
            heartbeat(self)               # M.3 tick the world while away
            # Drive NPC processes only while alive
            if self.mode != "death":
                try:
                    self.engine.process_npc_turns_async()
                except Exception as e:
                    logger.warning(f"NPC async tick error: {e}")
            if self.sound is not None:
                try:
                    self.sound.update_ambient(
                        self.engine.current_weather())
                except Exception:
                    pass
            if getattr(self.engine, "dm_bridge", None) is not None:
                try:
                    self.engine.dm_bridge.tick()
                except Exception:
                    pass
            self._render()
            self.clock.tick(30)

    def update(self) -> None:
        """Compat shim for terminal-style loops."""
        pass

    def shutdown(self) -> None:
        if self.sound is not None:
            self.sound.shutdown()
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
                prompt=(f"> {self.dialog_input}_   (Enter send, Esc leave, "
                        f"/persuade /intimidate /deceive <argument>)"),
                menu=self.dialog_menu,
            )

        if self.mode in ("menu", "travel") and self.overlay:
            title, lines = self.overlay
            self.hud.draw_text_overlay(
                self.screen, self.screen.get_rect(), title, lines)

        if self.mode == "help":
            self.hud.draw_help_overlay(
                self.screen, self.screen.get_rect(), "Controls",
                getattr(self, "help_columns", ([], [])))

        if self.mode == "settings" and self.settings_panel is not None:
            self.settings_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "confirm_quit":
            self.hud.draw_text_overlay(
                self.screen, self.screen.get_rect(), "Leave the game?",
                ["", "Quit to desktop? Unsaved progress is lost.",
                 "  (F5 quicksaves)", "",
                 "  [Y] quit        [N] keep playing"])

        if self.mode == "inventory" and self.inventory_panel is not None:
            self.inventory_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "shop" and self.shop_panel is not None:
            self.shop_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "crafting" and self.crafting_panel is not None:
            self.crafting_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "spells" and self.spell_panel is not None:
            self.spell_panel.draw(self.screen, self.screen.get_rect())

        if self.mode == "death":
            self._draw_death_popup()

        # Top-most: the AUTOPLAY banner rides over everything in play
        if self.mode == "play":
            self.hud.draw_autoplay_banner(
                self.screen, self.engine, self.screen.get_rect())

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

    def show_spellbook(self) -> None:
        from ui.spell_panel import SpellPanel
        if self.spell_panel is None:
            self.spell_panel = SpellPanel(self.engine)
        self.mode = "spells"

    def show_topics(self) -> None:
        try:
            lines = self.engine.topic_journal.overlay_lines()
        except Exception:
            lines = ["Journal unavailable."]
        try:
            from engine.legends import overlay_lines as legend_lines
            lines += legend_lines(self.engine)
        except Exception:
            pass
        self.overlay = ("Journal — Topics & Legends", lines)
        self.mode = "menu"

    def show_travel(self) -> None:
        try:
            lines = self.engine.travel_system.overlay_lines()
        except Exception:
            lines = ["Travel unavailable."]
        self.overlay = ("Travel", lines)
        self.mode = "travel"

    def show_diaries(self) -> None:
        try:
            lines = self.engine.diary_manager.overlay_lines()
        except Exception:
            lines = ["Diaries unavailable."]
        self.overlay = ("Achievement Diaries", lines)
        self.mode = "menu"

    def show_collection_log(self) -> None:
        try:
            lines = self.engine.collection_log.overlay_lines()
        except Exception:
            lines = ["Collection log unavailable."]
        self.overlay = ("Collection Log", lines)
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
        ]
        try:
            lines.append(self.engine.guild.status_line())
        except Exception:
            pass
        lines += ["", "Skills:"]
        try:
            from engine.skill_progression import (skill_summary,
                                                  total_skill_level)
            for line in skill_summary(p):
                lines.append(f"  {line}")
            lines.append(f"  {'Total':<14} {total_skill_level(p):>3}")
        except Exception:
            lines.append("  (unavailable)")
        lines += ["", "Goals:"]
        for g in p.goals:
            lines.append(f"  * {g}")
        self.overlay = ("Character Sheet", lines)
        self.mode = "menu"

    def show_help(self) -> None:
        from ui.controls import help_columns
        self.help_columns = help_columns()
        self.mode = "help"

    def show_settings(self) -> None:
        from ui.settings_panel import SettingsPanel
        if self.settings_panel is None:
            self.settings_panel = SettingsPanel(self)
        self.mode = "settings"

    # ---- dialog -----------------------------------------------------

    def _refresh_dialog_menu(self) -> None:
        from engine import conversation
        npc = self.engine.npc_manager.get_npc(self.dialog_npc_id)
        self.dialog_menu = conversation.menu(self.engine, npc) \
            if npc is not None else []

    def start_dialog(self, npc_id: str) -> None:
        self.dialog_npc_id = npc_id
        self.dialog_input = ""
        try:
            self.dialog_pending_reply = self.engine.interact_with_npc(npc_id)
        except Exception as e:
            logger.warning(f"Dialog start error: {e}")
            self.dialog_pending_reply = "..."
        self._refresh_dialog_menu()
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
        self._refresh_dialog_menu()

    def end_dialog(self) -> None:
        self.dialog_npc_id = None
        self.dialog_pending_reply = None
        self.dialog_input = ""
        self.dialog_menu = []
        self.mode = "play"

    def dialog_quest_action(self, idx: int) -> None:
        """A numbered quick-pick from the conversation menu (PUX.6)."""
        from ui.dialog_menu import apply
        apply(self, idx)
