"""Townsfolk ventures (George: the adventurer NPCs already roam/fight/quest —
extend a LIFE beyond the work-routine to ORDINARY folk too).

The world's adventurers (`AdventurerSystem`) live restless lives; the baker,
the merchant, the wandering bard mostly work their schedules and go home. This
gives them the OCCASIONAL trip: now and then a townsperson leaves on a VENTURE
with a mundane, story-shaped PURPOSE — visit kin in another settlement, a
pilgrimage to a shrine, a trading run, a bout of wanderlust to some ruin — walks
the roads there (fleeing danger, for a baker is no hero), lingers, and comes
home with tales. `[Town]` beats mark the going and the return.

Deliberately BOUNDED so the town never empties: at most `max_venturing` folk are
away at once, and only a per-day chance sends anyone out. A venturer is driven
here (cautious travel via `agent_nav`, NOT the fighter brain), skipped by the
ambient NPC AI (`metadata["venturing"]`), and resumes its schedule on return.
State rides the NPC save (`metadata["venture"]`); tuning is data
(`data/townsfolk_venture.json`). No per-tick LLM.
"""

import logging
import random
from typing import List, Optional, Tuple

from world.world_map import TerrainType

logger = logging.getLogger("llm_rpg.townsfolk_venture")

_WALKABLE = {TerrainType.GRASS, TerrainType.FOREST, TerrainType.ROAD,
             TerrainType.BRIDGE, TerrainType.FARMLAND}


