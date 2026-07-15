"""Conversation-menu dispatch (PUX.6) — runs a numbered quick-pick
from the dialog menu. Split out of gui.py to keep it under the line.
"""

from engine import secrets


def apply(gui, idx: int) -> None:
    """Execute the idx-th conversation option against the current NPC:
    accept / turn in a quest, open the shop, ask about a topic, or
    press for a secret. Free-text talk still works alongside it."""
    if not gui.dialog_npc_id or idx >= len(gui.dialog_menu):
        return
    npc = gui.engine.npc_manager.get_npc(gui.dialog_npc_id)
    item = gui.dialog_menu[idx]
    kind = item["kind"]
    if kind == "accept":
        q = gui.engine.quest_manager.get(item["quest_id"])
        gui.engine.accept_quest(item["quest_id"])
        gui.dialog_pending_reply = f"(Quest accepted: {q.title})"
    elif kind == "turnin":
        q = gui.engine.quest_manager.get(item["quest_id"])
        gui.engine.turn_in_quest(item["quest_id"])
        gui.dialog_pending_reply = (
            f"(Turned in: {q.title} — {q.reward_gold}g, {q.reward_xp}xp)")
    elif kind == "trade":
        gui.end_dialog()
        gui.show_shop(npc)
        return
    elif kind == "topic":
        gui.dialog_pending_reply = gui.engine.topic_journal.npc_response(
            npc, item["topic"]) or "..."
    elif kind == "secret":
        unlocked = secrets.unlocked_secrets(gui.engine, npc)
        if unlocked:
            gui.dialog_pending_reply = secrets.reveal(
                gui.engine, npc, unlocked[0]["id"]) or "..."
    gui._refresh_dialog_menu()
