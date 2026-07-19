"""NPC skill seeding (George: give NPCs calling-appropriate skills).

The richer skill roster feeds combat/magic power for ANY character, so a
guard with Weaponry hits harder and a cleric with Spellcraft has a deeper
mana well — but NPCs started at 0 in everything. This seeds each NPC's
skills from its CLASS and its ROLE (read from the id/name — a blacksmith
NPC is class `merchant`, so its craft is only legible from its name),
scaled by level, ONCE, at creation.

Deliberately CONSERVATIVE: a primary skill sits at ~level+2, a secondary
at ~level-1, so a low-level NPC's skill is below the `+1 per N levels`
threshold and its combat maths is unchanged — only seasoned NPCs pull
ahead. Pure over the character; hooked in `npc_manager.add_npc`.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.npc_skills")

_DATA = os.path.join(os.path.dirname(__file__), "..", "data",
                     "npc_skills.json")
_MAP = None
# classes that use natural weapons / aren't people — never skill-seeded
_SKIP_CLASSES = {"monster", "animal", "troll"}


def _maps():
    global _MAP
    if _MAP is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _MAP = json.load(fh)
        except Exception as e:                       # pragma: no cover
            logger.info(f"NPC skill data unavailable: {e}")
            _MAP = {"by_class": {}, "by_role": {}}
    return _MAP


def _tokens(npc):
    out = set()
    for src in (getattr(npc, "id", ""), getattr(npc, "name", "")):
        out |= set(str(src).lower().replace("_", " ").split())
    prof = (getattr(npc, "metadata", None) or {}).get("profession")
    if prof:
        out.add(str(prof).lower())
    return out


def _target(level, tier):
    if tier == "p":
        return min(50, max(2, level + 2))
    return min(50, max(1, level - 1))


def grants_for(npc):
    """{skill_id: 'p'|'s'} the NPC's class + role imply (primary wins)."""
    maps = _maps()
    cls = getattr(getattr(npc, "character_class", None), "value", "")
    specs = list(maps["by_class"].get(cls, []))
    toks = _tokens(npc)
    for tok in toks:
        specs += maps["by_role"].get(tok, [])
    out = {}
    for spec in specs:
        sid, _, tier = spec.partition(":")
        tier = tier or "s"
        if out.get(sid) != "p":                      # primary beats secondary
            out[sid] = tier
    return out


def seed(npc) -> bool:
    """Seed an NPC's skills once. Returns True if it seeded anything."""
    meta = getattr(npc, "metadata", None)
    if not isinstance(meta, dict):
        return False
    if meta.get("skills_seeded") or meta.get("player_char"):
        return False
    cls = getattr(getattr(npc, "character_class", None), "value", "")
    if cls in _SKIP_CLASSES:
        meta["skills_seeded"] = True
        return False
    level = int(getattr(npc, "level", 1) or 1)
    grants = grants_for(npc)
    meta["skills_seeded"] = True
    if not grants:
        return False
    try:
        from engine.skill_progression import add_skill_xp, total_xp_for_level
        for sid, tier in grants.items():
            add_skill_xp(npc, sid, total_xp_for_level(_target(level, tier)))
    except Exception as e:                            # pragma: no cover
        logger.debug(f"seed {getattr(npc, 'id', '?')}: {e}")
        return False
    return True


def seed_all(engine) -> int:
    """Safety-net pass over every NPC (idempotent). Returns count seeded."""
    n = 0
    try:
        for npc in list(engine.npc_manager.npcs.values()):
            if seed(npc):
                n += 1
    except Exception:
        pass
    return n
