"""Collection log — completionism tracking (P2.5, the OSRS pattern).

Four categories, each a set of unique ids the player has "collected":
- items:  every distinct item id that has entered the inventory
- kills:  every distinct enemy kind the player has personally defeated
- crafts: every distinct recipe the player has crafted
- places: every named location the player has stood in

State lives in `player.metadata["collection"]` (lists in JSON, sets in
memory) so persistence rides save v3. The item/place scans run from
`advance_turn`, so pickups, purchases, quest rewards, gathering, and
loot all get recorded no matter which code path granted them.
"""

import logging
from typing import Dict, List, Set

logger = logging.getLogger("llm_rpg.collection")

CATEGORIES = ("items", "kills", "crafts", "places")


class CollectionLog:
    def __init__(self, engine):
        self.engine = engine

    # ---- storage ------------------------------------------------------

    def _store(self) -> Dict[str, List[str]]:
        meta = self.engine.player.metadata
        coll = meta.setdefault("collection", {})
        for cat in CATEGORIES:
            coll.setdefault(cat, [])
        return coll

    def _add(self, category: str, key: str) -> bool:
        """Record a key; True if it was new."""
        if not key:
            return False
        bucket = self._store()[category]
        if key in bucket:
            return False
        bucket.append(key)
        return True

    def obtained(self, category: str) -> Set[str]:
        return set(self._store().get(category, []))

    # ---- hooks ----------------------------------------------------------

    def tick(self) -> None:
        """Scan inventory + location; called each turn (cheap)."""
        player = self.engine.player
        for it in player.inventory:
            iid = getattr(it, "id", None)
            if iid and self._add("items", iid):
                self._maybe_announce("items", iid)
        from characters.equipment import equipped_items
        for it in equipped_items(player):
            iid = getattr(it, "id", None)
            if iid:
                self._add("items", iid)
        loc = self.engine.world.get_location_at(*player.position)
        if loc is not None and self._add("places", loc.name):
            self._maybe_announce("places", loc.name)

    def record_kill(self, defeated) -> None:
        """Keyed by name so 'Wolf' counts once across spawned wolves."""
        if self._add("kills", getattr(defeated, "name", "")):
            self._maybe_announce("kills", defeated.name)

    def record_craft(self, recipe_id: str) -> None:
        self._add("crafts", recipe_id)

    def _maybe_announce(self, category: str, key: str) -> None:
        # Announce only for rarer moments — kills and places
        if category == "kills":
            self.engine.memory_manager.add_event(
                f"[Collection] First {key} defeated!")
        elif category == "places":
            self.engine.memory_manager.add_event(
                f"[Collection] Discovered: {key}")

    # ---- totals ----------------------------------------------------------

    def totals(self) -> Dict[str, tuple]:
        """category -> (obtained, possible)."""
        from items.item_registry import ITEM_REGISTRY
        from items.crafting import RECIPES
        from world.monsters import MONSTER_TEMPLATES
        from characters.npc_presets import NPC_SPECS
        hostile_presets = [n for n, s in NPC_SPECS.items()
                           if s.get("class") in ("brigand", "troll",
                                                 "monster")]
        possible = {
            "items": len(ITEM_REGISTRY),
            "kills": len(MONSTER_TEMPLATES) + len(hostile_presets),
            "crafts": len(RECIPES),
            "places": len(self.engine.world.locations),
        }
        return {cat: (len(self.obtained(cat)), possible[cat])
                for cat in CATEGORIES}

    def overlay_lines(self) -> List[str]:
        """Text for the collection log overlay (O key)."""
        titles = {"items": "Items", "kills": "Foes bested",
                  "crafts": "Recipes crafted", "places": "Places found"}
        out = []
        totals = self.totals()
        grand = sum(o for o, _ in totals.values())
        grand_max = sum(p for _, p in totals.values())
        out.append(f"Collected {grand}/{grand_max}")
        try:
            from engine.pets import PETS
            owned = self.engine.player.metadata.get("pets", [])
            names = [PETS[s]["name"] for s in owned if s in PETS]
            out.append(f"Pets ({len(owned)}/{len(PETS)})" +
                       (": " + ", ".join(names) if names else ""))
        except Exception:
            pass
        for cat in CATEGORIES:
            got, possible = totals[cat]
            out.append("")
            out.append(f"{titles[cat]}  ({got}/{possible})")
            names = sorted(self.obtained(cat))
            for row_start in range(0, len(names), 3):
                out.append("  " + ", ".join(names[row_start:row_start + 3]))
        return out
