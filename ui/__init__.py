# ui/__init__.py
from .terminal_ui import TerminalUI
try:
    from .gui import GameGUI
    __all__ = ['TerminalUI', 'GameGUI']
except ImportError:
    __all__ = ['TerminalUI']
