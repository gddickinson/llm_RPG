"""UI package for LLM-RPG.

Exports the terminal and pygame UIs (pygame is optional).
"""

from ui.terminal_ui import TerminalUI

try:
    from ui.gui import GameGUI
    from ui.renderer import MapRenderer
    from ui.hud import HUD
    from ui.input_handler import InputHandler
    from ui.sprite_loader import SpriteLoader
    __all__ = [
        "TerminalUI", "GameGUI",
        "MapRenderer", "HUD", "InputHandler", "SpriteLoader",
    ]
except ImportError:
    __all__ = ["TerminalUI"]
