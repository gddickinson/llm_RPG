"""Regional achievement diaries (P2.7, the OSRS pattern).

Three regions x three tiers of tasks, defined in `data/diaries.json`.
Tasks are predicates over state the game already tracks — the collection
log (kills/items/crafts/places), skill levels, and quest status — so no
new event plumbing is needed. Completed tiers auto-claim: gold + items
are granted with fanfare, and each claimed tier deepens the player's
shop discount with that region's merchants (stacking 5% per tier).

Claimed tiers live in `player.metadata["diaries"]`.
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("llm_rpg.diaries")

TIER_ORDER = ("easy", "medium", "hard")


def _load() -> Dict[str, dict]:
    from items.data_loader import load_data_file
    return load_data_file("diaries.json")


DIARIES: Dict[str, dict] = _load()


class DiaryManager:
    def __init__(self, engine):
        self.engine = engine

    # ---- state -----------------------------------------------------------

    def claimed(self, region: str) -> List[str]:
        meta = self.engine.player.metadata
        return meta.setdefault("diaries", {}).setdefault(region, [])

    # ---- task checking -----------------------------------------------------

    def task_done(self, task: dict) -> bool:
        log = self.engine.collection_log
        ttype = task["type"]
        target = task["target"]
        if ttype == "place":
            return target in log.obtained("places")
        if ttype == "kill":
            return target in log.obtained("kills")
        if ttype == "collect":
            return target in log.obtained("items")
        if ttype == "craft":
            return target in log.obtained("crafts")
        if ttype == "skill":
            from engine.skill_progression import get_skill_level
            return get_skill_level(self.engine.player, target) >= \
                task.get("level", 1)
        if ttype == "quest":
            qm = self.engine.quest_manager
            if not qm:
                return False
            quest = qm.get(target)
            return quest is not None and \
                getattr(quest.status, "value", "") == "turned_in"
        logger.debug(f"Unknown diary task type '{ttype}'")
        return False

    def tier_progress(self, region: str, tier: str) -> Tuple[int, int]:
        tasks = DIARIES[region]["tiers"][tier]["tasks"]
        done = sum(1 for t in tasks if self.task_done(t))
        return (done, len(tasks))

    # ---- auto-claim ---------------------------------------------------------

    def check_and_claim(self) -> List[str]:
        """Claim any newly-completed tiers. Returns announcements."""
        out = []
        for region, spec in DIARIES.items():
            for tier in TIER_ORDER:
                if tier not in spec["tiers"] or \
                        tier in self.claimed(region):
                    continue
                done, total = self.tier_progress(region, tier)
                if done < total:
                    continue
                self.claimed(region).append(tier)
                out.append(self._grant(spec, region, tier))
        for msg in out:
            self.engine.memory_manager.add_event(msg)
        return out

    def _grant(self, spec: dict, region: str, tier: str) -> str:
        reward = spec["tiers"][tier].get("reward", {})
        player = self.engine.player
        parts = []
        gold = reward.get("gold", 0)
        if gold:
            player.gold += gold
            parts.append(f"{gold}g")
        from items.item_registry import create_item
        for iid in reward.get("items", []):
            item = create_item(iid)
            if item:
                player.inventory.append(item)
                parts.append(item.name)
        if reward.get("discount"):
            pct = int(self.region_discount(region) * 100)
            parts.append(f"{pct}% off at {spec['name'].split()[0]} shops")
        try:
            from engine.player_deeds import record_deed
            record_deed(self.engine,
                        f"completed the {spec['name']} ({tier} tier)")
        except Exception:
            pass
        return (f"*** {spec['name']} — {tier} tier complete! "
                f"Reward: {', '.join(parts)} ***")

    # ---- shop integration ----------------------------------------------------

    def region_discount(self, region: str) -> float:
        spec = DIARIES.get(region, {})
        total = 0.0
        for tier in self.claimed(region):
            total += spec.get("tiers", {}).get(tier, {}) \
                .get("reward", {}).get("discount", 0.0)
        return total

    def discount_for_merchant(self, merchant) -> float:
        home = (getattr(merchant, "home_location", "") or "")
        for region, spec in DIARIES.items():
            if any(kw.lower() in home.lower()
                   for kw in spec.get("location_keywords", [])):
                return self.region_discount(region)
        return 0.0

    # ---- UI --------------------------------------------------------------

    def overlay_lines(self) -> List[str]:
        out = []
        for region, spec in DIARIES.items():
            out.append(spec["name"])
            for tier in TIER_ORDER:
                if tier not in spec["tiers"]:
                    continue
                done, total = self.tier_progress(region, tier)
                mark = "COMPLETE" if tier in self.claimed(region) \
                    else f"{done}/{total}"
                out.append(f"  {tier.title():<8} [{mark}]")
                if tier not in self.claimed(region):
                    for task in spec["tiers"][tier]["tasks"]:
                        box = "x" if self.task_done(task) else " "
                        out.append(f"    [{box}] {task['label']}")
            out.append("")
        return out
