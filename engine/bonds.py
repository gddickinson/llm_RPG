"""The bond ceremony (P12.11) — Qud's water ritual, tavern style.

Type `/bond` while talking to a named NPC to formally SHARE A
DRINK (one ale/mead/wine leaves your pack — the P12.5 drinks earn
another job). The ceremony happens once per NPC, ever, and mints
BOND POINTS: 10 for the gesture plus half your relationship. Bond
is spendable trust — `/spend`:

- `/spend secret` (15): they tell you something the usual gates
  still lock — trust IS the key.
- `/spend skill` (25): they teach their craft — +150 lattice XP in
  the skill their class knows.
- `/spend join` (12 × level-gap + 20, Qud's proselytize price):
  they join the party — the relationship gate waived (the bond is
  the trust), class and party-cap rules still apply.

Faction THRESHOLDS (despised/disliked/indifferent/favored/revered)
live in characters/factions.py and gate behavior, not just prices:
despised merchants refuse trade, disliked factions refuse to be
recruited from, revered guards wave off petty bounties.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.bonds")

CEREMONY_BASE = 10
SECRET_COST = 15
SKILL_COST = 25
JOIN_BASE = 20
JOIN_PER_LEVEL = 12
TEACH_XP = 150
DRINK_IDS = ("ale", "mead", "wine")

CLASS_TEACHES = {
    "wizard": "alchemy", "cleric": "cooking", "ranger": "foraging",
    "merchant": "smithing", "guard": "agility", "paladin": "agility",
    "bard": "fishing", "villager": "woodcutting",
}


def points(engine, npc) -> int:
    return int(engine.player.metadata.get("bonds", {})
               .get(npc.id, 0))


def _add(engine, npc, delta: int) -> int:
    bonds = engine.player.metadata.setdefault("bonds", {})
    bonds[npc.id] = max(0, bonds.get(npc.id, 0) + delta)
    if delta > 0:   # trust's high-water mark gates quests (P15.5)
        earned = engine.player.metadata.setdefault("bond_earned", {})
        earned[npc.id] = max(earned.get(npc.id, 0), bonds[npc.id])
    return bonds[npc.id]


def share_drink(engine, npc) -> str:
    """/bond: the ceremony. Once per NPC, ever."""
    player = engine.player
    if npc.metadata.get("bonded"):
        return (f"You and {npc.name} have already shared the cup — "
                f"bond {points(engine, npc)}. (/spend secret · "
                f"skill · join)")
    drink = next((it for it in player.inventory
                  if getattr(it, "id", "") in DRINK_IDS), None)
    if drink is None:
        return ("The ceremony needs a drink to share — carry ale, "
                "mead or wine.")
    from engine.item_use import _remove_one
    _remove_one(player, drink)
    npc.metadata["bonded"] = True
    rel = npc.get_relationship(player.id)
    minted = CEREMONY_BASE + max(0, rel) // 2
    total = _add(engine, npc, minted)
    npc.modify_relationship(player.id, 5)
    try:
        from engine.npc_memory import remember
        remember(npc, f"{player.name} and I shared the cup — "
                      f"we are bound.", 7, engine.world.time)
    except Exception:
        pass
    msg = (f"[Bond] You share the {drink.name} with {npc.name}. "
           f"The cup passes twice; something is settled between "
           f"you. (bond {total} — /spend secret · skill · join)")
    engine.memory_manager.add_event(msg)
    return msg


def spend(engine, npc, what: str) -> str:
    """/spend secret | skill | join — bond is spendable trust."""
    if not npc.metadata.get("bonded"):
        return f"Share the cup first (/bond) — {npc.name} owes you nothing."
    what = (what or "").strip().lower()
    if what.startswith("secret"):
        return _buy_secret(engine, npc)
    if what.startswith(("skill", "teach")):
        return _buy_lesson(engine, npc)
    if what.startswith(("join", "recruit")):
        return _buy_company(engine, npc)
    return "/spend secret (15) · /spend skill (25) · /spend join"


def _charge(engine, npc, cost: int) -> Optional[str]:
    if points(engine, npc) < cost:
        return (f"That costs {cost} bond; you have "
                f"{points(engine, npc)}. Deepen the friendship "
                f"first.")
    _add(engine, npc, -cost)
    return None


def _buy_secret(engine, npc) -> str:
    from engine.secrets import SECRETS, known_ids
    already = set(known_ids(engine.player))
    held = [s for s in SECRETS.get(npc.id, [])
            if s["id"] not in already]
    if not held:
        return f"{npc.name} has no secrets left to give you."
    short = _charge(engine, npc, SECRET_COST)
    if short:
        return short
    secret = held[0]
    engine.player.metadata.setdefault(
        "secrets_known", []).append(secret["id"])
    msg = (f"[Secret] {npc.name} leans close — the bond opens what "
           f"the gates would not: {secret['text']}")
    engine.memory_manager.add_event(msg)
    return msg


def _buy_lesson(engine, npc) -> str:
    klass = getattr(npc.character_class, "value", "")
    skill = CLASS_TEACHES.get(klass)
    if skill is None:
        return f"{npc.name} has no craft to pass on."
    short = _charge(engine, npc, SKILL_COST)
    if short:
        return short
    from engine.skill_progression import add_skill_xp, skill_name
    notes = add_skill_xp(engine.player, skill, TEACH_XP)
    msg = (f"[Lesson] {npc.name} walks you through the old ways "
           f"of {skill_name(skill)} (+{TEACH_XP} XP).")
    engine.memory_manager.add_event(msg)
    for note in notes:
        engine.memory_manager.add_event(note)
    return msg


def _buy_company(engine, npc) -> str:
    gap = max(0, getattr(npc, "level", 1)
              - getattr(engine.player, "level", 1))
    cost = JOIN_BASE + JOIN_PER_LEVEL * gap
    cm = engine.companion_manager
    reason = cm.can_recruit(npc)
    if reason and "trust" not in reason:
        return reason               # class/cap rules still stand
    short = _charge(engine, npc, cost)
    if short:
        return short
    if npc.id not in cm.party:
        cm.party.append(npc.id)
    msg = (f"[Bond] {npc.name} shoulders their pack — the bond is "
           f"answer enough. They join you. (-{cost} bond)")
    engine.memory_manager.add_event(msg)
    return msg
