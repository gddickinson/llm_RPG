"""Skill progression lattice — parallel skill tracks with a geometric
XP curve (Phase 2 of DEVELOPMENT_PLAN.md; modeled on OSRS's design).

Skills are defined in `data/skills.json`. Per-skill XP lives in
`player.metadata["skills"]` (a plain {skill_id: xp} dict), so it
persists through save v3 with no extra serialization.

Curve: advancing from level L to L+1 costs `floor(BASE * GROWTH^(L-1))`
XP — the first levels come in minutes, the last few take as long as all
the earlier ones combined. MAX_LEVEL caps progression at 50.
"""

import logging
import math
from typing import Dict, List, Tuple

logger = logging.getLogger("llm_rpg.skills")

BASE_XP = 50          # cost of level 1 -> 2
GROWTH = 1.10         # geometric growth per level
MAX_LEVEL = 50


def _load_skills() -> Dict[str, dict]:
    from items.data_loader import load_data_file
    return load_data_file("skills.json")


SKILLS: Dict[str, dict] = _load_skills()


def all_skill_ids() -> List[str]:
    return list(SKILLS.keys())


def skill_name(skill_id: str) -> str:
    return SKILLS.get(skill_id, {}).get("name", skill_id.title())


# ---- curve ---------------------------------------------------------------

def xp_for_level_up(level: int) -> int:
    """XP needed to advance FROM `level` to `level + 1`."""
    return int(BASE_XP * (GROWTH ** (level - 1)))


def total_xp_for_level(level: int) -> int:
    """Cumulative XP needed to REACH `level` (level 1 = 0 XP)."""
    return sum(xp_for_level_up(lv) for lv in range(1, level))


def level_for_xp(xp: float) -> int:
    level = 1
    remaining = xp
    while level < MAX_LEVEL:
        cost = xp_for_level_up(level)
        if remaining < cost:
            break
        remaining -= cost
        level += 1
    return level


def progress_within_level(xp: float) -> Tuple[int, int]:
    """(xp into current level, xp needed for next). needed=0 at cap."""
    level = level_for_xp(xp)
    if level >= MAX_LEVEL:
        return (0, 0)
    into = int(xp - total_xp_for_level(level))
    return (into, xp_for_level_up(level))


# ---- per-character state --------------------------------------------------

def _skills_dict(character) -> Dict[str, float]:
    meta = getattr(character, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        character.metadata = meta
    return meta.setdefault("skills", {})


def get_skill_xp(character, skill_id: str) -> float:
    return _skills_dict(character).get(skill_id, 0)


def get_skill_level(character, skill_id: str) -> int:
    return level_for_xp(get_skill_xp(character, skill_id))


def add_skill_xp(character, skill_id: str, xp: float) -> List[str]:
    """Award XP; returns human-readable messages (level-ups)."""
    if skill_id not in SKILLS:
        logger.debug(f"Unknown skill '{skill_id}'")
        return []
    if xp <= 0:
        return []
    skills = _skills_dict(character)
    before = level_for_xp(skills.get(skill_id, 0))
    skills[skill_id] = skills.get(skill_id, 0) + xp
    after = level_for_xp(skills[skill_id])
    messages = []
    if after > before:
        messages.append(
            f"** {skill_name(skill_id)} level up! "
            f"You are now level {after}. **")
    return messages


def skill_summary(character) -> List[str]:
    """Lines for the character sheet: name, level, progress."""
    out = []
    for sid in all_skill_ids():
        xp = get_skill_xp(character, sid)
        level = level_for_xp(xp)
        into, needed = progress_within_level(xp)
        tail = f"({into}/{needed})" if needed else "(MAX)"
        out.append(f"{skill_name(sid):<14} {level:>3}  {tail}")
    return out


def total_skill_level(character) -> int:
    return sum(get_skill_level(character, sid) for sid in all_skill_ids())
