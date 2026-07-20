"""The NPC production loop (P16.2) — villages that actually make things.

Ported from autonomous_world's `npc_work` FSM, but adapted to our
architecture: instead of pathing every villager to a resource tile each
tick (a per-tick cost we forbid), the economy resolves ABSTRACTLY once
per game-day, alongside the faction ticker and market drift. Each
settlement keeps a STORE (a {item: qty} larder), and its resident
producers work it:

  * GATHERERS (woodcutter / forager / fisher / hunter …) pull raw
    materials into the store from their trade;
  * CRAFTERS (cook / alchemist / smith …) consume the inputs the store
    holds and turn them into goods — a fisher's catch becomes the cook's
    cooked fish, a forager's herbs the alchemist's potions.

Who works where comes for free from data already in the game: an NPC's
class maps (via the bond `CLASS_TEACHES`) to a skill, and P16.1's
supply chain maps that skill to a profession and its outputs. So a
village of villagers, a cleric and a wizard quietly turns logs, herbs
and fish into potions and meals, night after night, whether or not the
player is there to watch — and the log breathes an occasional line so
they can tell it's alive. Heuristic, no per-tick LLM. Persists its
stores. (Merchant arbitrage between settlements + feeding the surplus
into shop stock is P16.2b.)
"""

import logging
import random
from typing import Dict, List

logger = logging.getLogger("llm_rpg.production_loop")

GATHER_YIELD = 3        # raw units a gatherer pulls per day
CRAFT_CAP = 2           # goods a crafter makes per day, per good
STORE_CAP = 99          # a larder only holds so much
CARAVAN_LOAD = 4        # goods a caravan shifts between settlements/day

# T2.4 consumption — a settlement EATS its provisions daily, so the larder trends
# toward scarcity instead of sitting at cap and real shortages emerge (feeding the
# director shortage -> radiant fetch-quest chain).
_FOOD_KEYS = ("fish", "bread", "meat", "ration", "stew", "food", "apple",
              "cheese", "berries", "vegetable", "grain", "wheat", "loaf", "pie")
_STAPLE = "bread"       # the shortage a hungry town declares (a valid item id)


def _is_food(item_id) -> bool:
    k = (item_id or "").lower()
    return any(f in k for f in _FOOD_KEYS)
CARAVAN_MIN_GAP = 8     # only when the glut vs scarcity gap is real (P16.2b)
SETTLEMENT_KEYS = ("village", "hamlet", "town")


class ProductionSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.stores: Dict[str, Dict[str, int]] = {}

    # ---- lookup ----------------------------------------------------

    def _settlements(self) -> list:
        # a settlement is a named town area, NOT a building that merely
        # carries the word (the "Village Well", the "Hamlet Chapel") —
        # those are enterable, so they have an interior; towns don't.
        ints = getattr(self.engine, "interiors", {}) or {}
        return [l for l in self.engine.world.locations
                if any(k in l.name.lower() for k in SETTLEMENT_KEYS)
                and l.name not in ints]

    def store_of(self, settlement_name: str) -> Dict[str, int]:
        return self.stores.setdefault(settlement_name, {})

    def _nearest(self, settlements, pos):
        best, bd = None, 1e9
        for s in settlements:
            cx, cy = s.center()
            d = (cx - pos[0]) ** 2 + (cy - pos[1]) ** 2
            if d < bd:
                best, bd = s, d
        return best

    def _producers_by_settlement(self, settlements) -> Dict[str, Dict[str, list]]:
        """{settlement_name: {profession: [npcs]}} — each civilian NPC
        assigned to its nearest settlement, class→skill→profession."""
        from engine.bonds import CLASS_TEACHES
        from engine import production as pr
        out: Dict[str, Dict[str, list]] = {s.name: {} for s in settlements}
        if not settlements:
            return out
        for npc in self.engine.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            meta = getattr(npc, "metadata", {}) or {}
            if meta.get("player_char"):
                continue
            cls = getattr(npc.character_class, "value", "")
            # occupation follows the WORKPLACE first (P16.3): a villager
            # living in a farmhouse is a farmer, not a woodcutter-by-class
            prof = (self._building_profession(npc)
                    or pr.profession_for_skill(CLASS_TEACHES.get(cls, "")))
            if not prof:
                continue
            s = self._nearest(settlements, npc.position)
            out[s.name].setdefault(prof, []).append(npc)
        return out

    def _building_profession(self, npc) -> str:
        """The trade an NPC's home building implies (P16.3): by its
        blueprint kind, or by its furniture (an anvil room is a smithy)."""
        home = getattr(npc, "home_location", "")
        if not home:
            return None
        from world import building_types as bt
        from world.blueprints import blueprint_for_location
        bp = blueprint_for_location(home)
        prof = bt.profession_of_kind(getattr(bp, "kind", "") if bp else "")
        if prof:
            return prof
        inter = (getattr(self.engine, "interiors", {}) or {}).get(home)
        if inter is not None:
            kind = bt.classify_interior(inter)
            if kind:
                return bt.profession_of_kind(kind)
        return None

    # ---- the daily step --------------------------------------------

    def run_day(self) -> List[str]:
        from engine import production as pr
        settlements = self._settlements()
        by_s = self._producers_by_settlement(settlements)
        summaries = []
        for s in settlements:
            profs = by_s.get(s.name, {})
            if not profs:
                continue
            store = self.store_of(s.name)
            made = self._work(pr, store, profs)
            if self._consume(store, profs):     # T2.4 the town eats; short → shortage
                self._maybe_shortage()
            if made:
                summaries.append((s.name, made))
        moves = self._arbitrage(settlements)     # P16.2b caravans
        notes = self._announce(summaries)
        self._announce_caravan(moves)
        return notes

    def _consume(self, store, profs) -> bool:
        """T2.4: the settlement EATS — daily demand drains provisions so the larder
        trends toward scarcity instead of sitting at STORE_CAP. Returns True if the
        town ran short of food (an emergent hunger that pushes a real shortage)."""
        pop = sum(len(v) for v in profs.values())
        if pop <= 0:
            return False
        need = max(1, pop // 2)                 # folk eat ~1 per 2 people/day
        food = sorted((k for k in list(store) if _is_food(k)),
                      key=lambda k: -store.get(k, 0))
        for k in food:
            if need <= 0:
                break
            take = min(store.get(k, 0), need)
            store[k] = store.get(k, 0) - take
            need -= take
            if store[k] <= 0:
                del store[k]
        return need > 0                          # still hungry → a real shortfall

    def _maybe_shortage(self) -> None:
        """A hungry settlement pushes a real food shortage → prices up + a radiant
        fetch quest, rate-limited so a lean spell doesn't spam."""
        d = getattr(self.engine, "world_director", None)
        if d is None:
            return
        try:
            now = self.engine.world.time
            if d.shortages.get(_STAPLE, 0) > now:    # a bread shortage is live
                return
            msg = d._apply_shortage({"item_id": _STAPLE})
            if msg:
                self.engine.memory_manager.add_event("[Realm] " + msg)
        except Exception:
            pass

    def _arbitrage(self, settlements) -> List[tuple]:
        """P16.2b: a caravan carries a settlement's GLUT of a good to
        where it's scarce — plenty flows to want, the merchant's trade.
        Redistributes the stores; returns the moves for the announcer."""
        if len(settlements) < 2:
            return []
        goods = set()
        for s in settlements:
            goods |= set(self.store_of(s.name))
        moves = []
        for good in sorted(goods):
            rich = max(settlements,
                       key=lambda s: self.store_of(s.name).get(good, 0))
            poor = min(settlements,
                       key=lambda s: self.store_of(s.name).get(good, 0))
            if rich is poor:
                continue
            have = self.store_of(rich.name).get(good, 0)
            want = self.store_of(poor.name).get(good, 0)
            if have - want < CARAVAN_MIN_GAP:
                continue
            load = min(CARAVAN_LOAD, (have - want) // 2)
            if load <= 0:
                continue
            self.store_of(rich.name)[good] = have - load
            self.store_of(poor.name)[good] = min(STORE_CAP, want + load)
            moves.append((good, load, rich.name, poor.name))
        return moves

    def _announce_caravan(self, moves) -> None:
        """One quiet caravan line a day (the state moved either way)."""
        if not moves or self.rng.random() > 0.5:
            return
        good, load, frm, to = self.rng.choice(moves)
        label = good.replace("_", " ")
        self.engine.memory_manager.add_event(
            f"[Realm] A caravan carried {load} {label} from {frm} to {to}.")

    def _work(self, pr, store, profs) -> Dict[str, int]:
        """Gather raws, then craft goods; returns what was CRAFTED."""
        # 1. gatherers fill the larder
        for prof, npcs in profs.items():
            raw = pr.primary_raw(prof)
            if raw is None:
                continue
            store[raw] = min(STORE_CAP,
                             store.get(raw, 0) + GATHER_YIELD * len(npcs))
        # 2. crafters consume inputs into goods
        crafted: Dict[str, int] = {}
        for prof, npcs in profs.items():
            for good in pr.producers(prof):
                if not pr.is_crafted(good):
                    continue
                inputs = pr.inputs_of(good)
                if not inputs:
                    continue
                makeable = min((store.get(i, 0) // n
                                for i, n in inputs.items()), default=0)
                makeable = min(makeable, CRAFT_CAP * len(npcs),
                               STORE_CAP - store.get(good, 0))
                if makeable <= 0:
                    continue
                for i, n in inputs.items():
                    store[i] -= n * makeable
                store[good] = store.get(good, 0) + makeable
                crafted[good] = crafted.get(good, 0) + makeable
        return crafted

    def _announce(self, summaries) -> List[str]:
        """One quiet line a day, so the living economy is felt not spammed."""
        if not summaries or self.rng.random() > 0.5:
            return []
        name, made = self.rng.choice(summaries)
        good, qty = max(made.items(), key=lambda kv: kv[1])
        label = good.replace("_", " ")
        line = f"{name}'s workshops turned out {qty} {label}."
        self.engine.memory_manager.add_event(f"[Realm] {line}")
        return [line]

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"stores": {k: dict(v) for k, v in self.stores.items()}}

    def from_dict(self, d: dict) -> None:
        self.stores = {k: dict(v)
                       for k, v in (d or {}).get("stores", {}).items()}
