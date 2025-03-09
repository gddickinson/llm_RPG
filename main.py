#!/usr/bin/env python3
"""
LLM-RPG: A D&D-style RPG with LLM-powered NPCs
Main entry point for the game
"""

import logging
import argparse
import time
import sys

from engine.game_engine import GameEngine
from ui.terminal_ui import TerminalUI
try:
    from ui.gui import GameGUI
    has_pygame = True
except ImportError:
    has_pygame = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("llm_rpg.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("llm_rpg")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="LLM-RPG: D&D-style game with LLM-powered NPCs")
    parser.add_argument("--model", default="llama3", help="LLM model to use (default: llama3)")
    parser.add_argument("--ui", choices=["terminal", "gui"], default="gui" if has_pygame else "terminal",
                      help="User interface to use (default: gui if available, otherwise terminal)")
    parser.add_argument("--width", type=int, default=1200, help="Window width for GUI (default: 1200)")
    parser.add_argument("--height", type=int, default=800, help="Window height for GUI (default: 800)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

def main():
    """Main entry point for the game"""
    # Parse command line arguments
    args = parse_args()

    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info(f"Starting LLM-RPG with model: {args.model}")

    # Initialize game engine
    engine = GameEngine(llm_model=args.model)

    # Initialize UI based on user choice
    if args.ui == "gui":
        if has_pygame:
            ui = GameGUI(engine, width=args.width, height=args.height)
        else:
            logger.warning("GUI requested but pygame not available. Falling back to terminal UI.")
            ui = TerminalUI(engine)
    else:
        ui = TerminalUI(engine)

    # Start the game
    try:
        ui.start()

        # If terminal UI, need to run the main loop here
        if args.ui == "terminal" or (args.ui == "gui" and not has_pygame):
            # Main game loop - UI handles most of the interaction
            while engine.running:
                # Process NPC actions asynchronously
                engine.process_npc_turns_async()

                # Update UI
                ui.update()

                # Small delay to prevent CPU overuse
                time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Game terminated by user")
    except Exception as e:
        logger.exception(f"Error in main game loop: {str(e)}")
    finally:
        # Clean up
        ui.shutdown()
        logger.info("Game ended")

if __name__ == "__main__":
    main()
