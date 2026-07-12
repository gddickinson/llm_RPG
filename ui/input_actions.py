"""Play-mode action helpers split out of `input_handler` to hold that
file under the 500-line rule: look-around, party toggle, open-shop.

Each takes the `InputHandler` (or its engine) so they can reach the engine
and gui without duplicating the wiring.
"""


def look_around(engine) -> None:
    try:
        x, y = engine.player.position
        visible = engine.world.map.get_visible_description(x, y)
        for line in visible.split("\n"):
            if line.strip():
                engine.memory_manager.add_event(line)
    except Exception:
        pass


def toggle_party(handler) -> None:
    """P key — dismiss an adjacent party member, or try to recruit."""
    engine = handler.engine
    try:
        npc = handler._find_adjacent_npc()
        if npc is None:
            engine.memory_manager.add_event("No one nearby to recruit.")
            return
        if npc.id in engine.companion_manager.party:
            engine.dismiss_companion(npc.id)
            return
        msg = engine.recruit(npc.id)
        # Success is logged by the manager; log refusals too
        if "joins your party" not in msg:
            engine.memory_manager.add_event(msg)
    except Exception:
        pass


def open_shop(handler) -> None:
    engine, gui = handler.engine, handler.gui
    try:
        from engine.shop import merchants_near
        merchants = merchants_near(engine, engine.player, radius=2.0)
        if not merchants:
            engine.memory_manager.add_event("There's no merchant nearby.")
            return
        refusal = engine.shop_manager.trade_refusal(
            engine.player, merchants[0])   # P12.11
        if refusal:
            engine.memory_manager.add_event(refusal)
            return
        gui.show_shop(merchants[0])
    except Exception:
        pass
