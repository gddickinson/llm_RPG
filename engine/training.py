"""Training & advancement (the skills/spells upgrade — George).

A level-up now grants TRAINING POINTS, a deliberate advancement currency
you SPEND at a class-appropriate TRAINER (a guild hall, a mage tower, a
temple, a wildwarden's lodge…) to raise skills and learn spells — chosen,
not automatic. A trainer serves only the classes suited to it (a warrior
can't study at a mage tower), so where you train matters.

Pure over the engine; the character-hub Training tab (`ui/hub_training`)
drives it. Skills are raised toward a cap tied to your character level
(directed growth up to your understanding; mastery beyond comes from
DOING). Spells taught are cross-school BREADTH — eligible spells of the
trainer's schools your class's innate list doesn't cover.
"""

import json
import logging
import os

logger = logging.getLogger("llm_rpg.training")

TP_PER_LEVEL = 3          # training points granted per character level
SKILL_TP = 1              # cost to raise a skill one rank
SPELL_TP = 2              # cost to learn a spell
_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "trainers.json")

_PROFILES = None


def _profiles() -> dict:
    global _PROFILES
    if _PROFILES is None:
        try:
            with open(_DATA, encoding="utf-8") as fh:
                _PROFILES = json.load(fh).get("profiles", {})
        except Exception as e:                       # pragma: no cover
            logger.info(f"Trainer data unavailable: {e}")
            _PROFILES = {}
    return _PROFILES


# ---- training points ---------------------------------------------------

def training_points(character) -> int:
    return int((getattr(character, "metadata", None) or {}).get(
        "training_points", 0))


def award_training_points(character, n: int = TP_PER_LEVEL) -> None:
    m = character.metadata
    m["training_points"] = int(m.get("training_points", 0)) + int(n)


def _spend(character, n: int) -> bool:
    have = training_points(character)
    if have < n:
        return False
    character.metadata["training_points"] = have - n
    return True


# ---- trainer detection -------------------------------------------------

def _player_class(engine) -> str:
    return getattr(getattr(engine.player, "character_class", None),
                   "value", "")


def _here_kinds(engine) -> set:
    """Location kind/name words at the player's spot."""
    words = set()
    try:
        loc = engine.player_location()
    except Exception:
        loc = None
    if loc is None:
        try:
            loc = engine.world.get_location_at(*engine.player.position)
        except Exception:
            loc = None
    if loc is not None:
        props = getattr(loc, "properties", None) or {}
        for v in (props.get("kind"), props.get("type"),
                  getattr(loc, "name", "")):
            if v:
                words |= set(str(v).lower().split())
    return words


def _nearby_npc_tokens(engine, r: int = 2) -> set:
    """Role tokens for every mentor near the player — its class value AND
    its id/name words + profession (a blacksmith NPC is class `merchant`,
    so `blacksmith` only shows in its id)."""
    out = set()
    try:
        px, py = engine.player.position
        z = getattr(engine, "current_interior", None) \
            or getattr(engine, "current_dungeon", None)
        zone_name = getattr(z, "name", None) if z else None
        from engine.agent_sense import _colocated
        for npc in engine.npc_manager.npcs.values():
            if not npc.is_active() or not _colocated(zone_name, npc):
                continue
            nx, ny = npc.position
            if max(abs(nx - px), abs(ny - py)) > r:
                continue
            out.add(getattr(getattr(npc, "character_class", None),
                            "value", ""))
            for src in (getattr(npc, "id", ""), getattr(npc, "name", "")):
                out |= set(str(src).lower().replace("_", " ").split())
            prof = (getattr(npc, "metadata", None) or {}).get("profession")
            if prof:
                out.add(str(prof).lower())
    except Exception:
        pass
    return out


def _profile_present(prof, kinds, tokens) -> bool:
    for k in prof.get("location_kinds", []):
        if any(k in w or w in k for w in kinds):
            return True
    return bool(set(prof.get("npc_classes", [])) & tokens)


