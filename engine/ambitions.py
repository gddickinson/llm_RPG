"""Ambitions that drive action (P20.1).

Every NPC is born with one to three goal strings — "earn enough to retire
comfortably", "find romance or companionship", "avenge a past wrong" — but
they were pure decoration: shown in a prompt, never acted upon. This makes
them MOVE the world, a little, every night.

Each NPC's goal is matched (by keyword, from `data/ambitions.json`) to an
AMBITION — wealth, romance, mastery, vengeance, escape. Every night the
NPC makes quiet progress toward it, and when the progress fills, the
ambition is REALISED with a real, persistent effect and a `[Realm]` beat
the gossip system can carry: a merchant prospers and retires, two lonely
souls become sweethearts (an emergent couple — a peer relationship, not a
spoke to the player), a crafter is hailed a master, an old score is
settled, a troubled past finally laid to rest.

Heuristic, deterministic, no per-tick LLM. All state lives on the NPC's
metadata, so it rides the save with the NPC.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.ambitions")

_CIVIL = ("villager", "merchant", "bard", "cleric", "wizard", "ranger",
          "guard", "noble", "druid", "paladin", "farmer", "blacksmith")


class AmbitionSystem:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    def _categories(self) -> dict:
        from items.data_loader import load_data_file
        try:
            return load_data_file("ambitions.json")
        except Exception as e:
            logger.debug(f"ambitions.json: {e}")
            return {}

    # ---- classification --------------------------------------------

    def _ambition_of(self, npc, cats):
        meta = npc.metadata
        if "ambition" in meta:
            return meta["ambition"] or None
        text = " ".join(npc.goals or []).lower()
        for cat, spec in cats.items():
            if any(k in text for k in spec.get("keywords", [])):
                meta["ambition"] = cat
                return cat
        meta["ambition"] = ""           # cache "no personal ambition"
        return None

    # ---- the nightly step ------------------------------------------

    def run_day(self) -> int:
        cats = self._categories()
        if not cats:
            return 0
        progressed = []
        achieved = 0
        for npc in list(self.engine.npc_manager.npcs.values()):
            if not npc.is_active():
                continue
            if (getattr(npc, "metadata", {}) or {}).get("player_char"):
                continue
            cat = self._ambition_of(npc, cats)
            if cat is None:
                continue
            meta = npc.metadata
            if meta.get("ambition_done"):
                continue
            spec = cats[cat]
            step = spec.get("per_night", 9) + self.rng.randint(
                0, spec.get("jitter", 4))
            meta["ambition_progress"] = meta.get("ambition_progress", 0) + step
            if meta["ambition_progress"] >= spec.get("goal", 100):
                self._achieve(npc, cat)
                meta["ambition_done"] = True
                achieved += 1
            else:
                progressed.append((npc, cat))
        self._announce_progress(progressed)
        return achieved

    def _announce_progress(self, progressed) -> None:
        """One quiet line a night so ambitions are FELT, not spammed."""
        if not progressed or self.rng.random() > 0.4:
            return
        npc, cat = self.rng.choice(progressed)
        verbs = {
            "wealth": "counts the day's takings, saving toward a quiet retirement",
            "romance": "hopes, quietly, to find someone",
            "mastery": "practises late, chasing mastery of the craft",
            "vengeance": "nurses an old grudge",
            "escape": "dreams of leaving a troubled past behind",
        }
        self.engine.memory_manager.add_event(
            f"[Realm] {npc.name} {verbs.get(cat, 'works toward a private goal')}.")

    # ---- realisation -----------------------------------------------

    def _achieve(self, npc, cat) -> None:
        line = getattr(self, f"_do_{cat}")(npc)
        npc.metadata["realised_ambition"] = cat
        self.engine.memory_manager.add_event(f"[Realm] {npc.name} {line}.")

    def _do_wealth(self, npc) -> str:
        try:
            npc.gold += self.rng.randint(40, 90)
        except Exception:
            pass
        npc.metadata["prospered"] = True
        return "has prospered at last — enough set by to retire in comfort"

    def _do_romance(self, npc) -> str:
        partner = self._single_soul(npc)
        if partner is None:
            npc.metadata["content_alone"] = True
            return "has made peace with a solitary life"
        npc.metadata["partner"] = partner.id
        partner.metadata["partner"] = npc.id
        npc.modify_relationship(partner.id, 45)
        partner.modify_relationship(npc.id, 45)
        return f"and {partner.name} have become sweethearts"

    def _do_mastery(self, npc) -> str:
        npc.metadata["master"] = True
        try:
            npc.level = getattr(npc, "level", 1) + 1
        except Exception:
            pass
        return "is now spoken of as a master of the craft"

    def _do_vengeance(self, npc) -> str:
        npc.metadata["avenged"] = True
        return "has settled an old score, and walks lighter for it"

    def _do_escape(self, npc) -> str:
        npc.metadata["moved_on"] = True
        return "has finally laid a troubled past to rest"

    def _single_soul(self, npc):
        """Another active, unattached civilian — a partner-to-be."""
        pool = []
        for other in self.engine.npc_manager.npcs.values():
            if other.id == npc.id or not other.is_active():
                continue
            meta = getattr(other, "metadata", {}) or {}
            if meta.get("player_char") or meta.get("partner"):
                continue
            if getattr(other.character_class, "value", "") not in _CIVIL:
                continue
            pool.append(other)
        return self.rng.choice(pool) if pool else None
