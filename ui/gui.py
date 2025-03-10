"""
GUI module for LLM-RPG using Pygame
Provides a graphical user interface for the game
"""

import pygame
import pygame_gui
import logging
import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple
import random

import config
from characters.character_types import CharacterClass, CharacterRace

logger = logging.getLogger("llm_rpg.gui")

# Define colors
COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (100, 100, 100),
    "light_gray": (200, 200, 200),
    "dark_gray": (50, 50, 50),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "brown": (165, 42, 42),
    "grass": (34, 139, 34),
    "water": (65, 105, 225),
    "mountain": (139, 137, 137),
    "forest": (0, 100, 0),
    "road": (210, 180, 140),
    "building": (139, 69, 19)
}

# Define terrain colors
TERRAIN_COLORS = {
    "grass": COLORS["grass"],
    "forest": COLORS["forest"],
    "mountain": COLORS["mountain"],
    "water": COLORS["water"],
    "road": COLORS["road"],
    "building": COLORS["building"],
    "cave": COLORS["dark_gray"]
}


class RenderOptimizer:
    """Helper class to optimize rendering performance"""

    def __init__(self, fps_limit=60):
        self.last_render_time = time.time()
        self.fps_limit = fps_limit
        self.frame_interval = 1.0 / fps_limit
        self.tile_cache = {}  # Cache for rendered tiles

    def should_render(self):
        """Check if we should render a new frame based on FPS limit"""
        current_time = time.time()
        elapsed = current_time - self.last_render_time

        if elapsed >= self.frame_interval:
            self.last_render_time = current_time
            return True
        return False

    def get_cached_tile(self, key, generator_func):
        """Get a tile from cache or generate it if not cached"""
        if key not in self.tile_cache:
            self.tile_cache[key] = generator_func()
        return self.tile_cache[key]

