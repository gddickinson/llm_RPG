"""Structures (P9.1) — fantastical buildings as pure data.

A structure in `data/structures.json` is a named stack of themed
levels that attaches to an overworld location: each level is a grid
of letters (W wall, F/. floor, D door, `>` stairs down, `<` stairs
up, T/B/C/R/A/S furniture, K inscription), linked with the P9A.5
twinned-stair convention. Levels can be `dark` (the P8.6
shadowcaster runs — bring your courage), carry authored inscriptions
(E to read), and list monsters that POPULATE ON FIRST VISIT and stay
put as zone natives. Which levels have been populated persists via
save_load, so a cleared crypt stays cleared.

The Ruined Keep ships as the first structure; the temple crypt and
wizard's tower (P9.3/P9.4) are JSON away.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.structures")

CELL_FURNITURE = {"T": "Table", "B": "Bed", "C": "Chest",
                  "R": "Barrel", "A": "Anvil", "S": "Altar"}


def _load() -> Dict[str, dict]:
    try:
        with open(os.path.join("data", "structures.json")) as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("structures.json missing/corrupt")
        return {}


STRUCTURES: Dict[str, dict] = _load()


class StructureBuilder:
    def __init__(self, engine):
        self.engine = engine
        self.populated: Dict[str, List[str]] = {}
        # (structure, x, y) -> [Item, ...]; looted keys
        self.chest_contents: Dict[str, list] = {}
        self.looted: List[str] = []
        # Sigil puzzles (P9.4): touch progress + solved wards
        self.puzzle_progress: Dict[str, list] = {}
        self.solved: List[str] = []
        # Lever/gate puzzles (P21.3): which levers are thrown, per zone
        self.lever_state: Dict[str, list] = {}

    # ------------------------------------------------------------ build

    def build(self) -> int:
        """Attach every structure to its location. Idempotent."""
        built = 0
        for sid, spec in STRUCTURES.items():
            target = spec.get("attach_to", "")
            loc = next((l for l in self.engine.world.locations
                        if target.lower() in l.name.lower()), None)
            if loc is None:
                continue
            existing = self.engine.interiors.get(loc.name)
            if existing is not None and \
                    getattr(existing, "structure_id", None) == sid:
                continue
            levels = [self._build_level(lv, sid)
                      for lv in spec.get("levels", [])]
            if not levels:
                continue
            self._link(levels, spec.get("levels", []))
            gi = self._ground_index(spec.get("levels", []))
            levels[gi].ground = True
            self.engine.interiors[loc.name] = levels[gi]
            self._history_inscriptions(levels)
            self._sweep_footprint_loot(loc, levels, sid)
            self._authored_loot(levels, spec.get("levels", []), sid)
            built += 1
        return built

    def _authored_loot(self, levels, specs, sid: str) -> None:
        """`chest_loot` item ids fill that level's chest (once)."""
        from items.item_registry import create_item
        for level, spec in zip(levels, specs):
            ids = spec.get("chest_loot", [])
            if not ids:
                continue
            chest = next((f for f in level.furniture
                          if f["name"] == "Chest"), None)
            if chest is None:
                continue
            key = f"{sid}:{chest['x']}:{chest['y']}"
            if key in self.looted or key in self.chest_contents:
                continue
            items = [create_item(i) for i in ids]
            self.chest_contents[key] = [i for i in items
                                        if i is not None]

    def _history_inscriptions(self, levels) -> None:
        """'$history' inscriptions carry this world's actual past
        (P9.2): the history-sim's lore lines, oldest first."""
        lore = [f"Year {ev.get('year')}: {ev.get('description')}"
                for ev in getattr(self.engine, "world_history", [])]
        i = 0
        for level in levels:
            for piece in level.furniture:
                if piece.get("text") == "$history":
                    piece["text"] = lore[i % len(lore)] if lore else \
                        "The carving is too worn to read."
                    i += 1

    def _sweep_footprint_loot(self, loc, levels, sid: str) -> None:
        """Relics the history sim dropped on the footprint (solid
        walls made them unreachable) move into the DEEPEST chest —
        guarded, findable, and legend-revealing when looted."""
        ground = getattr(self.engine.world, "ground_items", {})
        swept = []
        for (x, y) in list(ground.keys()):
            if loc.contains(x, y):
                items = ground.pop((x, y), [])
                swept += [i for i in items if hasattr(i, "id")]
        if not swept:
            return
        # the DEEPEST chest — by floor when floors are used, else the last
        deepest = min(levels, key=lambda z: z.floor) \
            if all(getattr(z, "floor", None) is not None for z in levels) \
            else levels[-1]
        chest = next((f for f in deepest.furniture
                      if f["name"] == "Chest"), None)
        if chest is None:
            return
        key = f"{sid}:{chest['x']}:{chest['y']}"
        self.chest_contents.setdefault(key, []).extend(swept)

    def loot_chest(self, zone, piece) -> Optional[str]:
        """Furniture hook: a structure chest with contents yields
        them exactly once."""
        sid = getattr(zone, "structure_id", None)
        if sid is None or piece.get("name") != "Chest":
            return None
        key = f"{sid}:{piece['x']}:{piece['y']}"
        if key in self.looted:
            return "The chest stands empty — you've had its secrets."
        items = self.chest_contents.get(key)
        if not items:
            return None
        player = self.engine.player
        from engine.carry import can_carry, full_message
        if not can_carry(player, extra=len(items)):
            return ("The chest brims with treasure — but " +
                    full_message(player))
        self.looted.append(key)
        names = []
        for item in items:
            player.inventory.append(item)
            names.append(getattr(item, "name", str(item)))
            try:
                from engine.legends import on_item_picked_up
                note = on_item_picked_up(self.engine, item)
                if note:
                    self.engine.memory_manager.add_event(note)
            except Exception:
                pass
        return f"Inside the chest: {', '.join(names)}."

    def _build_level(self, spec: dict, sid: str):
        from world.interiors import Interior
        from world.world_map import TerrainType
        rows = spec.get("grid", [])
        h, w = len(rows), max(len(r) for r in rows)
        inter = Interior(name=spec.get("name", sid),
                         width=w, height=h, ground=False,
                         description=spec.get("description", ""))
        inter.terrain = [[TerrainType.GRASS for _ in range(w)]
                         for _ in range(h)]
        inter.door = (w // 2, h - 1)
        inscriptions = list(spec.get("inscriptions", []))
        for y, row in enumerate(rows):
            for x, cell in enumerate(row.ljust(w, "W")):
                if cell == "W":
                    inter.terrain[y][x] = TerrainType.BUILDING
                elif cell == "D":
                    inter.terrain[y][x] = TerrainType.ROAD
                    inter.door = (x, y)
                elif cell == ">":
                    inter.stairs_down = (x, y)
                    inter.furniture.append(
                        {"name": "Stairs down", "x": x, "y": y})
                elif cell == "<":
                    inter.stairs_up = (x, y)
                    inter.furniture.append(
                        {"name": "Stairs up", "x": x, "y": y})
                elif cell == "K":
                    text = inscriptions.pop(0) if inscriptions else \
                        "The carving is too worn to read."
                    inter.furniture.append(
                        {"name": "Inscription", "x": x, "y": y,
                         "text": text})
                elif cell == "G":
                    idx = sum(1 for f in inter.furniture
                              if f["name"] == "Sigil")
                    inter.furniture.append(
                        {"name": "Sigil", "x": x, "y": y, "idx": idx})
                elif cell == "L":          # lever (P21.3), numbered in order
                    idx = sum(1 for f in inter.furniture
                              if f["name"] == "Lever")
                    inter.furniture.append(
                        {"name": "Lever", "x": x, "y": y, "idx": idx})
                elif cell in CELL_FURNITURE:
                    inter.furniture.append(
                        {"name": CELL_FURNITURE[cell], "x": x, "y": y})
        inter.dark = bool(spec.get("dark", False))
        inter.structure_id = sid
        inter.spawns = list(spec.get("monsters", []))
        inter.occupants = list(spec.get("occupants", []))   # P18.2 residents
        inter.puzzle = spec.get("puzzle")
        inter.floor = spec.get("floor")                     # P18.3 elevation
        try:   # P39.3 decorate the level in-theme (a crypt gets sarcophagi…)
            from world.furnishings import furnish
            furnish(inter, spec.get("name", sid))
        except Exception as e:
            logger.debug(f"furnish structure level {sid}: {e}")
        return inter

    # --------------------------------------------------------- puzzles

    def stairs_warded(self, zone, up: bool) -> bool:
        """A shimmering ward until the level's sigils are solved."""
        puzzle = getattr(zone, "puzzle", None)
        if not puzzle or zone.name in self.solved:
            return False
        return puzzle.get("wards") == ("up" if up else "down")

    def touch_sigil(self, zone, piece) -> str:
        """E on a sigil: touch them in the inscription's order."""
        puzzle = getattr(zone, "puzzle", None)
        if not puzzle:
            return "The sigil is cold and inert."
        if zone.name in self.solved:
            return "The sigils lie quiet; the ward is long gone."
        names = puzzle.get("names", [])
        order = puzzle.get("order", [])
        idx = piece.get("idx", 0)
        name = names[idx] if idx < len(names) else f"sigil {idx}"
        progress = self.puzzle_progress.setdefault(zone.name, [])
        expected = order[len(progress)] if len(progress) < len(order) \
            else None
        if idx == expected:
            progress.append(idx)
            if len(progress) == len(order):
                self.solved.append(zone.name)
                self.puzzle_progress.pop(zone.name, None)
                msg = (f"The {name} sigil blazes — and the ward over "
                       f"the stairs dissolves!")
            else:
                msg = f"The {name} sigil lights and holds. " \
                      f"({len(progress)}/{len(order)})"
        else:
            self.puzzle_progress[zone.name] = []
            msg = (f"The {name} sigil flares angrily; all the sigils "
                   f"go dark. (Read the inscription.)")
        self.engine.memory_manager.add_event(msg)
        return msg

    def pull_lever(self, zone, piece) -> str:
        """E on a lever (P21.3): throw levers until the up-set matches the
        mechanism's pattern, and the gate/ward grinds open."""
        puzzle = getattr(zone, "puzzle", None)
        if not puzzle or puzzle.get("kind") != "lever":
            return "The lever won't budge."
        if zone.name in self.solved:
            return "The mechanism is already sprung; the way is open."
        idx = piece.get("idx", 0)
        up = self.lever_state.setdefault(zone.name, [])
        if idx in up:
            up.remove(idx)
        else:
            up.append(idx)
        if set(up) == set(puzzle.get("pattern", [])):
            self.solved.append(zone.name)
            self.lever_state.pop(zone.name, None)
            msg = ("With a deep clank the gears catch — the gate grinds "
                   "open and the way is clear!")
        else:
            msg = ("The lever throws with a heavy clunk; somewhere stone "
                   "shifts. (The levers must all sit just so.)")
        self.engine.memory_manager.add_event(msg)
        return msg

    def offer_at_altar(self, zone, piece) -> str:
        """E on an altar (P21.3): an item-fit puzzle — lay the thing the
        altar hungers for upon it and the ward dissolves."""
        puzzle = getattr(zone, "puzzle", None)
        if not puzzle or puzzle.get("kind") != "altar":
            return "The altar is bare, cold stone."
        if zone.name in self.solved:
            return "The altar is spent; its ward is long gone."
        need = puzzle.get("requires", "")
        player = self.engine.player
        held = next((it for it in player.inventory
                     if getattr(it, "id", "") == need
                     or need and need in getattr(it, "name", "").lower()),
                    None)
        if held is None:
            return puzzle.get(
                "hint", "The altar hungers for something you do not carry.")
        player.inventory.remove(held)
        self.solved.append(zone.name)
        msg = puzzle.get(
            "solve_line",
            "Your offering flares and is gone — the ward dissolves!")
        self.engine.memory_manager.add_event(msg)
        return msg

    def _link(self, levels, specs) -> None:
        floors = [s.get("floor") for s in specs]
        if all(f is not None for f in floors):
            # Link by ELEVATION (P18.3): a mid-stack ground level can then
            # carry BOTH storeys above (apartments, battlements) AND a
            # cellar/dungeon below — the linear chain couldn't branch.
            order = sorted(range(len(levels)), key=lambda i: floors[i])
            for a, b in zip(order, order[1:]):
                lower, upper = levels[a], levels[b]
                lower.level_above = upper
                upper.level_below = lower
            return
        # Legacy linear chain by each level's `position` (above/below).
        for i in range(1, len(levels)):
            prev, cur = levels[i - 1], levels[i]
            if specs[i].get("position", "below") == "above":
                prev.level_above = cur
                cur.level_below = prev
            else:
                prev.level_below = cur
                cur.level_above = prev

    @staticmethod
    def _ground_index(specs) -> int:
        """Which level you enter from the overworld — the `floor: 0` (or
        `ground: true`) level if named, else the first (legacy)."""
        for i, s in enumerate(specs):
            if s.get("floor") == 0 or s.get("ground"):
                return i
        return 0

    # -------------------------------------------------------- populate

    def on_enter_level(self, zone) -> int:
        """First visit wakes the level's monsters AND seats its friendly
        residents (P18.2) — both as zone natives that stay put at their
        posts. Returns the count of monsters roused."""
        sid = getattr(zone, "structure_id", None)
        if sid is None:
            return 0
        done = self.populated.setdefault(sid, [])
        if zone.name in done:
            return 0
        done.append(zone.name)
        spawned = 0
        from world.monsters import build_monster
        for spawn in getattr(zone, "spawns", []):
            npc = build_monster(spawn.get("template", "goblin"),
                                tuple(spawn.get("at", (2, 2))))
            npc.metadata["zone"] = zone.name
            self.engine.npc_manager.add_npc(npc)
            spawned += 1
        self._seat_occupants(zone)
        if spawned:
            self.engine.memory_manager.add_event(
                "Something stirs in the dark ahead...")
        return spawned

    def _seat_occupants(self, zone) -> int:
        """P18.2: place a level's named residents (royal family, staff,
        garrison) as friendly zone natives at their posts — the same
        entities the dialog/memory systems already understand."""
        from characters.npc_presets import make_npc, NPC_SPECS
        seated = 0
        for occ in getattr(zone, "occupants", []):
            nid = occ.get("npc")
            if nid not in NPC_SPECS or \
                    self.engine.npc_manager.get_npc(nid) is not None:
                continue
            npc = make_npc(nid, position=tuple(occ.get("at", (2, 2))))
            npc.metadata["zone"] = zone.name
            npc.metadata["resident"] = True
            self.engine.npc_manager.add_npc(npc)
            seated += 1
        return seated

    # ------------------------------------------------------ persistence

    def to_dict(self) -> dict:
        chests = {}
        for key, items in self.chest_contents.items():
            chests[key] = [i.to_dict() for i in items
                           if hasattr(i, "to_dict")]
        return {"populated": {k: list(v)
                              for k, v in self.populated.items()},
                "chests": chests,
                "looted": list(self.looted),
                "solved": list(self.solved),
                "puzzle_progress": {k: list(v) for k, v in
                                    self.puzzle_progress.items()},
                "lever_state": {k: list(v) for k, v in
                                self.lever_state.items()}}

    def from_dict(self, data: dict) -> None:
        from items.item import Item
        self.populated = {k: list(v) for k, v in
                          data.get("populated", {}).items()}
        self.looted = list(data.get("looted", []))
        self.solved = list(data.get("solved", []))
        self.puzzle_progress = {k: list(v) for k, v in
                                data.get("puzzle_progress",
                                         {}).items()}
        self.lever_state = {k: list(v) for k, v in
                            data.get("lever_state", {}).items()}
        self.chest_contents = {}
        for key, dicts in data.get("chests", {}).items():
            try:
                self.chest_contents[key] = [Item.from_dict(d)
                                            for d in dicts]
            except Exception:
                pass