def trainer_here(engine):
    """A merged TrainerProfile suitable to the player's class at their
    location, or None. `{labels, skills, teaches_spells, schools}`."""
    cls = _player_class(engine)
    kinds = _here_kinds(engine)
    npc_classes = _nearby_npc_tokens(engine)
    labels, skills, schools = [], set(), set()
    for prof in _profiles().values():
        fc = prof.get("for_classes", [])
        if "*" not in fc and cls not in fc:
            continue
        if not _profile_present(prof, kinds, npc_classes):
            continue
        labels.append(prof.get("label", "Trainer"))
        skills |= set(prof.get("skills", []))
        schools |= set(prof.get("spell_schools", []))
    if not labels:
        return None
    return {"labels": labels, "skills": skills,
            "teaches_spells": bool(schools), "schools": schools}


# ---- options + spend ---------------------------------------------------

def skill_cap(character) -> int:
    return max(3, min(50, getattr(character, "level", 1) * 3))


def skill_options(engine, profile):
    """[(skill_id, name, level, at_cap)] for the trainer's skills."""
    from engine.skill_progression import (all_skill_ids, skill_name,
                                          get_skill_level)
    ids = set(all_skill_ids())
    cap = skill_cap(engine.player)
    out = []
    for sid in sorted(profile["skills"]):
        if sid not in ids:
            continue
        lvl = get_skill_level(engine.player, sid)
        out.append((sid, skill_name(sid), lvl, lvl >= cap))
    return out


def spell_options(engine, profile, limit: int = 16):
    """[(spell_id, name, tier, school)] the trainer can teach now — eligible
    spells of its schools the player doesn't yet know (cross-school breadth)."""
    if not profile.get("teaches_spells"):
        return []
    from engine.spells import SPELL_REGISTRY, can_learn, ensure_mana
    ensure_mana(engine.player)
    known = set((engine.player.metadata or {}).get("spells_known", []))
    schools = profile["schools"]
    out = []
    for s in SPELL_REGISTRY.values():
        if s.id in known or getattr(s, "school", "") not in schools:
            continue
        ok, _ = can_learn(engine.player, s)
        if ok:
            out.append((s.id, s.name, getattr(s, "tier", 1),
                        getattr(s, "school", "")))
    out.sort(key=lambda t: (t[2], t[3], t[1]))
    return out[:limit]


def train_skill(engine, skill_id: str):
    """Spend TP to raise a skill one rank at the current trainer."""
    prof = trainer_here(engine)
    if prof is None or skill_id not in prof["skills"]:
        return False, "No trainer here teaches that."
    p = engine.player
    from engine.skill_progression import (get_skill_level, get_skill_xp,
                                          total_xp_for_level, add_skill_xp,
                                          skill_name)
    lvl = get_skill_level(p, skill_id)
    if lvl >= skill_cap(p):
        return False, (f"You've learned all a trainer can teach of "
                       f"{skill_name(skill_id)} for now — practise in the "
                       f"field to go further.")
    if training_points(p) < SKILL_TP:
        return False, "You have no training points to spend."
    _spend(p, SKILL_TP)
    need = total_xp_for_level(lvl + 1) - get_skill_xp(p, skill_id)
    add_skill_xp(p, skill_id, max(1, need))
    return True, (f"The trainer drills you — {skill_name(skill_id)} rises to "
                  f"level {get_skill_level(p, skill_id)}.")


def learn_spell(engine, spell_id: str):
    """Spend TP to learn a spell at an arcane/divine/nature trainer."""
    prof = trainer_here(engine)
    if prof is None or not prof.get("teaches_spells"):
        return False, "No spell tutor here."
    from engine.spells import SPELL_REGISTRY, teach_spell
    s = SPELL_REGISTRY.get(spell_id)
    if s is None or getattr(s, "school", "") not in prof["schools"]:
        return False, "This tutor doesn't teach that art."
    p = engine.player
    if training_points(p) < SPELL_TP:
        return False, "You lack the training points for a new spell."
    ok, why = teach_spell(p, spell_id)
    if not ok:
        return False, why
    _spend(p, SPELL_TP)
    return True, f"The tutor teaches you {s.name}."