class GameGUI:
    """Graphical user interface for the game using Pygame"""

    def __init__(self, engine, width=1200, height=800):
        """Initialize the GUI with a reference to the game engine"""
        self.engine = engine
        self.width = width
        self.height = height
        self.running = False
        self.current_tab = "map"  # Options: map, character, inventory, settings
        self.dialog_active = False
        self.dialog_text = ""
        self.dialog_target = None
        self.message_log = []
        self.max_messages = 15
        self.tile_size = 32  # Size of each map tile in pixels

        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("LLM-RPG")

        # Initialize UI manager
        self.ui_manager = pygame_gui.UIManager((width, height))

        # Load assets
        self.load_assets()

        # Create UI elements
        self.setup_ui()

        logger.info("GUI initialized")

    def load_assets(self):
        """Load game assets with enhanced character types"""
        # Create a fonts directory
        fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        os.makedirs(fonts_dir, exist_ok=True)

        # Set default font
        self.font = pygame.font.SysFont('Arial', 16)
        self.font_bold = pygame.font.SysFont('Arial', 16, bold=True)
        self.font_large = pygame.font.SysFont('Arial', 24)
        self.font_title = pygame.font.SysFont('Arial', 32, bold=True)

        # Load tile images (or create them if not available)
        self.tiles = {}
        self.create_default_tiles()

    def create_default_tiles(self):
        """Create default tile images with enhanced character types"""
        # Player tile
        player_tile = pygame.Surface((self.tile_size, self.tile_size))
        player_tile.fill(COLORS["cyan"])
        self.tiles["player"] = player_tile

        # NPC tiles by class
        class_colors = {
            CharacterClass.WARRIOR: COLORS["red"],
            CharacterClass.WIZARD: COLORS["magenta"],
            CharacterClass.ROGUE: COLORS["yellow"],
            CharacterClass.CLERIC: COLORS["blue"],
            CharacterClass.BARD: COLORS["cyan"],
            CharacterClass.MERCHANT: COLORS["brown"],
            CharacterClass.GUARD: COLORS["gray"],
            CharacterClass.TROLL: (0, 100, 0),  # Dark green for trolls
            CharacterClass.BRIGAND: (139, 0, 0),  # Dark red for brigands
            CharacterClass.MONSTER: (128, 0, 128)  # Purple for monsters
        }

        # Create tiles for all character classes
        for char_class in CharacterClass:
            npc_tile = pygame.Surface((self.tile_size, self.tile_size))

            # Use specific color if defined, otherwise default to magenta
            color = class_colors.get(char_class, COLORS["magenta"])
            npc_tile.fill(color)

            self.tiles[char_class.value] = npc_tile

        # Special tile for troll brigand
        troll_tile = pygame.Surface((self.tile_size, self.tile_size))
        troll_tile.fill((0, 100, 0))  # Dark green
        self.tiles["troll_brigand"] = troll_tile

        # Terrain tiles
        for terrain, color in TERRAIN_COLORS.items():
            terrain_tile = pygame.Surface((self.tile_size, self.tile_size))
            terrain_tile.fill(color)
            self.tiles[terrain] = terrain_tile

        # Item tiles
        item_tile = pygame.Surface((self.tile_size // 2, self.tile_size // 2))
        item_tile.fill(COLORS["yellow"])
        self.tiles["item"] = item_tile

    def setup_ui(self):
        """Set up the user interface elements with corrected dialog input handling"""
        # Tab buttons
        button_width = 120
        button_height = 40
        spacing = 10
        button_y = 10

        self.tab_buttons = {}
        tabs = ["Map", "Character", "Inventory", "Settings"]

        for i, tab in enumerate(tabs):
            button_x = 10 + (button_width + spacing) * i
            self.tab_buttons[tab.lower()] = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(button_x, button_y, button_width, button_height),
                text=tab,
                manager=self.ui_manager
            )

        # Message log panel
        log_height = 200
        self.message_panel = pygame.Rect(10, self.height - log_height - 10, self.width - 20, log_height)

        # Dialog input (hidden initially)
        input_height = 40
        self.dialog_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(10, self.height - log_height - input_height - 20,
                                     self.width - button_width - 30, input_height),
            manager=self.ui_manager
        )
        self.dialog_input.hide()

        # Submit dialog button
        self.submit_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(self.width - button_width - 10,
                                     self.height - log_height - input_height - 20,
                                     button_width, input_height),
            text="Submit",
            manager=self.ui_manager
        )
        self.submit_button.hide()

        # Make the background of the text entry more visible
        dialog_bg_color = self.ui_manager.get_theme().get_colour('text_entry_line', 'dark_bg')
        if not dialog_bg_color:
            dialog_bg_color = pygame.Color('#505050')

        # Set the dialog input to be always on top
        self.dialog_input.layer_thickness = 5
        self.submit_button.layer_thickness = 5

         # Add combat buttons
        combat_panel_height = 40
        self.combat_panel = pygame.Rect(10, self.height - self.message_panel.height - combat_panel_height - 20,
                                        self.width - 20, combat_panel_height)

        # Define combat action buttons
        button_width = 100
        button_height = 30
        button_spacing = 10

        self.combat_buttons = {}
        combat_actions = ["Attack", "Use Item", "Flee"]

        for i, action in enumerate(combat_actions):
            button_x = self.combat_panel.x + i * (button_width + button_spacing)
            button_y = self.combat_panel.y + (combat_panel_height - button_height) // 2

            self.combat_buttons[action.lower()] = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(button_x, button_y, button_width, button_height),
                text=action,
                manager=self.ui_manager
            )

        # Hide combat buttons initially
        self.show_combat_ui(False)


    def start(self):
        """Start the GUI and game"""
        self.running = True
        self.engine.start_game()

        # Set initial UI state
        self.add_message("Welcome to LLM-RPG!")
        self.add_message("Use the tabs above to navigate. Press WASD or arrow keys to move.")
        self.add_message("Press T to talk to nearby NPCs.")

        self.main_loop()

    def show_combat_ui(self, show=True):
        """Show or hide the combat UI"""
        for button in self.combat_buttons.values():
            if show:
                button.show()
            else:
                button.hide()

    def handle_key_press(self, key):
        """Handle key press events with enhanced combat commands"""
        # Movement
        if key == pygame.K_w or key == pygame.K_UP:
            self.move_player(0, -1)
        elif key == pygame.K_s or key == pygame.K_DOWN:
            self.move_player(0, 1)
        elif key == pygame.K_a or key == pygame.K_LEFT:
            self.move_player(-1, 0)
        elif key == pygame.K_d or key == pygame.K_RIGHT:
            self.move_player(1, 0)

        # Combat keys
        elif key == pygame.K_SPACE:
            self.attack_nearest_enemy()  # Attack only hostile NPCs
        elif key == pygame.K_f:
            self.attack_any_character()  # Can attack any character

        # Other commands
        elif key == pygame.K_t:
            self.talk_to_npc()
        elif key == pygame.K_i:
            self.current_tab = "inventory"
        elif key == pygame.K_c:
            self.current_tab = "character"
        elif key == pygame.K_m:
            self.current_tab = "map"
        elif key == pygame.K_ESCAPE:
            if self.dialog_active:
                self.cancel_dialog()
            else:
                self.current_tab = "settings"




    def attack_nearest_enemy(self):
        """Attack the nearest enemy NPC"""
        player = self.engine.player
        player_x, player_y = player.position

        # Find the nearest hostile NPC
        nearest_enemy = None
        nearest_distance = float('inf')

        for pos, char in self.engine.world.map.characters.items():
            if char.id == player.id:  # Skip player
                continue

            # Check if NPC is hostile
            relation = char.get_relationship(player.id)
            if relation > -50:  # Not hostile
                continue

            # Calculate distance
            char_x, char_y = pos
            distance = ((player_x - char_x) ** 2 + (player_y - char_y) ** 2) ** 0.5

            if distance <= 1.5 and distance < nearest_distance:  # Within attack range
                nearest_enemy = char
                nearest_distance = distance

        if nearest_enemy:
            self._perform_attack(nearest_enemy)
        else:
            self.add_message("There are no enemies within attack range.")

    def attack_any_character(self):
        """Let the player attack any nearby character (friendly or hostile)"""
        player = self.engine.player
        player_x, player_y = player.position

        # Find all nearby characters
        nearby_chars = []

        for pos, char in self.engine.world.map.characters.items():
            if char.id == player.id:  # Skip player
                continue

            # Calculate distance
            char_x, char_y = pos
            distance = ((player_x - char_x) ** 2 + (player_y - char_y) ** 2) ** 0.5

            if distance <= 1.5:  # Within attack range
                nearby_chars.append(char)

        if not nearby_chars:
            self.add_message("There are no characters within attack range.")
            return

        # If only one character is nearby, attack them directly
        if len(nearby_chars) == 1:
            target = nearby_chars[0]
            self._perform_attack(target)
            return

        # If multiple characters are nearby, show selection dialog
        self._show_target_selection(nearby_chars, "Attack")


    def _perform_attack(self, target):
        """Perform the actual attack on a target with improved defeat handling"""
        # Calculate hit chance and damage
        hit_chance = 0.7  # 70% base chance to hit
        damage = random.randint(5, 10)  # Random damage

        # Roll for hit
        if random.random() <= hit_chance:
            # Hit
            target.take_damage(damage)
            self.add_message(f"You attack {target.name} for {damage} damage!")

            # Always make relationship worse when attacking
            target.modify_relationship(self.engine.player.id, -20)

            # Check if enemy defeated
            if not target.is_alive():
                # Properly mark as defeated
                target.defeat()

                self.add_message(f"You have defeated {target.name}!")

                # Store position before removal
                body_position = target.position

                # Store last position in character for potential revival
                target.last_position = body_position

                # Remove from map
                self.engine.world.map.remove_character(target)

                # Drop items if applicable
                if target.inventory:
                    item = random.choice(target.inventory)
                    self.engine.world.add_item_to_ground(item, body_position[0], body_position[1])
                    target.inventory.remove(item)
                    self.add_message(f"{target.name} drops {item}!")

                # Create a "body" item
                body_item = f"{target.name}'s body"
                self.engine.world.add_item_to_ground(body_item, body_position[0], body_position[1])
            else:
                # Target may counterattack if still alive
                self.engine.process_npc_turns()
        else:
            # Miss
            self.add_message(f"You attack {target.name} but miss!")

            # Target may still counterattack
            self.engine.process_npc_turns()


    def _show_target_selection(self, targets, action_type="Attack"):
        """Show a dialog to select which character to target"""
        # Create a modal dialog
        dialog_rect = pygame.Rect(
            (self.width - 400) // 2,
            (self.height - 300) // 2,
            400, 300
        )

        self.target_selection_dialog = pygame_gui.elements.UIWindow(
            rect=dialog_rect,
            manager=self.ui_manager,
            window_display_title=f"Select Target to {action_type}"
        )

        # Container for buttons
        container_rect = pygame.Rect(
            10, 10,
            dialog_rect.width - 20,
            dialog_rect.height - 50
        )
        button_container = pygame_gui.elements.UIPanel(
            relative_rect=container_rect,
            manager=self.ui_manager,
            container=self.target_selection_dialog
        )

        # Add a button for each target
        self.target_buttons = {}
        button_height = 40
        for i, target in enumerate(targets):
            button_rect = pygame.Rect(
                10, 10 + i * (button_height + 5),
                container_rect.width - 20, button_height
            )

            # Create button with target information
            relation = target.get_relationship(self.engine.player.id)
            relation_text = "Hostile" if relation <= -50 else "Neutral" if -50 < relation < 50 else "Friendly"
            health_pct = int(100 * target.hp / target.max_hp)

            button_text = f"{target.name} - {relation_text} - HP: {target.hp}/{target.max_hp} ({health_pct}%)"

            button = pygame_gui.elements.UIButton(
                relative_rect=button_rect,
                text=button_text,
                manager=self.ui_manager,
                container=button_container
            )

            self.target_buttons[button] = target

        # Store what we're doing with the selected target
        self.target_selection_action = action_type.lower()






    def move_player(self, dx, dy):
        """Move the player character"""
        result = self.engine.move_player(dx, dy)
        if not result:
            self.add_message("You can't go that way.")
        else:
            # Get current location
            game_state = self.engine.get_game_state()
            location = game_state.get("location")
            if location:
                self.add_message(f"You are now in {location.name}.")
            else:
                self.add_message("You move through the wilderness.")


    def talk_to_npc(self):
        """Talk to a nearby NPC"""
        # Get nearby NPCs
        player_x, player_y = self.engine.player.position
        nearby_npcs = []

        for pos, npc in self.engine.world.map.characters.items():
            if npc.id != self.engine.player.id:  # Skip player
                npc_x, npc_y = pos
                distance = ((player_x - npc_x) ** 2 + (player_y - npc_y) ** 2) ** 0.5
                if distance <= 1.5:  # Adjacent or diagonal
                    nearby_npcs.append(npc)

        if not nearby_npcs:
            self.add_message("There's nobody nearby to talk to.")
            return

        # If just one NPC, talk to them
        if len(nearby_npcs) == 1:
            npc = nearby_npcs[0]
            self.start_dialog(npc.id)
        else:
            # Multiple NPCs, let player choose
            self.add_message("Nearby characters:")
            for i, npc in enumerate(nearby_npcs):
                self.add_message(f"{i+1}. {npc.name} ({npc.character_class.value})")

            # For now, just talk to the first one
            npc = nearby_npcs[0]
            self.start_dialog(npc.id)

    def start_dialog(self, npc_id):
        """Start a dialog with an NPC"""
        npc = self.engine.npc_manager.get_npc(npc_id)
        if not npc:
            return

        # Get initial greeting
        response = self.engine.interact_with_npc(npc_id)
        self.add_message(f"{npc.name}: {response}")

        # Activate dialog mode
        self.dialog_active = True
        self.dialog_target = npc_id
        self.dialog_input.show()
        self.submit_button.show()
        self.add_message("Type your response and press Enter:")

        # Clear any existing input
        self.dialog_input.set_text("")

        # Make sure the input has focus
        self.dialog_input.focus()

    def submit_dialog(self):
        """Submit the current dialog to the NPC"""
        if not self.dialog_active or not self.dialog_target:
            return

        message = self.dialog_input.get_text()
        if not message:
            return

        # Clear input field
        self.dialog_input.set_text("")

        # Show waiting status
        self.dialog_status = "Waiting for response..."
        self.add_message(self.dialog_status)

        # Need to render to show status
        self.render()

        # Get response from NPC
        npc = self.engine.npc_manager.get_npc(self.dialog_target)
        response = self.engine.interact_with_npc(self.dialog_target, message)

        # Clear waiting status
        self.dialog_status = ""

        # Display messages
        self.add_message(f"You: {message}")
        self.add_message(f"{npc.name}: {response}")

        # Keep focus on the input field for continued conversation
        self.dialog_input.focus()

    def cancel_dialog(self):
        """Cancel the current dialog"""
        self.dialog_active = False
        self.dialog_target = None
        self.dialog_input.hide()
        self.submit_button.hide()
        self.add_message("Dialog canceled.")

    def add_message(self, message):
        """Add a message to the message log"""
        self.message_log.append(message)
        # Trim log if needed
        if len(self.message_log) > self.max_messages:
            self.message_log = self.message_log[-self.max_messages:]

    def render(self):
        """Render the game screen"""
        # Clear screen
        self.screen.fill(COLORS["black"])

        # Render current tab content
        if self.current_tab == "map":
            self.render_map_tab()
        elif self.current_tab == "character":
            self.render_character_tab()
        elif self.current_tab == "inventory":
            self.render_inventory_tab()
        elif self.current_tab == "settings":
            self.render_settings_tab()

        # Render message log
        self.render_message_log()

        # Render UI elements
        self.ui_manager.draw_ui(self.screen)

        # Update display
        pygame.display.flip()


    def _check_player_in_combat(self):
        """Check if the player is in combat with any nearby NPCs"""
        player = self.engine.player
        player_x, player_y = player.position

        # Check if any hostile NPCs are nearby
        for pos, char in self.engine.world.map.characters.items():
            if char.id == player.id:  # Skip player
                continue

            # Check distance
            char_x, char_y = pos
            distance = ((player_x - char_x) ** 2 + (player_y - char_y) ** 2) ** 0.5

            if distance <= 2.0:  # Within combat range
                # Check if NPC is hostile (has negative relationship)
                relation = char.get_relationship(player.id)
                if relation <= -50:
                    return True

        return False


    def render_character_tab(self):
        """Render the character tab"""
        player = self.engine.player

        # Draw character background
        char_bg = pygame.Rect(20, 70, self.width - 40, self.height - 300)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], char_bg)

        # Draw character title
        title_text = self.font_title.render("Character Sheet", True, COLORS["white"])
        self.screen.blit(title_text, (30, 80))

        # Draw character info
        char_x = 50
        char_y = 130
        line_height = 30

        # Basic info
        self.screen.blit(self.font_large.render(f"Name: {player.name}", True, COLORS["white"]), (char_x, char_y))
        self.screen.blit(self.font_large.render(f"Race: {player.race.value}", True, COLORS["white"]), (char_x, char_y + line_height))
        self.screen.blit(self.font_large.render(f"Class: {player.character_class.value}", True, COLORS["white"]), (char_x, char_y + line_height * 2))
        self.screen.blit(self.font_large.render(f"Level: {player.level}", True, COLORS["white"]), (char_x, char_y + line_height * 3))

        # HP bar
        hp_bar_width = 200
        hp_bar_height = 20
        hp_bg = pygame.Rect(char_x, char_y + line_height * 4, hp_bar_width, hp_bar_height)
        hp_fill = pygame.Rect(char_x, char_y + line_height * 4, int(hp_bar_width * (player.hp / player.max_hp)), hp_bar_height)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], hp_bg)
        pygame.draw.rect(self.screen, COLORS["red"], hp_fill)
        hp_text = self.font.render(f"HP: {player.hp}/{player.max_hp}", True, COLORS["white"])
        self.screen.blit(hp_text, (char_x + 10, char_y + line_height * 4 + 2))

        # Stats
        stats_x = 400
        stats_y = 130

        self.screen.blit(self.font_large.render("Stats", True, COLORS["white"]), (stats_x, stats_y))
        self.screen.blit(self.font.render(f"Strength: {player.strength} ({player.get_stat_modifier('strength'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height))
        self.screen.blit(self.font.render(f"Dexterity: {player.dexterity} ({player.get_stat_modifier('dexterity'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height * 2))
        self.screen.blit(self.font.render(f"Constitution: {player.constitution} ({player.get_stat_modifier('constitution'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height * 3))
        self.screen.blit(self.font.render(f"Intelligence: {player.intelligence} ({player.get_stat_modifier('intelligence'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height * 4))
        self.screen.blit(self.font.render(f"Wisdom: {player.wisdom} ({player.get_stat_modifier('wisdom'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height * 5))
        self.screen.blit(self.font.render(f"Charisma: {player.charisma} ({player.get_stat_modifier('charisma'):+d})", True, COLORS["white"]), (stats_x, stats_y + line_height * 6))

        # Goals
        goals_x = 50
        goals_y = 280

        self.screen.blit(self.font_large.render("Goals", True, COLORS["white"]), (goals_x, goals_y))
        for i, goal in enumerate(player.goals):
            self.screen.blit(self.font.render(f"• {goal}", True, COLORS["white"]), (goals_x, goals_y + line_height * (i + 1)))

    def render_inventory_tab(self):
        """Render the inventory tab"""
        player = self.engine.player

        # Draw inventory background
        inv_bg = pygame.Rect(20, 70, self.width - 40, self.height - 300)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], inv_bg)

        # Draw inventory title
        title_text = self.font_title.render("Inventory", True, COLORS["white"])
        self.screen.blit(title_text, (30, 80))

        # Draw gold
        gold_text = self.font_large.render(f"Gold: {player.gold}", True, COLORS["yellow"])
        self.screen.blit(gold_text, (30, 130))

        # Draw items
        item_x = 50
        item_y = 180
        line_height = 30

        if not player.inventory:
            self.screen.blit(self.font.render("Your inventory is empty.", True, COLORS["white"]), (item_x, item_y))
        else:
            for i, item in enumerate(player.inventory):
                item_name = item.name if hasattr(item, "name") else str(item)
                self.screen.blit(self.font.render(f"• {item_name}", True, COLORS["white"]), (item_x, item_y + line_height * i))

    def render_settings_tab(self):
        """Render the settings tab"""
        # Draw settings background
        settings_bg = pygame.Rect(20, 70, self.width - 40, self.height - 300)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], settings_bg)

        # Draw settings title
        title_text = self.font_title.render("Settings", True, COLORS["white"])
        self.screen.blit(title_text, (30, 80))

        # Draw settings content
        settings_x = 50
        settings_y = 130
        line_height = 30

        self.screen.blit(self.font_large.render("Game Controls:", True, COLORS["white"]), (settings_x, settings_y))
        controls = [
            "WASD or Arrow Keys: Move",
            "T: Talk to NPCs",
            "I: Open Inventory",
            "C: View Character Sheet",
            "M: View Map",
            "ESC: Settings / Cancel Dialog"
        ]

        for i, control in enumerate(controls):
            self.screen.blit(self.font.render(control, True, COLORS["white"]), (settings_x, settings_y + line_height * (i + 1)))

        # Game info
        info_x = 400
        info_y = 130

        self.screen.blit(self.font_large.render("Game Info:", True, COLORS["white"]), (info_x, info_y))
        self.screen.blit(self.font.render(f"LLM Model: {self.engine.llm_interface.model_name}", True, COLORS["white"]), (info_x, info_y + line_height))
        self.screen.blit(self.font.render(f"Game Time: {self.engine.world.get_formatted_time()}", True, COLORS["white"]), (info_x, info_y + line_height * 2))
        self.screen.blit(self.font.render(f"Turn: {self.engine.turn_counter}", True, COLORS["white"]), (info_x, info_y + line_height * 3))

    def render_message_log(self):
        """Render the message log"""
        # Draw message panel background
        pygame.draw.rect(self.screen, COLORS["dark_gray"], self.message_panel)
        pygame.draw.rect(self.screen, COLORS["gray"], self.message_panel, 2)  # Border

        # Draw messages
        message_x = self.message_panel.x + 10
        message_y = self.message_panel.y + 10
        line_height = 20

        for i, message in enumerate(self.message_log):
            # Check if we're out of space
            if message_y + i * line_height >= self.message_panel.bottom - line_height:
                break

            self.screen.blit(self.font.render(message, True, COLORS["white"]), (message_x, message_y + i * line_height))

    def shutdown(self):
        """Shutdown the GUI"""
        self.running = False
        pygame.quit()
        logger.info("GUI shutdown")



    def main_loop(self):
        """Optimized main game loop with better timing"""
        clock = pygame.time.Clock()

        # Initialize render optimizer
        self.render_optimizer = RenderOptimizer(fps_limit=60)

        # Track framerate for debugging
        frame_count = 0
        frame_timer = time.time()

        # Dialog status message
        self.dialog_status = ""

        while self.running:
            # Limit frame rate while still processing events
            time_delta = clock.tick(60) / 1000.0

            # Process events
            for event in pygame.event.get():
                # Quit event
                if event.type == pygame.QUIT:
                    self.running = False

                # Process UI events first
                self.ui_manager.process_events(event)

                # Handle UI button events
                if event.type == pygame.USEREVENT:
                    if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                        # Check if it's a target selection button
                        if hasattr(self, 'target_buttons') and event.ui_element in self.target_buttons:
                            target = self.target_buttons[event.ui_element]

                            # Close the dialog
                            if hasattr(self, 'target_selection_dialog'):
                                self.target_selection_dialog.kill()
                                delattr(self, 'target_selection_dialog')
                                delattr(self, 'target_buttons')

                            # Perform the selected action
                            if self.target_selection_action == "attack":
                                self._perform_attack(target)

                # Key events - only process if not typing in dialog
                if event.type == pygame.KEYDOWN:
                    # Always handle ESC key for dialog cancelation
                    if event.key == pygame.K_ESCAPE:
                        if self.dialog_active:
                            self.cancel_dialog()
                        else:
                            self.current_tab = "settings"
                    # Enter key for dialog submission
                    elif event.key == pygame.K_RETURN and self.dialog_active:
                        self.submit_dialog()
                    # Only handle other keys if not in dialog mode or if dialog input doesn't have focus
                    elif not self.dialog_active:
                        self.handle_key_press(event.key)

                # Check for button clicks
                if event.type == pygame.USEREVENT:
                    if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                        # Tab buttons
                        for tab, button in self.tab_buttons.items():
                            if event.ui_element == button:
                                self.current_tab = tab

                        # Submit dialog button
                        if event.ui_element == self.submit_button:
                            self.submit_dialog()

            # Update game state (use async processing)
            self.engine.process_npc_turns_async()

            # Update UI manager
            self.ui_manager.update(time_delta)

            # Only render at the configured frame rate
            if self.render_optimizer.should_render():
                self.render()
                frame_count += 1

            # Calculate and log FPS every second
            if time.time() - frame_timer >= 1.0:
                fps = frame_count / (time.time() - frame_timer)
                if frame_count > 0:
                    logger.debug(f"FPS: {fps:.1f}")
                frame_count = 0
                frame_timer = time.time()




    def update(self):
        """Update the UI based on game state"""
        # Force a character position refresh for the next render
        self._refresh_character_positions()

        # Only render if needed
        if hasattr(self, 'render_optimizer'):
            if self.render_optimizer.should_render():
                self.render()
        else:
            self.render()

    def _refresh_character_positions(self):
        """Refresh character positions from the game engine"""
        # This method ensures we're always using the latest character positions
        # Log all character positions for debugging
        if hasattr(self.engine, 'world') and hasattr(self.engine.world, 'map'):
            character_positions = {}
            for pos, char in self.engine.world.map.characters.items():
                character_positions[char.name] = pos

                # Verify that the character position matches what's in the character object
                if char.position != pos:
                    logger.warning(f"Position mismatch for {char.name}: Map has {pos}, character has {char.position}")
                    # Force update of character position
                    char.position = pos

            # Log all positions
            logger.debug(f"Character positions refreshed: {character_positions}")

    def render_map_tab(self):
        """Render the map tab with enhanced visualization for items and combat"""
        # Get game state
        game_state = self.engine.get_game_state()

        # Get player position
        player_pos = self.engine.player.position

        # Calculate visible area
        visibility_range = config.DEFAULT_VISIBILITY_RANGE
        view_width = visibility_range * 2 + 1
        view_height = visibility_range * 2 + 1

        # Calculate map display position (centered on screen)
        map_x = (self.width - view_width * self.tile_size) // 2
        map_y = (self.height - view_height * self.tile_size - 250) // 2 + 70  # Offset for tabs and message log

        # Draw map background
        map_bg = pygame.Rect(map_x - 10, map_y - 10,
                             view_width * self.tile_size + 20,
                             view_height * self.tile_size + 20)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], map_bg)

        # Draw map title
        location = game_state.get("location")
        location_name = location.name if location else "Wilderness"
        title_text = self.font_large.render(f"Location: {location_name}", True, COLORS["white"])
        self.screen.blit(title_text, (map_x, map_y - 40))

        # Draw map
        for y_offset in range(-visibility_range, visibility_range + 1):
            for x_offset in range(-visibility_range, visibility_range + 1):
                # Calculate world coordinates
                world_x = player_pos[0] + x_offset
                world_y = player_pos[1] + y_offset

                # Check if within world bounds
                if (0 <= world_x < self.engine.world.map.width and
                    0 <= world_y < self.engine.world.map.height):

                    # Calculate distance from player
                    distance = ((x_offset) ** 2 + (y_offset) ** 2) ** 0.5

                    # Only draw if within visibility range
                    if distance <= visibility_range:
                        # Calculate screen coordinates
                        screen_x = map_x + (x_offset + visibility_range) * self.tile_size
                        screen_y = map_y + (y_offset + visibility_range) * self.tile_size

                        # Draw terrain
                        terrain = self.engine.world.map.get_terrain_at(world_x, world_y)
                        terrain_tile = self.tiles.get(terrain.value, self.tiles["grass"])
                        self.screen.blit(terrain_tile, (screen_x, screen_y))

                        # Draw items on ground if any
                        ground_items = self.engine.world.get_items_at(world_x, world_y)
                        if ground_items:
                            # Draw a smaller yellow square to represent items
                            item_tile = self.tiles["item"]
                            item_x = screen_x + (self.tile_size - item_tile.get_width()) // 2
                            item_y = screen_y + (self.tile_size - item_tile.get_height()) // 2
                            self.screen.blit(item_tile, (item_x, item_y))

                        # Draw character if present
                        character = self.engine.world.map.get_character_at(world_x, world_y)

                        if character:
                            if character.id == self.engine.player.id:
                                # Draw player
                                self.screen.blit(self.tiles["player"], (screen_x, screen_y))

                                # Draw player label
                                label = self.font_bold.render("P", True, COLORS["black"])
                                label_x = screen_x + (self.tile_size - label.get_width()) // 2
                                label_y = screen_y + (self.tile_size - label.get_height()) // 2
                                self.screen.blit(label, (label_x, label_y))

                                # Draw HP indicator for player
                                self._draw_hp_indicator(screen_x, screen_y, character)
                            else:
                                # Special handling for troll brigand
                                if character.race == CharacterRace.TROLL and character.character_class == CharacterClass.BRIGAND:
                                    self.screen.blit(self.tiles["troll_brigand"], (screen_x, screen_y))
                                else:
                                    # Draw NPC based on class
                                    char_class = character.character_class.value
                                    if char_class in self.tiles:
                                        self.screen.blit(self.tiles[char_class], (screen_x, screen_y))
                                    else:
                                        self.screen.blit(self.tiles["warrior"], (screen_x, screen_y))

                                # Draw NPC label (first letter of name)
                                label = self.font_bold.render(character.name[0], True, COLORS["black"])
                                label_x = screen_x + (self.tile_size - label.get_width()) // 2
                                label_y = screen_y + (self.tile_size - label.get_height()) // 2
                                self.screen.blit(label, (label_x, label_y))

                                # Draw HP indicator for characters in combat
                                if hasattr(character, 'hp') and character.hp < character.max_hp:
                                    self._draw_hp_indicator(screen_x, screen_y, character)

        # Draw a simple legend
        legend_y = map_y + view_height * self.tile_size + 20
        legend_x = map_x
        self.screen.blit(self.font_bold.render("Characters:", True, COLORS["white"]), (legend_x, legend_y))

        # List visible NPCs for clarity
        visible_npcs = []
        for pos, char in self.engine.world.map.characters.items():
            if char.id != self.engine.player.id:  # Skip player
                char_x, char_y = pos
                player_x, player_y = player_pos
                distance = ((char_x - player_x) ** 2 + (char_y - player_y) ** 2) ** 0.5
                if distance <= visibility_range:
                    visible_npcs.append(f"{char.name[0]}: {char.name} ({char.character_class.value})")

        # Draw the legend
        for i, npc_text in enumerate(visible_npcs):
            self.screen.blit(self.font.render(npc_text, True, COLORS["white"]),
                            (legend_x, legend_y + 25 + i * 20))

        # Draw ground items legend if there are any items
        has_items = False
        for y_offset in range(-visibility_range, visibility_range + 1):
            for x_offset in range(-visibility_range, visibility_range + 1):
                world_x = player_pos[0] + x_offset
                world_y = player_pos[1] + y_offset
                if 0 <= world_x < self.engine.world.map.width and 0 <= world_y < self.engine.world.map.height:
                    if self.engine.world.get_items_at(world_x, world_y):
                        has_items = True
                        break

        if has_items:
            item_legend_y = legend_y + 25 + len(visible_npcs) * 20 + 10
            self.screen.blit(self.font_bold.render("Items on ground:", True, COLORS["white"]),
                             (legend_x, item_legend_y))

            item_y = item_legend_y + 25
            for y_offset in range(-visibility_range, visibility_range + 1):
                for x_offset in range(-visibility_range, visibility_range + 1):
                    world_x = player_pos[0] + x_offset
                    world_y = player_pos[1] + y_offset

                    if 0 <= world_x < self.engine.world.map.width and 0 <= world_y < self.engine.world.map.height:
                        items = self.engine.world.get_items_at(world_x, world_y)
                        if items:
                            item_str = ", ".join([i.name if hasattr(i, 'name') else str(i) for i in items])
                            item_text = f"At ({world_x}, {world_y}): {item_str}"
                            self.screen.blit(self.font.render(item_text, True, COLORS["yellow"]),
                                            (legend_x, item_y))
                            item_y += 20

                            # Limit the number of items shown to avoid overcrowding
                            if item_y > item_legend_y + 100:
                                self.screen.blit(self.font.render("...", True, COLORS["white"]),
                                                (legend_x, item_y))
                                break

    def _draw_hp_indicator(self, x, y, character):
        """Draw a health bar indicator below a character"""
        if not hasattr(character, 'hp') or not hasattr(character, 'max_hp'):
            return

        # Calculate health percentage
        health_pct = character.hp / character.max_hp

        # Draw health bar background
        bar_width = self.tile_size - 4
        bar_height = 4
        bar_x = x + 2
        bar_y = y + self.tile_size - bar_height - 2

        bar_bg = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLORS["dark_gray"], bar_bg)

        # Draw health bar fill
        fill_width = int(bar_width * health_pct)
        if fill_width > 0:
            # Color based on health percentage
            if health_pct > 0.7:
                color = COLORS["green"]
            elif health_pct > 0.3:
                color = COLORS["yellow"]
            else:
                color = COLORS["red"]

            bar_fill = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
            pygame.draw.rect(self.screen, color, bar_fill)
