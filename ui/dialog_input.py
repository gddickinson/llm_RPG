"""Dialog typing input (split from input_handler.py to keep it under
the file-size line). Handles the text field, submit/cancel, and the
1–9 quest accept/turn-in hotkeys while a conversation is open.
"""

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False


def handle_dialog_input(gui, event) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_ESCAPE:
        gui.end_dialog()
        return True
    if event.key == pygame.K_RETURN:
        gui.submit_dialog()
        return True
    if event.key == pygame.K_BACKSPACE:
        gui.dialog_input = gui.dialog_input[:-1]
        return True
    # Quest accept / turn-in hotkeys (1-9) — only when the input field
    # is empty (otherwise the player is typing a number).
    if not gui.dialog_input and pygame.K_1 <= event.key <= pygame.K_9:
        gui.dialog_quest_action(event.key - pygame.K_1)
        return True
    ch = event.unicode
    if ch and ch.isprintable():
        gui.dialog_input += ch
        return True
    return False
