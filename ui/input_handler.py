"""Input handler — maps key/mouse events to engine actions.

Modes:
- 'play' (default): WASD/arrows move, F attack, T talk, I inventory, Q quests
- 'dialog': typing into dialog box
- 'menu': inventory/quest overlay shown
"""

import logging

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.input")

from ui import input_actions

# 8-directional movement on the numpad (the letter-corner keys QEZC that
# a WASD player would reach for are already bound to quit/interact/forage/
# sheet, so the numpad carries the diagonals — the classic roguelike map).
_NUMPAD_MOVE = {}
if PYGAME_OK:
    _NUMPAD_MOVE = {
        pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1),
        pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0),
        pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1),
        pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1),
    }


class InputHandler:
    """Translate pygame events into engine method calls."""

    def __init__(self, engine, gui):
        self.engine = engine
        self.gui = gui

    def handle_event(self, event) -> bool:
        """Return True if event was consumed by the input handler."""
        if event.type == pygame.QUIT:
            self.engine.end_game()
            self.gui.running = False
            return True

        # Click-to-target (P8.7 UX): left-click a visible enemy
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.gui.mode == "play":
            tile = self._pixel_to_tile(event.pos)
            if tile is not None:
                self.engine.targeting.lock_tile(*tile)
                return True

        # Death popup: only R / Q / ESC respond ----------------------------
        if self.gui.mode == "death":
            if event.type != pygame.KEYDOWN:
                return True
            if event.key == pygame.K_r:
                self.gui.restart()
                return True
            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                self.engine.end_game()
                self.gui.running = False
                return True
            return True

        # Help overlay — any key dismisses it -----------------------------
        if self.gui.mode == "help":
            if event.type == pygame.KEYDOWN:
                self.gui.mode = "play"
            return True

        # Quit confirmation — Y quits, N / Esc keeps playing
        if self.gui.mode == "confirm_quit":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_y, pygame.K_RETURN):
                    self.engine.end_game()
                    self.gui.running = False
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    self.gui.mode = "play"
            return True
        # Settings overlay
        if self.gui.mode == "settings":
            if self.gui.settings_panel is not None:
                return self.gui.settings_panel.handle_key(event)
            self.gui.mode = "play"
            return True
        # Dialog typing mode
        if self.gui.mode == "dialog":
            from ui.dialog_input import handle_dialog_input
            return handle_dialog_input(self.gui, event)

        # The numbered pop-up menus (travel / stable / waystone) live in
        # input_actions to hold the 500-line line
        from ui.input_actions import menu_mode_key
        _mm = menu_mode_key(self.gui, self.engine, event)
        if _mm is not None:
            return _mm

        # Menu mode (text overlay — help / character sheet / quest log)
        if self.gui.mode == "menu":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_q, pygame.K_c):
                self.gui.mode = "play"
                self.gui.overlay = None
                return True
            return False

        # Interactive inventory panel
        if self.gui.mode == "inventory":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_i):
                self.gui.mode = "play"
                return True
            if self.gui.inventory_panel is not None:
                return self.gui.inventory_panel.handle_key(event)
            return True

        # Shop panel
        if self.gui.mode == "shop":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.gui.mode = "play"
                self.gui.shop_panel = None
                return True
            if self.gui.shop_panel is not None:
                return self.gui.shop_panel.handle_key(event)
            return True

        # Spellbook panel
        if self.gui.mode == "spells":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_x):
                self.gui.mode = "play"
                return True
            if self.gui.spell_panel is not None:
                return self.gui.spell_panel.handle_key(event)
            return True

        # Crafting panel
        if self.gui.mode == "crafting":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_k):
                self.gui.mode = "play"
                return True
            if self.gui.crafting_panel is not None:
                return self.gui.crafting_panel.handle_key(event)
            return True

        # Build / terraform planner (M5)
        if self.gui.mode == "build":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.gui.mode = "play"
                return True
            if self.gui.build_planner is not None:
                return self.gui.build_planner.handle_key(event)
            return True

        if event.type != pygame.KEYDOWN:
            return False

        return self._handle_play_input(event)

    # ---- play mode ---------------------------------------------------

    def _handle_play_input(self, event) -> bool:
        k = event.key
        # SHIFT = move deliberately: RUN in the clear, careful DISENGAGE by a foe
        # (P34.9 — macOS-safe: Ctrl is grabbed by the OS for Spaces/input switch).
        mod = getattr(event, "mod", 0)
        shift = bool(mod & pygame.KMOD_SHIFT)

        if k == pygame.K_BACKQUOTE:              # ` = jump / leap forward
            return input_actions.jump(self)
        if k == pygame.K_PERIOD:                 # . = cycle pace (walk/jog/crawl)
            return input_actions.cycle_move_mode(self)
        if k == pygame.K_SEMICOLON:              # ; = a random dance / jig / taunt
            return input_actions.perform_emote(self)
        if k == pygame.K_QUOTE:                  # ' = slide (needs running momentum)
            return input_actions.slide(self)

        # Movement (SHIFT+move = run when safe, careful disengage next to a foe)
        if k in (pygame.K_w, pygame.K_UP):
            return input_actions.step(self, 0, -1, shift)
        if k in (pygame.K_s, pygame.K_DOWN):
            return input_actions.step(self, 0, 1, shift)
        if k in (pygame.K_a, pygame.K_LEFT):
            return input_actions.step(self, -1, 0, shift)
        if k in (pygame.K_d, pygame.K_RIGHT):
            return input_actions.step(self, 1, 0, shift)
        if k in _NUMPAD_MOVE:                    # 8-way: diagonals included
            dx, dy = _NUMPAD_MOVE[k]
            return input_actions.step(self, dx, dy, shift)
        if k == pygame.K_KP5:                    # wait a beat in place
            self.engine.move_player(0, 0, careful=shift)
            return True

        # Attack adjacent (SHIFT+F = shove)
        if k in (pygame.K_SPACE, pygame.K_f):
            if shift:
                from engine.tactics import shove
                shove(self.engine)
                return True
            self.engine.melee_or_shoot()
            return True

        if k == pygame.K_r:   # ranged; SHIFT+R aims
            self.engine.shoot_ranged(aimed=shift)
            return True

        if k == pygame.K_x:   # spellbook
            self.gui.show_spellbook()
            return True

        if k == pygame.K_v:   # heal; SHIFT+V: weapon action (P12.7)
            try:
                from engine.combat_depth import weapon_action
                (weapon_action(self.engine) if shift else
                 self.engine.cast_spell("heal", "me"))
            except Exception:
                pass
            return True

        if k == pygame.K_z:   # forage; SHIFT+Z: treat the pet
            if shift:
                self.engine.pet_system.feed_pet()
            else:
                self.engine.forage()
            return True

        if k == pygame.K_TAB:   # enter/exit; SHIFT forces the door
            if shift and not self.engine.current_interior:
                self.engine.force_door()
            else:
                self._handle_interact()
            return True

        # Bank deposit all (N) / withdraw all (M)
        if k in (pygame.K_n, pygame.K_m):
            try:
                if k == pygame.K_n:
                    self.engine.deposit_gold(self.engine.player.gold)
                else:
                    self.engine.withdraw_gold(
                        self.engine.bank_balance())
            except Exception:
                pass
            return True

        if k == pygame.K_l:   # look around; SHIFT+L: log detail
            if shift:
                from engine.event_filter import cycle_verbosity
                cycle_verbosity(self.engine)
            else:
                input_actions.look_around(self.engine)
            return True

        # Cycle ranged targets ([ back, ] forward) (P8.7)
        if k in (pygame.K_RIGHTBRACKET, pygame.K_LEFTBRACKET):
            self.engine.targeting.cycle(
                1 if k == pygame.K_RIGHTBRACKET else -1)
            return True

        if k == pygame.K_b:   # barter by a merchant, else the build/terraform tool
            try:
                from engine.shop import merchants_near
                near = merchants_near(self.engine, self.engine.player,
                                      radius=2.0)
            except Exception:
                near = None
            if near:
                input_actions.open_shop(self)
            else:
                self.gui.show_build_planner()
            return True

        if k == pygame.K_k:   # crafting overlay
            self.gui.show_crafting()
            return True

        if k == pygame.K_p:   # SHIFT: pray; plain: party toggle
            (self.engine.pray() if shift
             else input_actions.toggle_party(self))
            return True

        if k == pygame.K_RETURN:   # sleep / camp (P12.6)
            try:
                from engine.rest import sleep
                lines = sleep(self.engine)
                if lines:
                    self.gui.overlay = ("A New Day", lines)
                    self.gui.mode = "menu"
            except Exception:
                pass
            return True

        # single-key overlays, play-mode number keys (guard / quick-cast), and
        # the SHIFT skill verbs live in input_actions to hold the 500-line line
        from ui.input_actions import (one_key_overlay, number_key, skill_verb,
                                       grapple_verb)
        if one_key_overlay(self.gui, k):
            return True
        if number_key(self.engine, k):
            return True
        if shift and skill_verb(self.engine, k):
            return True
        if shift and grapple_verb(self.engine, k):
            return True

        # Talk to adjacent NPC
        if k == pygame.K_t:
            npc = self._find_adjacent_npc()
            if npc:
                self.gui.start_dialog(npc.id)
            else:
                self.engine.memory_manager.add_event("No one nearby to talk to.")
            return True

        # E/G: ground item beats furniture; then furniture; then pickup
        if k in (pygame.K_g, pygame.K_e):
            if shift and k == pygame.K_g:   # carry a body (P13.2)
                from engine.ransom import hoist_or_deliver
                hoist_or_deliver(self.engine)
                return True
            tn = getattr(self.engine, "teleport_network", None)   # P37.1
            if tn is not None and not self.engine.current_interior \
                    and tn.platform_at(self.engine.player.position) is not None:
                self.gui.show_teleport()
                return True
            col = getattr(self.engine, "colosseum", None)   # combat-test arena
            if col is not None and not self.engine.current_interior \
                    and col.at_entrance(self.engine.player.position):
                col.enter()                       # stage the next matchup
                return True
            # GX.5b: search out Oakvale's hidden Deepdelve stair where the
            # ground rings hollow (nothing underfoot to pick up instead)
            dd = getattr(self.engine, "deepdelve", None)
            if dd is not None and not self.engine.current_interior \
                    and dd.secret_near(self.engine.player.position) is not None:
                try:
                    underfoot = self.engine.world.get_items_at(
                        *self.engine.player.position)
                except Exception:
                    underfoot = []
                if not underfoot and dd.reveal_secret():
                    return True
            if self.engine.current_interior:
                try:
                    here = self.engine.world.get_items_at(
                        *self.engine.player.position)
                except Exception:
                    here = []
                if not here:   # furniture, else claim/repair a home (P15.7)
                    msg = self.engine.use_furniture() or self.engine.home_action()
                    if msg:
                        return True
            # P28.2d a stable: open the buy-and-ride menu (nothing underfoot)
            try:
                if not self.engine.current_interior \
                        and self.engine.at_stable() \
                        and not self.engine.world.get_items_at(
                            *self.engine.player.position):
                    self.gui.show_stable()
                    return True
            except Exception:
                pass
            # A-board: a tavern notice board — view & take posted quests
            try:
                if self.engine.quest_board_at_player() is not None \
                        and not self.engine.world.get_items_at(
                            *self.engine.player.position):
                    self.gui.show_quest_board()
                    return True
            except Exception:
                pass
            from engine.mount import try_buy_at_stable   # P15.8b mule (legacy)
            if try_buy_at_stable(self.engine):
                return True
            msg = self.engine.pickup_item()
            return True

        if k == pygame.K_h:   # quick potion
            self._use_potion()
            return True

        # Inventory overlay
        if k == pygame.K_i:
            self.gui.show_inventory()
            return True

        # Quest log
        if k == pygame.K_q:
            self.gui.show_quests()
            return True

        # Character sheet
        if k == pygame.K_c:
            self.gui.show_character_sheet()
            return True

        # Save / load
        if k == pygame.K_F5:
            path = self.engine.save_game(label="quicksave")
            self.engine.memory_manager.add_event(f"Game saved: {path}")
            return True
        if k == pygame.K_F9:
            if self.engine.load_game():
                self.engine.memory_manager.add_event("Game loaded.")
            else:
                self.engine.memory_manager.add_event("Load failed.")
            return True

        # Help
        if k in (pygame.K_F1, pygame.K_SLASH):
            self.gui.show_help()
            return True

        # Quit — ask first, never drop the game on a stray ESC
        if k == pygame.K_ESCAPE:
            self.gui.mode = "confirm_quit"
            return True

        return False

    # ---- dialog input ------------------------------------------------

    # ---- helpers -----------------------------------------------------

    def _pixel_to_tile(self, pos):
        """Map-view pixel -> world/zone tile (mirrors the renderer's
        camera math)."""
        try:
            rect = self.gui.layout["map"]
            if not rect.collidepoint(pos):
                return None
            ts = self.gui.renderer.tile_size
            engine = self.engine
            zone = None
            try:
                zone = engine.active_zone()
            except Exception:
                pass
            grid = zone if zone is not None else engine.world.map
            cols = rect.width // ts
            rows = rect.height // ts
            px, py = engine.player.position
            cam_x = max(0, min(grid.width - cols, px - cols // 2))
            cam_y = max(0, min(grid.height - rows, py - rows // 2))
            tx = cam_x + (pos[0] - rect.x) // ts
            ty = cam_y + (pos[1] - rect.y) // ts
            return (tx, ty)
        except Exception:
            return None

    def _find_adjacent_npc(self):
        from engine.presence import npc_adjacent_to_player
        for npc in self.engine.npc_manager.npcs.values():
            if npc.is_active() and \
                    npc_adjacent_to_player(self.engine, npc):
                return npc
        return None

    def _find_adjacent_enemy(self):
        px, py = self.engine.player.position
        best = None
        best_score = -1
        for npc in self.engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            d = ((npc.position[0] - px) ** 2 +
                 (npc.position[1] - py) ** 2) ** 0.5
            if d > 1.5:
                continue
            klass = getattr(npc.character_class, "value", "")
            # Prefer hostile classes
            score = 2 if klass in ("brigand", "troll", "monster") else 1
            if score > best_score:
                best_score = score
                best = npc
        return best

    def _use_potion(self):
        for it in self.engine.player.inventory:
            name = it.name if hasattr(it, "name") else str(it)
            if "potion" in name.lower():
                self.engine.use_item(name)
                return
        self.engine.memory_manager.add_event("No potions in inventory.")

    def _handle_interact(self) -> None:
        """Smart 'Tab' key — enter/exit building, or descend into a cave."""
        try:
            # On Tutorial Island, TAB only departs at the boat
            tm = getattr(self.engine, "tutorial_manager", None)
            if tm is not None and tm.active:
                msg = tm.try_depart()
                self.engine.memory_manager.add_event(msg)
                return
            if self.engine.current_interior:
                self.engine.exit_building()
                return
            if self.engine.current_dungeon:
                self.engine.exit_dungeon()
                return
            # Cave?
            from world.world_map import TerrainType
            x, y = self.engine.player.position
            if self.engine.world.map.get_terrain_at(x, y) == TerrainType.CAVE:
                self.engine.enter_dungeon()
                return
            # Building?
            loc = self.engine.world.get_location_at(x, y)
            if loc and loc.name in self.engine.interiors:
                self.engine.enter_building()
                return
            self.engine.memory_manager.add_event(
                "There's nothing to enter here.")
        except Exception:
            pass
