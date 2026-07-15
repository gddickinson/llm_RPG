"""Off-screen faction ticker (P5.4, the Kenshi lesson).

Factions have STRENGTH (fighting power) and STORES (wealth/supplies),
0-100. Once per game-day one dice-resolved event moves those numbers —
raids, patrols, caravans, incursions, harvests — whether or not the
player is watching. Consequences are real:

- brigand strength scales bandit encounter weight (strong gangs roam);
- villager stores dropping low pushes a food shortage + rumor through
  the world director (prices rise, a radiant fetch quest follows);
- every event becomes a rumor NPCs repeat.

State persists via to_dict/from_dict.
"""

import logging
import random
from typing import Dict, List

logger = logging.getLogger("llm_rpg.faction_ticker")

DEFAULT_STATE = {
    "villagers": {"strength": 50, "stores": 55},
    "guards": {"strength": 55, "stores": 50},
    "merchants": {"strength": 40, "stores": 60},
    "brigands": {"strength": 45, "stores": 40},
    "monsters": {"strength": 50, "stores": 30},
}

LOW_STORES = 30
STRONG = 65


class FactionTicker:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.state: Dict[str, Dict[str, int]] = {
            k: dict(v) for k, v in DEFAULT_STATE.items()}

    # ---- daily tick ------------------------------------------------------

    def run_day(self) -> List[str]:
        event = self.rng.choice([
            self._brigand_raid, self._guard_patrol, self._trade_caravan,
            self._monster_incursion, self._good_harvest,
        ])
        notes = event()
        self._clamp()
        consequences = self._consequences()
        for note in notes + consequences:
            self.engine.memory_manager.add_event(f"[Realm] {note}")
            self._push_rumor(note)
        return notes + consequences

    # ---- events (dice-resolved) ---------------------------------------------

    def _roll(self) -> int:
        return self.rng.randint(1, 10)

    @staticmethod
    def _casualty_hit(ratio: float) -> int:
        """Strength shed ~= the share of the army lost in the fight,
        bounded so one skirmish can't gut a faction (P17.8)."""
        return min(10, max(1, int(round((1.0 - ratio) * 12))))

    def _clash(self, atk: str, dfn: str, terrain: str = "plains") -> dict:
        """P17.8: settle an off-screen clash between two factions with
        the real Lanchester resolver, dressing each side's strength as an
        army. The caller reads `winner` and applies its own store/flavor
        effects; strength losses scale with the mauling via _casualty_hit."""
        from engine.faction_battle import resolve_raid
        return resolve_raid(atk, self.state[atk]["strength"],
                            dfn, self.state[dfn]["strength"],
                            self.rng, terrain=terrain)

    def _brigand_raid(self) -> List[str]:
        # P17.8: the real resolver settles it, not a die — a brigand
        # mounted rush can founder on the guards' spear line.
        res = self._clash("brigands", "guards")
        if res["winner"] == "brigands":
            self.state["villagers"]["stores"] -= 8
            self.state["brigands"]["stores"] += 8
            self.state["brigands"]["strength"] += 2
            self.state["guards"]["strength"] -= \
                self._casualty_hit(res["def_ratio"])
            return ["Brigands raided an outlying farmstead and got away "
                    "with the stores."]
        self.state["brigands"]["strength"] -= \
            self._casualty_hit(res["atk_ratio"])
        self.state["guards"]["strength"] += 2
        self._spawn_raider()
        return ["The guard repelled a brigand raid on the farmsteads."]

    def _spawn_raider(self) -> bool:
        """A raid leaves a straggler near a guard's beat — the P7.1
        conflict system makes the ensuing patrol fight visible."""
        try:
            from world.monsters import build_monster
            from engine.npc_conflict import _cls, GUARD_CLASSES
            guards = [n for n in self.engine.npc_manager.npcs.values()
                      if n.is_active() and _cls(n) in GUARD_CLASSES]
            if not guards:
                return False
            guard = self.rng.choice(guards)
            gx, gy = guard.position
            px, py = self.engine.player.position
            wmap = self.engine.world.map
            for dx, dy in ((5, 0), (-5, 0), (0, 5), (0, -5), (4, 4)):
                x, y = gx + dx, gy + dy
                if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                    continue
                if abs(x - px) + abs(y - py) < 6:
                    continue
                if wmap.get_character_at(x, y) is not None:
                    continue
                raider = build_monster("bandit", (x, y))
                self.engine.npc_manager.add_npc(raider)
                wmap.place_character(raider, x, y)
                self.engine.memory_manager.add_event(
                    "[Realm] A raider straggler was seen skulking "
                    "near the watch.")
                return True
        except Exception:
            pass
        return False

    def _guard_patrol(self) -> List[str]:
        # P17.8: the patrol falls on a brigand camp — resolve the clash.
        res = self._clash("guards", "brigands")
        if res["winner"] == "guards":
            self.state["brigands"]["strength"] -= \
                self._casualty_hit(res["def_ratio"])
            return ["A guard patrol broke up a brigand camp on the "
                    "east road."]
        self.state["guards"]["strength"] -= \
            self._casualty_hit(res["atk_ratio"])
        return ["A guard patrol returned empty-handed and footsore."]

    def _trade_caravan(self) -> List[str]:
        if self._roll() + self.state["brigands"]["strength"] // 20 <= 7:
            self.state["merchants"]["stores"] += 7
            self.state["villagers"]["stores"] += 4
            return ["A trade caravan arrived safely; the markets are "
                    "well stocked."]
        self.state["merchants"]["stores"] -= 6
        self.state["brigands"]["stores"] += 6
        return ["A trade caravan was waylaid on the road — its goods "
                "are gone."]

    def _monster_incursion(self) -> List[str]:
        # P17.8: beasts out of the wilds (forest) fall on the village
        # militia — the resolver weighs terror & charge against numbers.
        res = self._clash("monsters", "villagers", terrain="forest")
        if res["winner"] == "monsters":
            self.state["monsters"]["strength"] += 2
            self.state["villagers"]["stores"] -= 4
            self.state["villagers"]["strength"] -= \
                self._casualty_hit(res["def_ratio"])
            return ["Beasts pressed in from the wilds; shepherds count "
                    "their losses."]
        self.state["monsters"]["strength"] -= \
            self._casualty_hit(res["atk_ratio"])
        return ["Hunters drove the beasts back from the pastures."]

    def _good_harvest(self) -> List[str]:
        self.state["villagers"]["stores"] += 6
        self.state["merchants"]["stores"] += 3
        return ["A good week in the fields — granaries are fuller."]

    # ---- consequences ----------------------------------------------------------

    def _consequences(self) -> List[str]:
        out = []
        if self.state["villagers"]["stores"] < LOW_STORES:
            try:
                director = self.engine.world_director
                item = self.rng.choice(["bread", "ale"])
                if director.shortage_multiplier(item) == 1.0:
                    director._apply({"type": "shortage",
                                     "item_id": item})
                    out.append("Food runs short in the villages — "
                               "prices are climbing.")
            except Exception:
                pass
        if self.state["brigands"]["strength"] > STRONG:
            out.append("The brigand bands grow bold; travelers "
                       "arm themselves.")
        return out

    def bandit_weight_multiplier(self) -> float:
        """Strong gangs roam: scales the bandit encounter weight."""
        s = self.state["brigands"]["strength"]
        if s > STRONG:
            return 2.0
        if s < 25:
            return 0.5
        return 1.0

    def _push_rumor(self, note: str) -> None:
        try:
            director = self.engine.world_director
            director.rumors.append(note)
            del director.rumors[:-5]
        except Exception:
            pass

    def _clamp(self) -> None:
        for fac in self.state.values():
            for key in fac:
                fac[key] = max(5, min(100, fac[key]))

    # ---- persistence -----------------------------------------------------------

    def to_dict(self):
        return {"state": {k: dict(v) for k, v in self.state.items()}}

    def from_dict(self, d):
        loaded = d.get("state", {})
        for fac, vals in DEFAULT_STATE.items():
            self.state[fac] = dict(vals)
            self.state[fac].update(loaded.get(fac, {}))
