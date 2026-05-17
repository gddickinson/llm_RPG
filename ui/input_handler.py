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

        # Dialog typing mode -----------------------------------------------
        if self.gui.mode == "dialog":
            return self._handle_dialog_input(event)

        # Menu mode (inventory / quest log) --------------------------------
        if self.gui.mode == "menu":
            if event.type == pygame.KEYDOWN and event.key in \
                    (pygame.K_ESCAPE, pygame.K_i, pygame.K_q, pygame.K_c, pygame.K_m):
                self.gui.mode = "play"
                self.gui.overlay = None
                return True
            return False

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
                msg = self.engine.use_item(name)
                return
        self.engine.memory_manager.add_event("No potions in inventory.")