def _dist(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class TownsfolkVentureSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.venturing: set = set()      # ids currently away on a venture

    # ---- config ----------------------------------------------------

    def _cfg(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("townsfolk_venture.json") or {}
        except Exception as e:
            logger.debug(f"townsfolk_venture.json: {e}")
            return {}

    # ---- nightly: start a few ventures -----------------------------

    def run_day(self) -> None:
        import os
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return
        cfg = self._cfg()
        # drop anyone whose venture ended or whose Character is gone
        self.venturing = {i for i in self.venturing
                          if self._active(i)
                          and self._npc(i).metadata.get("venture")}
        cap = int(cfg.get("max_venturing", 3))
        if len(self.venturing) >= cap:
            return
        if self.rng.random() > float(cfg.get("daily_start_chance", 0.6)):
            return
        picks = self._eligible(cfg)
        self.rng.shuffle(picks)
        for npc in picks:
            if len(self.venturing) >= cap:
                break
            if self._start(npc, cfg):
                self.venturing.add(npc.id)

    # ---- per-turn: drive the venturers -----------------------------

    def run_turn(self) -> None:
        import os
        if os.environ.get("LLM_RPG_NO_ADVENTURERS"):
            return
        cfg = self._cfg()
        driven = 0
        for nid in list(self.venturing):
            if driven >= int(cfg.get("max_driven", 3)):
                break
            npc = self._npc(nid)
            if npc is None or not npc.is_active() \
                    or not npc.metadata.get("venture"):
                self.venturing.discard(nid)
                continue
            try:
                self._drive(npc, cfg)
                driven += 1
            except Exception as e:
                logger.debug(f"Drive venturer {nid}: {e}")

    # ---- eligibility & start ---------------------------------------

    def _eligible(self, cfg: dict) -> List:
        classes = set(cfg.get("classes",
                              ["villager", "merchant", "bard", "noble"]))
        party = getattr(getattr(self.engine, "companion_manager", None),
                        "party", {})
        out = []
        for npc in self.engine.npc_manager.npcs.values():
            m = getattr(npc, "metadata", {}) or {}
            if self._class_of(npc) not in classes:
                continue
            if (m.get("player_char") or m.get("adventurer")
                    or m.get("wildlife") or m.get("arena_fighter")
                    or m.get("zone_bound") or m.get("venture")
                    or m.get("mayor") or m.get("quest_giver")
                    or m.get("adventure")            # adventure cast stays put
                    or m.get("hire") or m.get("shopkeeper_essential")):
                continue
            if npc.id in party or npc.id in self.venturing:
                continue
            if not npc.is_active():
                continue
            if self._home_spot(npc) is None:
                continue
            out.append(npc)
        return out

    def _start(self, npc, cfg: dict) -> bool:
        home = self._home_spot(npc)
        if home is None:
            return False
        purposes = cfg.get("purposes", [])
        if not purposes:
            return False
        purpose = self.rng.choice(purposes)
        dest = self._destination(home, purpose, cfg)
        if dest is None:
            return False
        if _dist(home, tuple(dest[0])) < int(cfg.get("min_trip", 12)):
            return False                     # no degenerate on-the-doorstep trip
        # leave the doorstep: if stuck on a building tile, step outside
        if not self._is_outdoor(npc.position):
            if not self._step_outside(npc, home):
                return False
        npc.metadata["venture"] = {
            "purpose": purpose["id"], "dest": list(dest[0]),
            "dest_name": dest[1], "home": list(home),
            "phase": "out", "linger": 0, "turns": 0,
        }
        npc.metadata["venturing"] = True
        self._beat(purpose.get("out", "{name} sets out for {dest}."),
                   npc, dest[1])
        return True

    # ---- driving ---------------------------------------------------

    def _drive(self, npc, cfg: dict) -> None:
        from engine import agent_nav
        v = npc.metadata["venture"]
        v["turns"] = v.get("turns", 0) + 1
        # a venture ALWAYS ends: past the cap the townsperson has "come home"
        # (even if the exact doorstep is blocked/occupied) — never a wanderer
        # stuck forever oscillating near a tile it can't quite reach
        if v["turns"] > int(cfg.get("max_turns", 400)):
            self._end(npc)
            return
        goal = tuple(v["dest"]) if v["phase"] != "home" else tuple(v["home"])

        trail = npc.metadata.setdefault("_venture_trail", [])
        threat = self._nearest_threat(npc, int(cfg.get("flee_radius", 5)))
        if threat is not None:
            step = agent_nav.flee_step(self.engine, npc, threat, avoid=trail)
            if step is None:                 # cornered — a civilian defends
                self._defend(npc, threat)
                return
        else:
            step = agent_nav.safe_step(self.engine, npc, goal, avoid=trail)

        if step and step != (0, 0):
            x, y = npc.position
            self.engine.world.map.move_character(npc, x + step[0], y + step[1])
            trail.append(tuple(npc.position))
            if len(trail) > 6:
                del trail[:-6]

        self._advance_phase(npc, v, cfg)

    def _advance_phase(self, npc, v: dict, cfg: dict) -> None:
        pos = tuple(npc.position)
        if v["phase"] == "out" and _dist(pos, tuple(v["dest"])) <= 2:
            v["phase"] = "linger"
        elif v["phase"] == "linger":
            v["linger"] = v.get("linger", 0) + 1
            if v["linger"] >= int(cfg.get("linger_turns", 6)):
                v["phase"] = "home"
        elif v["phase"] == "home" and _dist(pos, tuple(v["home"])) <= 2:
            self._end(npc)

    def _end(self, npc) -> None:
        v = npc.metadata.pop("venture", None)
        npc.metadata.pop("venturing", None)
        npc.metadata.pop("_venture_trail", None)
        self.venturing.discard(npc.id)
        if v:
            purpose = next((p for p in self._cfg().get("purposes", [])
                            if p["id"] == v.get("purpose")), {})
            self._beat(purpose.get("back", "{name} comes home from {dest}."),
                       npc, v.get("dest_name", "afar"))

    def _defend(self, npc, threat) -> None:
        cs = getattr(self.engine, "combat_system", None)
        wmap = self.engine.world.map
        foe = wmap.characters.get(tuple(threat))
        if cs is not None and foe is not None and _dist(npc.position,
                                                        threat) <= 1:
            try:
                cs.npc_attack(npc, foe.id)     # resolved via find_character
            except Exception:
                pass

    # ---- destinations ----------------------------------------------

    def _destination(self, home, purpose: dict,
                     cfg: dict) -> Optional[Tuple[Tuple[int, int], str]]:
        lo, hi = int(cfg.get("min_trip", 12)), int(cfg.get("max_trip", 110))
        prefer = [w.lower() for w in purpose.get("prefer", [])]
        skip = ("well", "stable", "sign", "board", "gate", "tower",
                "colosseum", "arena")
        far, any_far = [], []
        for loc in getattr(self.engine.world, "locations", []):
            name = getattr(loc, "name", "")
            if not name or any(w in name.lower() for w in skip):
                continue
            spot = self._loc_spot(loc)
            if spot is None:
                continue
            d = _dist(home, spot)
            if not (lo <= d <= hi):
                continue
            any_far.append((spot, name))
            if prefer and any(w in name.lower() for w in prefer):
                far.append((spot, name))
        pool = far or any_far
        if pool:
            return self.rng.choice(pool)
        return self._wild_spot(home, lo, hi)

    def _loc_spot(self, loc) -> Optional[Tuple[int, int]]:
        cx = getattr(loc, "x", None)
        cy = getattr(loc, "y", None)
        if cx is None or cy is None:
            return None
        return self._nearest_outdoor((int(cx), int(cy)))

    def _wild_spot(self, home, lo: int,
                   hi: int) -> Optional[Tuple[Tuple[int, int], str]]:
        wmap = self.engine.world.map
        for _ in range(120):
            x = self.rng.randint(1, wmap.width - 2)
            y = self.rng.randint(1, wmap.height - 2)
            if wmap.terrain[y][x] in _WALKABLE and lo <= _dist(home, (x, y)) <= hi:
                return ((x, y), "the open country")
        return None

    # ---- placement helpers -----------------------------------------

    def _home_spot(self, npc) -> Optional[Tuple[int, int]]:
        if self._is_outdoor(npc.position):
            return tuple(npc.position)
        return self._nearest_outdoor(tuple(npc.position))

    def _nearest_outdoor(self, pos) -> Optional[Tuple[int, int]]:
        """The closest walkable, UNOCCUPIED overworld tile — where a townsperson
        can actually stand once it steps off its doorstep."""
        wmap = self.engine.world.map
        cx, cy = pos
        for r in range(0, 6):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < wmap.width and 0 <= y < wmap.height \
                            and wmap.terrain[y][x] in _WALKABLE \
                            and (x, y) not in wmap.characters:
                        return (x, y)
        return None

    def _step_outside(self, npc, home) -> bool:
        return bool(self.engine.world.map.move_character(npc, home[0], home[1]))

    def _is_outdoor(self, pos) -> bool:
        wmap = self.engine.world.map
        x, y = pos
        return (0 <= x < wmap.width and 0 <= y < wmap.height
                and wmap.terrain[y][x] in _WALKABLE)

    def _nearest_threat(self, npc, r: int) -> Optional[Tuple[int, int]]:
        from engine.agent_sense import _is_hostile
        wmap = self.engine.world.map
        best, bd = None, r + 1
        for other in self.engine.npc_manager.npcs.values():
            if other is npc or not other.is_active() or not _is_hostile(other):
                continue
            d = _dist(npc.position, other.position)
            if d <= r and d < bd and tuple(other.position) in wmap.characters:
                best, bd = tuple(other.position), d
        return best

    # ---- misc ------------------------------------------------------

    def _class_of(self, npc) -> str:
        return getattr(getattr(npc, "character_class", None), "value", "")

    def _npc(self, nid: str):
        return self.engine.npc_manager.npcs.get(nid)

    def _active(self, nid: str) -> bool:
        n = self._npc(nid)
        return n is not None and n.is_active()

    def _beat(self, template: str, npc, dest_name: str) -> None:
        try:
            line = template.format(name=npc.name, dest=dest_name,
                                   home="home")
            self.engine.memory_manager.add_event("[Town] " + line)
        except Exception:
            pass

    def venturing_ids(self) -> List[str]:
        return sorted(self.venturing)

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"venturing": sorted(self.venturing)}

    def from_dict(self, d: dict) -> None:
        d = d or {}
        # the venture state rides each NPC's metadata; rebuild the live set
        # from the ids that still carry an active venture
        self.venturing = {i for i in d.get("venturing", [])
                          if self._active(i)
                          and self._npc(i).metadata.get("venture")}
