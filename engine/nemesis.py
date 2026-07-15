"""The Nemesis system (P19.6) — foes that remember you.

Shadow-of-Mordor's best idea, ported small: when you almost kill an ELITE
(the P19.5 champion), it may not die. It flees your blade, earns a name
and a title, and swears revenge — and nights later it comes back for you,
stronger and grander of title than before. Survive it enough times and
its luck runs out; cut it down for good and it passes into the
Legendarium as a grudge finally ended.

The loop, in four hooks:
  * DEATH'S DOOR — `intercept_death` runs before a monster is defeated. An
    elite may be BORN a nemesis (named, titled) and escape instead of
    dying; an existing nemesis with escapes left flees and RISES (power +
    a grander title); one out of escapes dies for real and becomes legend.
  * RETURN — `run_day` (nightly) brings a living, off-field nemesis back to
    hunt the player: a scaled champion tagged so the P19.3 pack brain and
    the P19.5 elite handling both apply.
Content-as-data (`data/nemesis.json`); the roster persists.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.nemesis")


class NemesisSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)
        self.nemeses: dict = {}          # nid -> record

    # ---- data ------------------------------------------------------

    def _cfg(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("nemesis.json")
        except Exception as e:
            logger.debug(f"nemesis.json: {e}")
            return {}

    def _title(self, power: int, cfg: dict) -> str:
        titles = cfg.get("titles", ["the Fierce"])
        return titles[min(max(power, 1) - 1, len(titles) - 1)]

    def _template_of(self, defender) -> str:
        parts = getattr(defender, "id", "").split("_")
        return "_".join(parts[1:-1]) if len(parts) > 2 else "bandit"

    # ---- death's door ----------------------------------------------

    def intercept_death(self, defender):
        """Before `defender.defeat()`. Return an escape MESSAGE if it lives
        on as a nemesis (removed from the field), else None (it dies) —
        recording a legend if a nemesis's last life just ended."""
        meta = getattr(defender, "metadata", {}) or {}
        nid = meta.get("nemesis_id")
        if nid is None and not meta.get("elite"):
            return None                  # an ordinary foe dies normally
        cfg = self._cfg()
        rec = self.nemeses.get(nid) if nid else None
        if rec is None:
            if self.rng.random() > cfg.get("birth_chance", 0.5):
                return None              # this elite simply dies
            rec = self._birth(defender, cfg)
        if rec["escapes_left"] <= 0:
            self._fall(rec)              # its luck is out — it dies for real
            return None
        rec["escapes_left"] -= 1
        rec["power"] += 1
        rec["title"] = self._title(rec["power"], cfg)
        rec["npc_id"] = None             # it has left the field
        self._flee(defender)
        self.engine.memory_manager.add_event(
            f"[Legend] {rec['name']} {rec['title']} flees your blade, "
            f"swearing revenge!")
        return (f"{rec['name']} {rec['title']} escapes, wounded but alive — "
                f"you have made an enemy.")

    def _birth(self, defender, cfg) -> dict:
        name = self.rng.choice(cfg.get("names", ["Grukk"]))
        nid = f"nem_{name}_{self.rng.randrange(1000000)}"
        rec = {
            "id": nid, "name": name, "title": self._title(1, cfg),
            "template": self._template_of(defender), "power": 1,
            "escapes_left": cfg.get("max_escapes", 2),
            "level": getattr(defender, "level", 3), "npc_id": None,
        }
        self.nemeses[nid] = rec
        defender.metadata["nemesis_id"] = nid
        return rec

    def _flee(self, defender) -> None:
        try:
            self.engine.world.map.remove_character(defender)
        except Exception:
            pass
        try:
            self.engine.npc_manager.remove_npc(defender.id)
        except Exception:
            pass

    def _fall(self, rec) -> None:
        """A nemesis dies for good — into the Legendarium."""
        try:
            from engine.dm_library import record_legend
            record_legend({
                "name": f"{rec['name']} {rec['title']}",
                "kind": "nemesis",
                "story": (f"A {rec['template']} that rose to hunt the realm, "
                          f"slain at last after {rec['power']} escapes."),
                "slain_by": self.engine.player.name,
                "day": self.engine.world.time // (24 * 60),
            })
        except Exception as e:
            logger.debug(f"Legend record: {e}")
        self.engine.memory_manager.add_event(
            f"[Legend] {rec['name']} {rec['title']} falls at last — "
            f"the grudge ends.")
        self.nemeses.pop(rec["id"], None)

    # ---- the return ------------------------------------------------

    def _on_field(self, rec) -> bool:
        nid = rec.get("npc_id")
        if not nid:
            return False
        n = self.engine.npc_manager.get_npc(nid)
        return n is not None and n.is_active()

    def run_day(self) -> int:
        cfg = self._cfg()
        returned = 0
        for rec in list(self.nemeses.values()):
            if self._on_field(rec):
                continue
            if self.rng.random() > cfg.get("return_chance", 0.5):
                continue
            if self._summon(rec, cfg):
                returned += 1
        return returned

    def _summon(self, rec, cfg) -> bool:
        pos = self._spot_near_player()
        if pos is None:
            return False
        from world.monsters import build_monster
        m = build_monster(rec["template"], pos)
        power = rec["power"]
        m.name = f"{rec['name']} {rec['title']}"
        m.level = rec["level"] + cfg.get("power_level_bonus", 2) * power
        m.max_hp = int(m.max_hp * (1 + cfg.get("power_hp_mult", 0.5) * power))
        m.hp = m.max_hp
        try:
            m.strength += 2 * power
        except Exception:
            pass
        m.metadata["nemesis_id"] = rec["id"]
        m.metadata["elite"] = True
        self.engine.npc_manager.add_npc(m)
        self.engine.world.map.place_character(m, *pos)
        rec["npc_id"] = m.id
        self.engine.memory_manager.add_event(
            f"[Legend] {m.name} returns to hunt you!")
        return True

    def _spot_near_player(self):
        from world.world_map import TerrainType
        wmap = self.engine.world.map
        px, py = self.engine.player.position
        for r in range(6, 11):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = px + dx, py + dy
                    if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                        continue
                    if wmap.terrain[y][x] in (TerrainType.WATER,
                                              TerrainType.MOUNTAIN,
                                              TerrainType.BUILDING,
                                              TerrainType.CAVE):
                        continue
                    if (x, y) in wmap.characters:
                        continue
                    return (x, y)
        return None

    # ---- persistence -----------------------------------------------

    def to_dict(self) -> dict:
        return {"nemeses": self.nemeses}

    def from_dict(self, d: dict) -> None:
        self.nemeses = (d or {}).get("nemeses", {}) or {}
