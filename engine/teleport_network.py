"""P28.1a — the Wayfarers' Conclave teleport network.

A public magical transit: a rune-circle PLATFORM (waystone) is planted beside
every town, and a traveller carrying a common Wayfarer's RING (a data item
flagged `teleport_access`, which the player starts with) can stand on one
platform and step to any other. Place-to-place travel — not the diary-gated
anywhere-to-a-town-centre `TravelSystem`, which stays as it is.

Content-as-data: `data/teleport_network.json` (platforms + their settlements).
Markers ride the world save; the system persists its own small index. Arrival
lands on a safe walkable tile beside the destination waystone (P28.1b will
divert a crowded arrival further out).
"""

import logging
from typing import Dict, List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.teleport_network")

_WALKABLE_BAD = (TerrainType.BUILDING, TerrainType.WATER, TerrainType.MOUNTAIN)
STAND_RADIUS = 1                 # how near the waystone you must stand to use it


class TeleportNetwork:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.platforms: List[dict] = []      # [{id, name, settlement, pos}]
        self._seeded = False

    # ---- data ------------------------------------------------------

    def _specs(self) -> List[dict]:
        from items.data_loader import load_data_file
        try:
            return load_data_file("teleport_network.json").get("platforms", [])
        except Exception as e:
            logger.debug(f"teleport_network.json: {e}")
            return []

    # ---- seeding ---------------------------------------------------

    def seed(self) -> int:
        # gated with the guild halls / adventurers so a few extra Location
        # markers don't perturb the general suite; the teleport tests clear it
        import os
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return 0
        if self._seeded or self.platforms:
            return 0
        self._seeded = True
        placed = 0
        for spec in self._specs():
            spot = self._site(spec.get("settlement", ""))
            if spot is None:
                continue
            self._plant(spec, spot)
            placed += 1
        # P37.2 — also link the notable PLACES OF INTEREST on the map
        for spec in self._landmark_specs():
            anchor = spec.pop("_anchor")
            if self._too_close_to_platform((anchor.x, anchor.y)):
                continue
            spot = self._walkable_near(anchor.x, anchor.y,
                                       anchor.width, anchor.height)
            if spot is None:
                continue
            self._plant(spec, spot)
            placed += 1
        if placed:
            logger.info(f"Seeded {placed} teleport platform(s).")
        return placed

    def _landmark_specs(self) -> List[dict]:
        """Places of interest beyond the towns (P37.2): every guild hall and
        castle, plus the nearest few ruins — so the Conclave links the whole
        map. Each spec carries an `_anchor` Location to plant beside."""
        from items.data_loader import load_data_file
        try:
            cfg = load_data_file("teleport_network.json").get("landmarks", {})
        except Exception:
            cfg = {}
        always = cfg.get("always", ["guildhall", "castle"])
        limited = cfg.get("limited", {"ruin": 3})
        kw = cfg.get("settlement_keywords",
                     ["village", "town", "hamlet", "city"])
        locs = getattr(self.engine.world, "locations", [])
        try:
            px, py = self.engine.player.position
        except Exception:
            px, py = 0, 0

        def _far(l):
            return abs(l.x - px) + abs(l.y - py)

        def _eligible(l):
            return (not l.get_property("waystone")
                    and l.width <= 30 and l.height <= 30)  # a place, not a region

        # settlements already covered by an authored data-spec platform
        covered = {(p.get("settlement") or "").lower().split()[0]
                   for p in self.platforms if p.get("settlement")}
        ints = getattr(self.engine, "interiors", {}) or {}

        def _is_settlement(l, nm):
            # a town area, NOT a building that merely carries the word (the
            # "Village Well", "Hamlet Chapel") — those are enterable (P16.2)
            return (any(w in nm for w in kw) and l.name not in ints
                    and not any(c and c in nm for c in covered))

        chosen, seen = [], set()
        for l in locs:            # always: guild halls, the castle, settlements
            props = l.properties or {}
            nm = l.name.lower()
            if _eligible(l) and l.name not in seen \
                    and (any(k in props for k in always) or _is_settlement(l, nm)):
                chosen.append(l)
                seen.add(l.name)
        for kind, n in limited.items():      # limited: the nearest N of a kind
            matches = sorted((l for l in locs
                              if _eligible(l) and l.name not in seen
                              and (l.properties or {}).get(kind) is not None),
                             key=_far)[:int(n)]
            for l in matches:
                chosen.append(l)
                seen.add(l.name)

        specs = []
        for l in chosen:
            slug = "".join(c.lower() if c.isalnum() else "_" for c in l.name)
            specs.append({"id": f"waystone_{slug}",
                          "name": f"{l.name} Waystone",
                          "settlement": l.name,
                          "legend": getattr(l, "description", "") or "",
                          "_anchor": l})
        return specs

    def _too_close_to_platform(self, pos, min_dist: int = 6) -> bool:
        for p in self.platforms:
            if abs(p["pos"][0] - pos[0]) + abs(p["pos"][1] - pos[1]) < min_dist:
                return True
        return False

    def _site(self, settlement: str) -> Optional[Tuple[int, int]]:
        locs = getattr(self.engine.world, "locations", [])
        anchors = [l for l in locs
                   if settlement and settlement.lower() in l.name.lower()
                   and any(k in l.name.lower()
                           for k in ("village", "hamlet", "town", "camp"))]
        anchors = anchors or [l for l in locs
                              if settlement.lower() in l.name.lower()]
        for a in anchors:
            spot = self._walkable_near(a.x, a.y, a.width, a.height)
            if spot is not None:
                return spot
        return None

    def _walkable_near(self, lx, ly, lw, lh) -> Optional[Tuple[int, int]]:
        wmap = self.engine.world.map
        cx, cy = lx + lw // 2, ly + lh // 2
        for r in range(max(lw, lh), max(lw, lh) + 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in _WALKABLE_BAD \
                            or (x, y) in wmap.characters \
                            or self.engine.world.get_location_at(x, y):
                        continue
                    return (x, y)
        return None

    def _plant(self, spec: dict, spot: Tuple[int, int]) -> None:
        from world.location import Location
        cx, cy = spot
        loc = Location(spec["name"], spec.get("legend", ""), cx, cy, 1, 1)
        loc.add_property("waystone", spec["id"])
        self.engine.world.add_location(loc)
        self.platforms.append({"id": spec["id"], "name": spec["name"],
                               "settlement": spec.get("settlement", ""),
                               "pos": [cx, cy]})

    # ---- access & travel -------------------------------------------

    def has_ring(self, player) -> bool:
        """The traveller has a teleport_access item — the Wayfarer's Ring — in
        the bag OR worn (it auto-equips into the ring slot)."""
        candidates = list(getattr(player, "inventory", []))
        try:
            from characters.equipment import equipped_items
            candidates += equipped_items(player)
        except Exception:
            pass
        for it in candidates:
            meta = getattr(it, "metadata", None) or {}
            if meta.get("teleport_access") \
                    or "teleport" in getattr(it, "id", ""):
                return True
        return False

    def platform_at(self, pos, r: int = STAND_RADIUS) -> Optional[dict]:
        """The waystone the player is standing on/beside, or None."""
        for p in self.platforms:
            px, py = p["pos"]
            if abs(px - pos[0]) <= r and abs(py - pos[1]) <= r:
                return p
        return None

    def destinations(self, from_id: str) -> List[dict]:
        """The other waystones a traveller can step to from `from_id`, NEAREST
        first (so the menu and `teleport_index` agree on order)."""
        here = next((p for p in self.platforms if p["id"] == from_id), None)
        others = [p for p in self.platforms if p["id"] != from_id]
        if here is not None:
            hx, hy = here["pos"]
            others.sort(key=lambda p: abs(p["pos"][0] - hx)
                        + abs(p["pos"][1] - hy))
        return others

    # ---- player-facing hook (P37.1) --------------------------------

    def can_use(self, player) -> bool:
        """True when `player` stands on a waystone AND holds a ring — the
        gate the hint bar and the E-key route on."""
        return (self.platform_at(player.position) is not None
                and self.has_ring(player))

    def overlay_lines(self) -> List[str]:
        """The Wayfarer's Waystone destination menu (numbered), for the GUI."""
        player = self.engine.player
        here = self.platform_at(player.position)
        if here is None:
            return ["You are not standing on a waystone."]
        if not self.has_ring(player):
            return ["You need a Wayfarer's Ring to use the waystones.",
                    "", "The Conclave's rings are common enough — ask in town."]
        dests = self.destinations(here["id"])
        lines = [f"You stand on the {here['name']}.",
                 "The Wayfarers' Conclave links it to:", ""]
        if not dests:
            lines.append("  (no other waystone is attuned yet)")
        for i, p in enumerate(dests[:9], start=1):
            lines.append(f"  [{i}] {p['name']}")
        if len(dests) > 9:
            lines.append(f"  … and {len(dests) - 9} more, farther off")
        lines += ["", "  [Esc] step back"]
        return lines

    def teleport_index(self, i: int) -> str:
        """Travel to the i-th (0-based) destination from the current waystone —
        the 1-9 key route. Player-facing line."""
        player = self.engine.player
        here = self.platform_at(player.position)
        if here is None:
            return "You must stand on a waystone to travel the network."
        dests = self.destinations(here["id"])
        if not (0 <= i < len(dests)):
            return "No such waystone to travel to."
        return self.teleport(dests[i]["id"])

    def teleport(self, dest_id: str) -> str:
        """The PLAYER steps from the waystone they're on to `dest_id`."""
        return self.teleport_actor(self.engine.player, dest_id, announce=True)

    def teleport_actor(self, actor, dest_id: str,
                       announce: bool = False) -> str:
        """Move ANY ring-bearing actor standing on a waystone to `dest_id` —
        the player, an away-hero, or an NPC all travel the same rails (P37.2)."""
        here = self.platform_at(actor.position)
        if here is None:
            return "You must stand on a waystone to travel the network."
        if not self.has_ring(actor):
            return "You need a Wayfarer's Ring to use the waystones."
        dest = next((p for p in self.platforms if p["id"] == dest_id), None)
        if dest is None or dest["id"] == here["id"]:
            return "No such waystone to travel to."
        wmap = self.engine.world.map
        land = self._safe_landing(tuple(dest["pos"]))
        wmap.remove_character(actor)
        actor.position = land
        wmap.place_character(actor, *land)
        if announce:
            self.engine.memory_manager.add_event(
                f"[Realm] You step through the {here['name']} and out of the "
                f"{dest['name']}.")
        return f"You arrive at the {dest['name']}."

    def _safe_landing(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        wmap = self.engine.world.map
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = pos[0] + dx, pos[1] + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in _WALKABLE_BAD \
                            or (x, y) in wmap.characters:
                        continue
                    return (x, y)
        return pos

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"seeded": self._seeded, "platforms": self.platforms}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        self._seeded = d.get("seeded", bool(d.get("platforms")))
        self.platforms = d.get("platforms", []) or []
