#!/usr/bin/env python3
"""LLM-RPG entry point.

Examples:
    python main.py                                  # Pygame GUI, heuristic AI
    python main.py --ui terminal                    # Terminal UI
    python main.py --provider ollama --model llama3 # Use local Ollama
    python main.py --provider anthropic \\
        --model claude-haiku-4-5-20251001           # Use Anthropic
    python main.py --load                           # Resume last save
"""

import argparse
import logging
import sys
import time

from engine.game_engine import GameEngine
from llm.providers import available_providers

try:
    from ui.gui import GameGUI
    has_pygame = True
except ImportError:
    has_pygame = False

from ui.terminal_ui import TerminalUI


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("llm_rpg.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("llm_rpg")


def parse_args():
    p = argparse.ArgumentParser(
        description="LLM-RPG: D&D-style game with LLM-powered NPCs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--ui", choices=["terminal", "gui"],
                   default="gui" if has_pygame else "terminal",
                   help="User interface (default: gui if pygame installed)")
    p.add_argument("--provider", default="heuristic",
                   choices=available_providers(),
                   help="LLM provider (default: heuristic, no LLM needed)")
    p.add_argument("--model", default="llama3",
                   help="Model name for the provider (default: llama3)")
    p.add_argument("--width", type=int, default=1280,
                   help="Window width for GUI")
    p.add_argument("--height", type=int, default=800,
                   help="Window height for GUI")
    p.add_argument("--tile-size", type=int, default=32,
                   help="Tile size in pixels")
    p.add_argument("--load", nargs="?", const="quicksave.json",
                   default=None,
                   help="Load a save file at startup (defaults to quicksave.json)")
    p.add_argument("--no-quests", action="store_true",
                   help="Disable quest system")
    p.add_argument("--no-npc-processes", action="store_true",
                   help="Disable multiprocess NPC actions (uses sync calls instead)")
    p.add_argument("--dm-bridge", action="store_true",
                   help="Enable the file-based Dungeon Master bridge "
                        "(saves/dm/)")
    p.add_argument("--tutorial", action="store_true",
                   help="Start on Tutorial Island (learn every system)")
    p.add_argument("--no-menu", action="store_true",
                   help="Skip the start menu and go straight to the game")
    p.add_argument("--debug", action="store_true",
                   help="Enable debug logging")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(
        f"Starting LLM-RPG (provider={args.provider}, model={args.model}, "
        f"ui={args.ui})"
    )

    # Start menu (GUI only) — returns the user's choice
    player_spec = None
    load_save_name = args.load
    if args.ui == "gui" and has_pygame and not args.no_menu \
            and not args.load:
        try:
            from ui.start_menu import StartMenu
            while True:                       # menu loops for the testbed
                choice = StartMenu(
                    width=args.width, height=args.height).run()
                if choice["action"] == "battle":
                    from ui.battle_screen import run_battle_testbed
                    run_battle_testbed(choice["scenario"],
                                       width=args.width,
                                       height=args.height)
                    continue                  # back to the menu
                break
            if choice["action"] == "quit":
                return 0
            if choice["action"] == "load":
                load_save_name = choice["save_name"]
            elif choice["action"] == "new":
                player_spec = choice.get("spec")
        except Exception as e:
            logger.warning(f"Start menu failed, skipping: {e}")

    # Build engine
    engine = GameEngine(
        llm_model=args.model,
        llm_provider=args.provider,
        enable_npc_processes=(not args.no_npc_processes
                              and args.provider != "heuristic"),
        enable_quests=(not args.no_quests),
        player_spec=player_spec,
        start_tutorial=args.tutorial,
        enable_dm_bridge=args.dm_bridge,
    )

    # Optional load
    if load_save_name:
        if engine.load_game(load_save_name):
            logger.info(f"Loaded save: {load_save_name}")
        else:
            logger.warning(f"Could not load save: {load_save_name}")

    # UI selection
    if args.ui == "gui":
        if not has_pygame:
            logger.warning("pygame not available, falling back to terminal")
            ui = TerminalUI(engine)
        else:
            ui = GameGUI(engine, width=args.width, height=args.height,
                         tile_size=args.tile_size)
    else:
        ui = TerminalUI(engine)

    try:
        ui.start()
        if args.ui == "terminal":
            while engine.running:
                engine.process_npc_turns_async()
                ui.update()
                time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal: {e}")
        return 1
    finally:
        try:
            ui.shutdown()
        except Exception as e:
            logger.warning(f"Shutdown warning: {e}")
        logger.info("Game ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
