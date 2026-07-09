"""Nightly world director (P3.7) — LLM-as-director, not LLM-per-NPC.

Once per game night, ONE call reads the day's events and emits 1-3
structured world events that the deterministic systems act out:

- rumor {text}                — joins the gossip pool + morning announce
- shortage {item_id}          — that item costs x1.5 in shops for a day
- caravan {}                  — a random merchant restocks + purse boost
- monster_sighting {template} — a monster spawns in the wilderness
- feud {npc_a, npc_b}         — two NPCs' mutual relationship drops 20

Heuristic mode rolls 1-2 of the same events from templates, so the world
moves overnight on every backend. Junk LLM output falls back to the
heuristic roll. State (rumors, shortages) persists via to_dict/from_dict.
"""

import json
import logging
import random
import re
from typing import Dict, List

logger = logging.getLogger("llm_rpg.director")

MAX_RUMORS = 5
SHORTAGE_MINUTES = 24 * 60
SHORTAGE_MARKUP = 1.5

DIRECTOR_SYSTEM = """You are the world director of a fantasy RPG village region.
Given today's events, emit 1-3 plausible overnight developments as ONLY a JSON list:
[{"type": "rumor", "text": "<one sentence villagers might repeat>"},
 {"type": "shortage", "item_id": "<id from KNOWN ITEMS>"},
 {"type": "caravan"},
 {"type": "monster_sighting", "template": "<id from KNOWN MONSTERS>"},
 {"type": "feud", "npc_a": "<id>", "npc_b": "<id>"}]
Ground developments in today's events. Use only listed ids. No commentary."""


class WorldDirector:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.rumors: List[str] = []
        self.shortages: Dict[str, int] = {}   # item_id -> expiry time

    # ---- nightly run -----------------------------------------------------

    def run_night(self) -> List[str]:
        """Generate + apply overnight events. Returns morning lines."""
        events = None
        iface = getattr(self.engine, "llm_interface", None)
        if iface is not None and getattr(iface, "provider_name",
                                         "heuristic") != "heuristic":
            events = self._llm_events()
        if not events:
            events = self._heuristic_events()

        notes = []
        for event in events[:3]:
            note = self._apply(event)
            if note:
                notes.append(note)
        for note in notes:
            self.engine.memory_manager.add_event(
                f"[Overnight] {note}")
        return notes

    # ---- generation --------------------------------------------------------

    def _llm_events(self) -> List[dict]:
        from items.item_registry import all_item_ids
        from world.monsters import MONSTER_TEMPLATES
        from characters.npc_presets import NPC_SPECS
        day_log = "\n".join(
            self.engine.memory_manager.get_recent_history(count=15))
        prompt = (
            f"TODAY'S EVENTS\n{day_log}\n\n"
            f"KNOWN ITEMS: {all_item_ids()[:40]}\n"
            f"KNOWN MONSTERS: {list(MONSTER_TEMPLATES)}\n"
            f"KNOWN NPCS: {list(NPC_SPECS)}\n\n"
            f"Emit tonight's developments.")
        try:
            raw = self.engine.llm_interface.generate_response(
                prompt, DIRECTOR_SYSTEM, max_tokens=300, temperature=0.9)
            m = re.search(r"\[.*\]", raw or "", re.DOTALL)
            if not m:
                return []
            data = json.loads(m.group(0))
            return [e for e in data if isinstance(e, dict)]
        except Exception as e:
            logger.debug(f"Director LLM failed: {e}")
            return []

    def _heuristic_events(self) -> List[dict]:
        from world.monsters import encounter_table
        from characters.gossip import STATIC_GOSSIP
        rollable = [
            {"type": "rumor", "text": self.rng.choice(STATIC_GOSSIP)},
            {"type": "shortage",
             "item_id": self.rng.choice(["ale", "bread", "arrow",
                                         "potion", "bandage"])},
            {"type": "caravan"},
            {"type": "monster_sighting",
             "template": self.rng.choice(
                 [tid for tid, _ in encounter_table()])},
        ]
        count = self.rng.randint(1, 2)
        return self.rng.sample(rollable, count)

    # ---- application ----------------------------------------------------------

    def _apply(self, event: dict) -> str:
        etype = event.get("type", "")
        try:
            if etype == "rumor":
                text = str(event.get("text", "")).strip()
                if not text:
                    return ""
                self.rumors.append(text)
                del self.rumors[:-MAX_RUMORS]
                return f"Word spreads: {text}"
            if etype == "shortage":
                return self._apply_shortage(event)
            if etype == "caravan":
                return self._apply_caravan()
            if etype == "monster_sighting":
                return self._apply_sighting(event)
            if etype == "feud":
                return self._apply_feud(event)
        except Exception as e:
            logger.debug(f"Director apply error ({etype}): {e}")
        return ""

    def _apply_shortage(self, event: dict) -> str:
        from items.item_registry import ITEM_REGISTRY
        item_id = str(event.get("item_id", ""))
        item = ITEM_REGISTRY.get(item_id)
        if item is None:
            return ""
        self.shortages[item_id] = \
            self.engine.world.time + SHORTAGE_MINUTES
        return (f"A {item.name} shortage grips the region — "
                f"prices are up.")

    def _apply_caravan(self) -> str:
        merchants = [n for n in self.engine.npc_manager.npcs.values()
                     if getattr(n.character_class, "value", "") ==
                     "merchant" and n.is_active()]
        if not merchants:
            return ""
        lucky = self.rng.choice(merchants)
        cat = self.engine.shop_manager.catalog_for(lucky)
        self.engine.shop_manager._stock(cat, lucky)
        cat.gold += 100
        return (f"A trade caravan reached {lucky.name} — "
                f"fresh stock and full purses.")

    def _apply_sighting(self, event: dict) -> str:
        from world.monsters import MONSTER_TEMPLATES, build_monster
        template = str(event.get("template", ""))
        if template not in MONSTER_TEMPLATES:
            return ""
        pos = self._wilderness_spot()
        if pos is None:
            return ""
        monster = build_monster(template, pos)
        self.engine.npc_manager.add_npc(monster)
        self.engine.world.map.place_character(monster, *pos)
        return (f"Travelers report a {monster.name} prowling "
                f"the wilds.")

    def _apply_feud(self, event: dict) -> str:
        a = self.engine.npc_manager.get_npc(str(event.get("npc_a", "")))
        b = self.engine.npc_manager.get_npc(str(event.get("npc_b", "")))
        if a is None or b is None or a.id == b.id:
            return ""
        a.modify_relationship(b.id, -20)
        b.modify_relationship(a.id, -20)
        return f"{a.name} and {b.name} had a falling-out, folk say."

    def _wilderness_spot(self):
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        for _ in range(60):
            x = self.rng.randint(1, wmap.width - 2)
            y = self.rng.randint(1, wmap.height - 2)
            if wmap.get_terrain_at(x, y) in (TerrainType.GRASS,
                                             TerrainType.FOREST) and \
                    abs(x - px) + abs(y - py) > 12:
                return (x, y)
        return None

    # ---- queries -----------------------------------------------------------

    def shortage_multiplier(self, item_id: str) -> float:
        expiry = self.shortages.get(item_id, 0)
        return SHORTAGE_MARKUP if self.engine.world.time < expiry else 1.0

    # ---- persistence -------------------------------------------------------

    def to_dict(self):
        return {"rumors": list(self.rumors),
                "shortages": dict(self.shortages)}

    def from_dict(self, d):
        self.rumors = list(d.get("rumors", []))[-MAX_RUMORS:]
        self.shortages = {k: int(v)
                          for k, v in d.get("shortages", {}).items()}
