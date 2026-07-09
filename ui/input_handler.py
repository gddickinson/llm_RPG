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

        # Dialog typing mode -----------------------------------------------
        if self.gui.mode == "dialog":
            return self._handle_dialog_input(event)

        # Travel menu: 1-9 teleports, Esc cancels
        if self.gui.mode == "travel":
            if event.type != pygame.KEYDOWN:
                return True
            if event.key in (pygame.K_ESCAPE, pygame.K_u):
                self.gui.mode = "play"
                self.gui.overlay = None
                return True
            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                try:
                    self.engine.travel_system.teleport(idx)
                except Exception:
                    pass
                self.gui.mode = "play"
                self.gui.overlay = None
                return True
            return True

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

        # Crafting panel
        if self.gui.mode == "crafting":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_k):
                self.gui.mode = "play"
                return True
            if self.gui.crafting_panel is not None:
                return self.gui.crafting_panel.handle_key(event)
            return True

        if event.type != pygame.KEYDOWN:
            return False

        return self._handle_play_input(event)

    # ---- play mode ---------------------------------------------------

    def _handle_play_input(self, event) -> bool:
        k = event.key
        # Movement
        if k in (pygame.K_w, pygame.K_UP):
            self.engine.move_player(0, -1)
            return True
        if k in (pygame.K_s, pygame.K_DOWN):
            self.engine.move_player(0, 1)
            return True
        if k in (pygame.K_a, pygame.K_LEFT):
            self.engine.move_player(-1, 0)
            return True
        if k in (pygame.K_d, pygame.K_RIGHT):
            self.engine.move_player(1, 0)
            return True

        # Attack adjacent
        if k in (pygame.K_SPACE, pygame.K_f):
            target = self._find_adjacent_enemy()
            if target:
                self.engine.attack_character(target.name)
            else:
                self.engine.memory_manager.add_event("No enemy adjacent.")
            return True

        # Ranged attack (R)
        if k == pygame.K_r:
            self.engine.shoot_ranged()
            return True

        # Cast quick fireball (X)
        if k == pygame.K_x:
            try:
                self.engine.cast_spell("fireball")
            except Exception:
                pass
            return True

        # Quick heal (V)
        if k == pygame.K_v:
            try:
                self.engine.cast_spell("heal", "me")
            except Exception:
                pass
            return True

        # Forage (Z)
        if k == pygame.K_z:
            try:
                self.engine.forage()
            except Exception:
                pass
            return True

        # Enter / exit building or dungeon (Tab)
        if k == pygame.K_TAB:
            self._handle_interact()
            return True

        # Bank deposit all (N) / withdraw all (M)
        if k == pygame.K_n:
            try:
                self.engine.deposit_gold(self.engine.player.gold)
            except Exception:
                pass
            return True
        if k == pygame.K_m:
            try:
                self.engine.withdraw_gold(self.engine.bank_balance())
            except Exception:
                pass
            return True

        # Look around (L) — log the visible description
        if k == pygame.K_l:
            self._look_around()
            return True

        # Open shop with adjacent merchant (B for barter — S is taken by
        # move-down, which shadowed the old binding and made shops unreachable)
        if k == pygame.K_b:
            self._open_shop()
            return True

        # Crafting overlay (K)
        if k == pygame.K_k:
            self.gui.show_crafting()
            return True

        # Party: recruit / dismiss adjacent NPC (P)
        if k == pygame.K_p:
            self._toggle_party()
            return True

        # Collection log (O)
        if k == pygame.K_o:
            self.gui.show_collection_log()
            return True

        # Achievement diaries (J)
        if k == pygame.K_j:
            self.gui.show_diaries()
            return True

        # Travel menu (U)
        if k == pygame.K_u:
            self.gui.show_travel()
            return True

        # Topic journal (Y)
        if k == pygame.K_y:
            self.gui.show_topics()
            return True

        # Talk to adjacent NPC
        if k == pygame.K_t:
            npc = self._find_adjacent_npc()
            if npc:
                self.gui.start_dialog(npc.id)
            else:
                self.engine.memory_manager.add_event("No one nearby to talk to.")
            return True

        # Pickup
        if k in (pygame.K_g, pygame.K_e):
            msg = self.engine.pickup_item()
            return True

        # Use item (potion auto-select)
        if k == pygame.K_h:
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

        # Quit
        if k == pygame.K_ESCAPE:
            self.engine.end_game()
            self.gui.running = False
            return True

        return False

    # ---- dialog input ------------------------------------------------

    def _handle_dialog_input(self, event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_ESCAPE:
            self.gui.end_dialog()
            return True
        if event.key == pygame.K_RETURN:
            self.gui.submit_dialog()
            return True
        if event.key == pygame.K_BACKSPACE:
            self.gui.dialog_input = self.gui.dialog_input[:-1]
            return True
        # Quest accept / turn-in hotkeys (1-9) -------------------------
        # Only trigger if the dialog input field is empty (otherwise user
        # is typing).
        if not self.gui.dialog_input and pygame.K_1 <= event.key <= pygame.K_9:
            idx = event.key - pygame.K_1  # 0-based
            self.gui.dialog_quest_action(idx)
            return True
        # Typing
        ch = event.unicode
        if ch and ch.isprintable():
            self.gui.dialog_input += ch
            return True
        return False

    # ---- helpers -----------------------------------------------------

    def _find_adjacent_npc(self):
        px, py = self.engine.player.position
        for npc in self.engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            d = ((npc.position[0] - px) ** 2 +
                 (npc.position[1] - py) ** 2) ** 0.5
            if d <= 1.5:
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

    def _look_around(self) -> None:
        try:
            x, y = self.engine.player.position
            visible = self.engine.world.map.get_visible_description(x, y)
            for line in visible.split("\n"):
                if line.strip():
                    self.engine.memory_manager.add_event(line)
        except Exception:
            pass

    def _toggle_party(self) -> None:
        """P key — dismiss an adjacent party member, or try to recruit."""
        try:
            npc = self._find_adjacent_npc()
            if npc is None:
                self.engine.memory_manager.add_event(
                    "No one nearby to recruit.")
                return
            if npc.id in self.engine.companion_manager.party:
                self.engine.dismiss_companion(npc.id)
                return
            msg = self.engine.recruit(npc.id)
            # Success is logged by the manager; log refusals too
            if "joins your party" not in msg:
                self.engine.memory_manager.add_event(msg)
        except Exception:
            pass

    def _open_shop(self) -> None:
        try:
            from engine.shop import merchants_near
            merchants = merchants_near(self.engine, self.engine.player,
                                       radius=2.0)
            if not merchants:
                self.engine.memory_manager.add_event(
                    "There's no merchant nearby.")
                return
            self.gui.show_shop(merchants[0])
        except Exception:
            pass
