"""The NPC social graph (P20.2) — a world of relationships.

Reputation used to be a wheel of spokes: every relationship pointed at the
player, and the only NPC-to-NPC bond that ever moved was the world
director's feud — and that fired on the LLM path alone, so on the default
heuristic backend the townsfolk had no feelings about each other at all.

This gives them a peer graph that drifts every night. Folk of the same
faction and kin warm to each other; a settlement's neighbours grow
familiar; the lawful and the outlaw grate. Let it run and relationships
cross thresholds on their own — two people become fast friends, or fall
into a bitter feud — each a `[Realm]` beat the gossip system can carry.
The romance couples P20.1 mints are the same graph at its warmest.

Heuristic and deterministic. Every edge lives in the NPCs' own
`relationships` dict and `metadata`, so the whole graph rides the save.
"""

import logging
import random

logger = logging.getLogger("llm_rpg.social_graph")

FRIEND = 55              # a bond this warm is a friendship
FEUD = -45              # a bond this cold is a feud
BOND, KIN, NEIGHBOUR = 2, 3, 1
FRICTION = -3          # the lawful and the outlaw grate
_SOCIAL = ("monster", "troll")     # these don't keep a social calendar


class SocialGraph:
    def __init__(self, engine, seed: int = None):
        self.engine = engine
        self.rng = random.Random(seed)

    # ---- the nightly step ------------------------------------------

    def run_day(self) -> int:
        pool = [n for n in self.engine.npc_manager.npcs.values()
                if n.is_active()
                and not (getattr(n, "metadata", {}) or {}).get("player_char")
                and getattr(n.character_class, "value", "") not in _SOCIAL]
        seen, events = set(), []
        for npc in pool:
            assoc = self._associates(npc, pool)
            if not assoc:
                continue
            other = self.rng.choice(assoc)
            key = tuple(sorted((npc.id, other.id)))
            if key in seen:
                continue
            seen.add(key)
            drift = self._drift(npc, other)
            npc.modify_relationship(other.id, drift)
            other.modify_relationship(npc.id, drift)
            ev = self._threshold(npc, other)
            if ev:
                events.append(ev)
        self._announce(events)
        return len(events)

    def _associates(self, npc, pool):
        """Same-faction peers (bonds), plus a couple of outsiders (friction
        or acquaintance) so the graph isn't only cliques."""
        same = [o for o in pool if o.id != npc.id and o.faction == npc.faction]
        others = [o for o in pool if o.id != npc.id and o.faction != npc.faction]
        picks = list(same)
        if others:
            picks += self.rng.sample(others, min(2, len(others)))
        return picks

    def _kin(self, a, b) -> bool:
        try:
            from characters.families import relation_to
            return relation_to(a.id, b.id) not in ("", "stranger", None)
        except Exception:
            return False

    def _drift(self, a, b) -> int:
        if self._kin(a, b):
            return KIN
        fa, fb = getattr(a, "faction", "neutral"), getattr(b, "faction", "neutral")
        if fa == fb:
            return BOND
        hostile = {"brigands", "monsters"}
        if (fa in hostile) != (fb in hostile):     # one outlaw, one not
            return FRICTION
        ha = getattr(a, "home_location", None)
        if ha and ha == getattr(b, "home_location", None):
            return NEIGHBOUR
        return self.rng.choice([-1, 0, 1])         # acquaintance noise

    def _threshold(self, a, b):
        rel = a.get_relationship(b.id)
        sa = a.metadata.setdefault("social", {})
        sb = b.metadata.setdefault("social", {})
        if rel >= FRIEND and not sa.get(f"friend:{b.id}"):
            sa[f"friend:{b.id}"] = True
            sb[f"friend:{a.id}"] = True
            return f"{a.name} and {b.name} have become fast friends."
        if rel <= FEUD and not sa.get(f"feud:{b.id}"):
            sa[f"feud:{b.id}"] = True
            sb[f"feud:{a.id}"] = True
            return f"{a.name} and {b.name} have fallen into a bitter feud."
        return None

    def _announce(self, events) -> None:
        """Friendships and feuds are rare milestones — announce them, but
        cap a burst so a quiet night stays quiet."""
        for line in events[:3]:
            self.engine.memory_manager.add_event(f"[Realm] {line}")
