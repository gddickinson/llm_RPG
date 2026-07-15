"""Tutorial flow — teach by doing, one rep per system (P4.4c).

Steps are PREDICATES over state the game already tracks (collection
log, inventory, NPC status), so progress needs no bespoke plumbing.
The hint bar shows the current step; the boat at the dock's end is the
one-way exit. State: `player.metadata["tutorial_done"]`; being ON the
island = `current_dungeon.name == ISLAND_NAME` (so saves resume
mid-lesson for free).
"""

import logging
from typing import List, Optional

from world.tutorial_island import (ISLAND_NAME, SPAWN, BOAT_TILE,
                                   generate_island, build_instructors)

logger = logging.getLogger("llm_rpg.tutorial")


class TutorialManager:
    def __init__(self, engine):
        self.engine = engine

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Move a fresh player onto the island with a fishing rod."""
        engine = self.engine
        island = generate_island()
        engine.dungeons[ISLAND_NAME] = island
        engine.current_dungeon = island
        engine.dungeon_return_pos = engine.player.position
        engine.player.position = SPAWN
        for npc in build_instructors():
            engine.npc_manager.add_npc(npc)
        from items.item_registry import create_item
        rod = create_item("fishing_rod")
        if rod:
            engine.player.inventory.append(rod)
        engine.memory_manager.add_event(
            "You wake on Tutorial Island. Old Willem waves from the "
            "dock. (Follow the hints at the bottom of the view.)")

    @property
    def active(self) -> bool:
        zone = getattr(self.engine, "current_dungeon", None)
        return zone is not None and \
            getattr(zone, "name", "") == ISLAND_NAME and \
            not self.engine.player.metadata.get("tutorial_done")

    # ---- steps ---------------------------------------------------------------

    def _talked_to(self, npc_id: str) -> bool:
        npc = self.engine.npc_manager.get_npc(npc_id)
        return npc is not None and bool(npc.metadata.get("dialog_log"))

    def _collected(self, category: str, key: str) -> bool:
        return key in self.engine.collection_log.obtained(category)

    def _carrying(self, item_id: str) -> bool:
        return any(getattr(it, "id", "") == item_id
                   for it in self.engine.player.inventory)

    def current_step(self) -> Optional[str]:
        """The next instruction, or None when ready to depart."""
        if not self._talked_to("tut_willem"):
            return "[T] Talk to Old Willem on the dock"
        if not self._collected("items", "raw_trout"):
            return "[Z] Fish from the dock (you have Willem's rod)"
        if not self._collected("crafts", "cooked_trout"):
            return "[K] Cook your trout"
        if self._carrying("cooked_trout"):
            return "[I] Eat the trout (select it, then Q)"
        dummy = self.engine.npc_manager.get_npc("tut_dummy")
        if dummy is not None and dummy.is_active():
            return "[F] Strike Sergeant Bors' training dummy"
        return ("Walk to the end of the dock and press [TAB] "
                "to sail for the mainland")

    # ---- departure ---------------------------------------------------------------

    def try_depart(self) -> str:
        """TAB on the island: only the boat tile leaves — one way."""
        if self.engine.player.position != BOAT_TILE:
            step = self.current_step()
            return (f"The boat waits at the dock's end. "
                    f"Current lesson: {step}" if step else
                    "Walk to the dock's end to board the boat.")
        return self.depart()

    def depart(self) -> str:
        engine = self.engine
        # Remove the island cast
        for nid in list(engine.npc_manager.npcs):
            if nid.startswith("tut_"):
                npc = engine.npc_manager.npcs.pop(nid)
                try:
                    engine.world.map.remove_character(npc)
                except Exception:
                    pass
        engine.dungeons.pop(ISLAND_NAME, None)
        engine.current_dungeon = None
        pos = engine.dungeon_return_pos or (45, 35)
        engine.dungeon_return_pos = None
        engine.player.position = pos
        engine.world.map.place_character(engine.player, *pos)
        engine.player.metadata["tutorial_done"] = True
        msg = ("The boat carries you to the mainland. Your adventure "
               "begins — Oakvale Village lies ahead.")
        engine.memory_manager.add_event(msg)
        return msg


def hint_lines(engine) -> List[str]:
    """Tutorial hint for the hint bar (empty when not in tutorial)."""
    tm = getattr(engine, "tutorial_manager", None)
    if tm is None or not tm.active:
        return []
    step = tm.current_step()
    return [f"[Lesson] {step}" if step else
            "[Lesson] All done — board the boat! ([TAB] at dock's end)"]
