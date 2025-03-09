"""
GUI Interface module for LLM-RPG
Entry point for launching the GUI version of the game
"""

import logging
import argparse
import sys
import os

# Ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.game_engine import GameEngine
from ui.gui import GameGUI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("llm_rpg.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("llm_rpg.gui_interface")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="LLM-RPG GUI: D&D-style game with LLM-powered NPCs")
    parser.add_argument("--model", default="llama3", help="LLM model to use (default: llama3)")
    parser.add_argument("--width", type=int, default=1200, help="Window width (default: 1200)")
    parser.add_argument("--height", type=int, default=800, help="Window height (default: 800)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

def main():
    """Main entry point for the GUI version of the game"""
    # Parse command line arguments
    args = parse_args()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting LLM-RPG GUI with model: {args.model}")
    
    # Initialize game engine
    engine = GameEngine(llm_model=args.model)
    
    # Initialize GUI
    gui = GameGUI(engine, width=args.width, height=args.height)
    
    # Start the game
    try:
        gui.start()
    except KeyboardInterrupt:
        logger.info("Game terminated by user")
    except Exception as e:
        logger.exception(f"Error in main game loop: {str(e)}")
    finally:
        # Clean up
        gui.shutdown()
        logger.info("Game ended")

if __name__ == "__main__":
    main()