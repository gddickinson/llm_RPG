"""Secrets as gated tokens — the Dead Meat pattern (P3.3).

NPCs hold typed secrets (`data/secrets.json`) with release conditions:
    {"affinity": 25}   — relationship with the player >= 25
    {"quest": "id"}    — that quest turned in
    {"item": "id"}     — the player is carrying that item
    {"skill": "id", "level": N} — player skill level >= N

The dialog prompt only ever contains secrets whose conditions pass, so
no amount of prompt injection can extract a locked one — the model has
never seen it. Locked secrets surface only as a "holding something back"
tell. Revealed ids live in `player.metadata["secrets_known"]`.

In heuristic mode (no LLM), an unlocked secret is shared outright once
per conversation, so the system is a real feature on every backend.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("llm_rpg.secrets")


def _load() -> Dict[str, list]:
    from items.data_loader import load_data_file
    return load_data_file("secrets.json")


SECRETS: Dict[str, list] = _load()


def _condition_met(engine, npc, condition: dict) -> bool:
    player = engine.player
    if "affinity" in condition:
        if npc.get_relationship(player.id) < condition["affinity"]:
            return False
    if "quest" in condition:
        qm = engine.quest_manager
        quest = qm.get(condition["quest"]) if qm else None
        if quest is None or \
                getattr(quest.status, "value", "") != "turned_in":
            return False
    if "item" in condition:
        ids = [getattr(it, "id", "") for it in player.inventory]
        if condition["item"] not in ids:
            return False
    if "skill" in condition:
        from engine.skill_progression import get_skill_level
        if get_skill_level(player, condition["skill"]) < \
                condition.get("level", 1):
            return False
    return True


def known_ids(player) -> List[str]:
    return list(player.metadata.get("secrets_known", []))


def unlocked_secrets(engine, npc) -> List[dict]:
    """Secrets this NPC is currently willing to share (not yet told)."""
    already = set(known_ids(engine.player))
    out = []
    for secret in SECRETS.get(npc.id, []):
        if secret["id"] in already:
            continue
        if _condition_met(engine, npc, secret.get("condition", {})):
            out.append(secret)
    return out


def locked_count(engine, npc) -> int:
    already = set(known_ids(engine.player))
    return sum(1 for s in SECRETS.get(npc.id, [])
               if s["id"] not in already and
               not _condition_met(engine, npc, s.get("condition", {})))


def reveal(engine, npc, secret_id: str) -> Optional[str]:
    """Mark a secret revealed IF it is genuinely unlocked for this NPC."""
    for secret in unlocked_secrets(engine, npc):
        if secret["id"] == secret_id:
            engine.player.metadata.setdefault(
                "secrets_known", []).append(secret_id)
            note = f"[Secret] {npc.name}: {secret['text']}"
            engine.memory_manager.add_event(note)
            return note
    logger.debug(f"reveal refused: '{secret_id}' not unlocked "
                 f"for {npc.id}")
    return None


def prompt_block(engine, npc) -> str:
    """The secrets section of the dialog prompt — unlocked ones only."""
    unlocked = unlocked_secrets(engine, npc)
    locked = locked_count(engine, npc)
    lines = []
    if unlocked:
        lines.append("SECRETS YOU ARE WILLING TO SHARE (use the "
                     "reveal_secret action when it fits the conversation):")
        for s in unlocked:
            lines.append(f"- id={s['id']}: {s['text']}")
    if locked:
        lines.append(f"(You are keeping {locked} other secret(s). If "
                     f"probed, deflect — do NOT invent their contents.)")
    return "\n".join(lines)
