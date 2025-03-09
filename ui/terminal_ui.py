"""
Terminal UI module for LLM-RPG
Provides a simple terminal-based user interface
"""

import logging
import os
import time
import sys
from typing import Dict, List, Any, Optional, Tuple
import threading
# import msvcrt  # For Windows key input
import readchar  # Cross-platform input

# Try to import colorama for cross-platform colored terminal
try:
    from colorama import init, Fore, Back, Style
    has_colorama = True
    # Initialize colorama
    init()
except ImportError:
    has_colorama = False

import config

logger = logging.getLogger("llm_rpg.ui")

class TerminalUI:
    """Simple terminal-based UI for the game"""

    def __init__(self, engine):
        """Initialize the terminal UI with a reference to the game engine"""
        self.engine = engine
        self.running = False
        self.input_buffer = ""
        self.input_mode = "command"  # 'command' or 'dialog'
        self.current_dialog_target = None
        self.message_log = []
        self.max_messages = 10
        self.command_help = {
            "w/↑": "Move north",
            "s/↓": "Move south",
            "a/←": "Move west",
            "d/→": "Move east",
            "t": "Talk to nearby NPC",
            "i": "Show inventory",
            "c": "Show character sheet",
            "m": "Show full map",
            "l": "Look around",
            "h": "Show help",
            "q": "Quit game"
        }

        # Initialize terminal
        self._clear_screen()
        logger.info("Terminal UI initialized")

    def start(self):
        """Start the UI and game"""
        self.running = True
        self.engine.start_game()

        # Start input thread
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()

        # Initial render
        self.add_message("Welcome to LLM-RPG! Press 'h' for help.")
        self.add_message("You arrive at the outskirts of Oakvale Village.")
        self.render()

    def shutdown(self):
        """Shutdown the UI"""
        self.running = False
        # Wait for input thread to finish
        if hasattr(self, 'input_thread') and self.input_thread.is_alive():
            self.input_thread.join(timeout=0.5)

        # Clear screen on exit
        self._clear_screen()
        print("Thanks for playing LLM-RPG!")

    def _input_loop(self):
        """Thread for handling keyboard input"""
        while self.running:
            # Replace msvcrt.kbhit() and msvcrt.getch()
            key = readchar.readkey()
            self._handle_key(key)

    def _handle_key(self, key):
        """Handle a single key press"""
        if self.input_mode == "command":
            self._handle_command_key(key)
        elif self.input_mode == "dialog":
            self._handle_dialog_key(key)

    def _handle_command_key(self, key):
        """Handle key in command mode"""
        key = key.lower()

        # Movement
        # Arrow keys in readchar
        if key == readchar.key.UP:
            self.move_player(0, -1)
        elif key == readchar.key.DOWN:
            self.move_player(0, 1)
        elif key == readchar.key.RIGHT:
            self.move_player(1, 0)
        elif key == readchar.key.LEFT:
            self.move_player(-1, 0)
        # Regular keys
        elif key == 'w':
            self.move_player(0, -1)
        elif key == 's':
            self.move_player(0, 1)
        elif key == 'a':
            self.move_player(-1, 0)
        elif key == 'd':
            self.move_player(1, 0)

        # Other commands
        elif key == 't':
            self.talk_to_npc()
        elif key == 'i':
            self.show_inventory()
        elif key == 'c':
            self.show_character()
        elif key == 'm':
            self.show_map()
        elif key == 'l':
            self.look_around()
        elif key == 'h':
            self.show_help()
        elif key == 'q':
            self.engine.end_game()

        # Refresh UI after any command
        self.render()

    def _handle_dialog_key(self, key):
        """Handle key in dialog mode"""
        if key == readchar.key.ENTER:  # Enter
            # Submit dialog
            self._submit_dialog()
        elif key == readchar.key.ESC:  # Escape
            # Cancel dialog
            self.add_message("Dialog canceled.")
            self.input_mode = "command"
            self.input_buffer = ""
            self.current_dialog_target = None
        elif key == readchar.key.BACKSPACE:  # Backspace
            # Remove last character
            self.input_buffer = self.input_buffer[:-1]
        else:
            # Add character to buffer if it's a printable character
            if len(key) == 1 and key.isprintable():
                self.input_buffer += key

        # Refresh UI
        self.render()

    def _submit_dialog(self):
        """Submit the current dialog to the NPC"""
        if not self.input_buffer:
            return

        message = self.input_buffer
        self.input_buffer = ""

        if self.current_dialog_target:
            # Get response from NPC
            response = self.engine.interact_with_npc(self.current_dialog_target, message)
            self.add_message(f"You: {message}")
            self.add_message(f"{self.current_dialog_target}: {response}")

        # Return to command mode
        self.input_mode = "command"
        self.current_dialog_target = None

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
            self.current_dialog_target = npc.id
            response = self.engine.interact_with_npc(npc.id)
            self.add_message(f"{npc.name}: {response}")
            self.input_mode = "dialog"
            self.add_message("Type your response and press Enter (or Esc to cancel):")
        else:
            # Multiple NPCs, let player choose
            self.add_message("Nearby characters:")
            for i, npc in enumerate(nearby_npcs):
                self.add_message(f"{i+1}. {npc.name} ({npc.character_class.value})")

            # TODO: Implement NPC selection
            self.add_message("Talk to the first one for now.")
            npc = nearby_npcs[0]
            self.current_dialog_target = npc.id
            response = self.engine.interact_with_npc(npc.id)
            self.add_message(f"{npc.name}: {response}")
            self.input_mode = "dialog"
            self.add_message("Type your response and press Enter (or Esc to cancel):")

    def show_inventory(self):
        """Show the player's inventory"""
        player = self.engine.player
        self.add_message("--- Inventory ---")
        if not player.inventory:
            self.add_message("Your inventory is empty.")
        else:
            for item in player.inventory:
                item_name = item.name if hasattr(item, "name") else str(item)
                self.add_message(f"- {item_name}")

        self.add_message(f"Gold: {player.gold}")

    def show_character(self):
        """Show the player's character sheet"""
        player = self.engine.player
        self.add_message("--- Character Sheet ---")
        self.add_message(f"Name: {player.name}")
        self.add_message(f"Class: {player.character_class.value}")
        self.add_message(f"Race: {player.race.value}")
        self.add_message(f"Level: {player.level}")
        self.add_message(f"HP: {player.hp}/{player.max_hp}")
        self.add_message("--- Stats ---")
        self.add_message(f"STR: {player.strength}")
        self.add_message(f"DEX: {player.dexterity}")
        self.add_message(f"CON: {player.constitution}")
        self.add_message(f"INT: {player.intelligence}")
        self.add_message(f"WIS: {player.wisdom}")
        self.add_message(f"CHA: {player.charisma}")

    def show_map(self):
        """Show the full game map"""
        map_str = self.engine.world.map.to_string(
            highlight_pos=self.engine.player.position,
            visibility_range=config.DEFAULT_VISIBILITY_RANGE
        )
        self.add_message("--- World Map ---")
        for line in map_str.split('\n'):
            if line.strip():
                self.add_message(line)

    def look_around(self):
        """Look at the surrounding area"""
        player_x, player_y = self.engine.player.position

        # Get current location
        game_state = self.engine.get_game_state()
        location = game_state.get("location")

        if location:
            self.add_message(f"Location: {location.name}")
            self.add_message(f"{location.description}")
        else:
            self.add_message("You are in the wilderness.")

        # Get visible area description
        visible_desc = self.engine.world.map.get_visible_description(
            player_x, player_y,
            visibility_range=config.DEFAULT_VISIBILITY_RANGE
        )

        self.add_message("--- You see ---")
        for line in visible_desc.split('\n'):
            if line.strip():
                self.add_message(line)

    def show_help(self):
        """Show help text"""
        self.add_message("--- Commands ---")
        for cmd, desc in self.command_help.items():
            self.add_message(f"{cmd}: {desc}")

    def add_message(self, message):
        """Add a message to the message log"""
        self.message_log.append(message)
        # Trim log if needed
        if len(self.message_log) > self.max_messages:
            self.message_log = self.message_log[-self.max_messages:]

    def update(self):
        """Update the UI based on game state"""
        # Only render if something has changed
        self.render()

    def render(self):
        """Render the current game state to the terminal"""
        self._clear_screen()

        # Get game state
        game_state = self.engine.get_game_state()

        # Print header
        self._print_header(game_state)

        # Print map
        self._print_map(game_state)

        # Print message log
        self._print_messages()

        # Print status line
        self._print_status_line(game_state)

        # Print input line if in dialog mode
        if self.input_mode == "dialog":
            self._print_input_line()

    def _print_header(self, game_state):
        """Print the header with game info"""
        location = game_state.get("location")
        location_name = location.name if location else "Wilderness"

        # Format time
        time_str = self.engine.world.get_formatted_time()

        if has_colorama:
            print(f"{Fore.YELLOW}{Style.BRIGHT}LLM-RPG{Style.RESET_ALL} | " +
                  f"{Fore.GREEN}{location_name}{Style.RESET_ALL} | " +
                  f"{Fore.CYAN}{time_str}{Style.RESET_ALL}")
            print("-" * 80)
        else:
            print(f"LLM-RPG | {location_name} | {time_str}")
            print("-" * 80)

    def _print_map(self, game_state):
        """Print a small section of the map around the player"""
        player_pos = self.engine.player.position
        small_map = self.engine.world.map.to_string(
            highlight_pos=player_pos,
            visibility_range=config.DEFAULT_VISIBILITY_RANGE
        )

        # Print small map section
        print("Map:")
        for line in small_map.split('\n'):
            if line.strip():
                # Colorize map if colorama is available
                if has_colorama:
                    colored_line = ""
                    for char in line:
                        if char == '.':  # Grass
                            colored_line += Fore.GREEN + char
                        elif char == 'T':  # Forest
                            colored_line += Fore.GREEN + Style.BRIGHT + char
                        elif char == '^':  # Mountain
                            colored_line += Fore.WHITE + Style.BRIGHT + char
                        elif char == '~':  # Water
                            colored_line += Fore.BLUE + char
                        elif char == '=':  # Road
                            colored_line += Fore.YELLOW + char
                        elif char == '#':  # Building
                            colored_line += Fore.RED + char
                        elif char == 'C':  # Cave
                            colored_line += Fore.BLACK + Style.BRIGHT + char
                        elif char == '@':  # Player
                            colored_line += Fore.CYAN + Style.BRIGHT + char
                        elif char == '?':  # Unknown
                            colored_line += Fore.BLACK + char
                        else:  # NPCs and other objects
                            colored_line += Fore.MAGENTA + Style.BRIGHT + char
                    print(colored_line + Style.RESET_ALL)
                else:
                    print(line)

        print()

    def _print_messages(self):
        """Print the message log"""
        print("Messages:")
        for msg in self.message_log:
            print(msg)
        print()

    def _print_status_line(self, game_state):
        """Print the status line with player info"""
        player = self.engine.player

        if has_colorama:
            hp_color = Fore.GREEN if player.hp > player.max_hp * 0.5 else (
                      Fore.YELLOW if player.hp > player.max_hp * 0.25 else Fore.RED)

            print(f"{Fore.CYAN}{Style.BRIGHT}{player.name}{Style.RESET_ALL} | " +
                  f"HP: {hp_color}{player.hp}/{player.max_hp}{Style.RESET_ALL} | " +
                  f"Gold: {Fore.YELLOW}{player.gold}{Style.RESET_ALL}")
        else:
            print(f"{player.name} | HP: {player.hp}/{player.max_hp} | Gold: {player.gold}")

    def _print_input_line(self):
        """Print the input line for dialog mode"""
        print("\nYour response:")

        if has_colorama:
            print(f"{Fore.CYAN}> {self.input_buffer}{Style.RESET_ALL}")
        else:
            print(f"> {self.input_buffer}")

    def _clear_screen(self):
        """Clear the terminal screen"""
        if os.name == 'nt':  # For Windows
            os.system('cls')
        else:  # For Linux and Mac
            os.system('clear')
