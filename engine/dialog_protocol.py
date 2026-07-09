"""Structured dialog protocol — engine owns truth, LLM owns voice (P3.1).

When an LLM provider is active, player↔NPC dialog goes through a JSON
contract instead of free prose:

    {"dialogue": "...", "mood": "wary",
     "action": "give_item", "action_args": {"item_id": "ale"}}

`action` must come from a small whitelist and is executed by the ENGINE
after validation — the model can only propose. Malformed output degrades
gracefully: any JSON-looking payload is mined for a dialogue string, and
raw prose is accepted as plain dialogue (Mantella's lesson: small tool
lists; AI Dungeon's lesson: state lives in code).

Actions:
- adjust_affinity {delta}: -3..+3 relationship shift (how the chat went)
- give_item {item_id}: hand over an item — ONLY if the NPC actually has it
- refuse {}: explicit no (marker for future stakes; logs nothing)
- end {}: NPC wants to end the conversation
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("llm_rpg.dialog_protocol")

ALLOWED_ACTIONS = ("adjust_affinity", "give_item", "reveal_secret",
                   "refuse", "end")
MAX_AFFINITY_DELTA = 3

SYSTEM_PROMPT = """You are roleplaying an NPC in a fantasy RPG. Reply with ONLY a JSON object:
{"dialogue": "<what you say, 1-3 sentences, in character>",
 "mood": "<one word>",
 "action": "<optional, one of: adjust_affinity, give_item, refuse, end>",
 "action_args": {}}

Action rules:
- adjust_affinity: args {"delta": -3..3} — how this exchange changed your feelings.
- give_item: args {"item_id": "<id>"} — ONLY ids listed under YOUR INVENTORY. Give items rarely, when it truly fits.
- reveal_secret: args {"secret_id": "<id>"} — ONLY ids listed under SECRETS YOU ARE WILLING TO SHARE, and only when the conversation naturally leads there.
- refuse: decline a request that conflicts with your interests. You are a person, not a servant — do NOT agree to everything.
- end: you want to end the conversation.
Stay in character. Never invent facts about the world state; the FACTS section is the truth."""


def build_prompt(engine, npc, player_message: str,
                 recent_history: List[str]) -> str:
    """User prompt: character sheet facts + inventory + recent context."""
    player = engine.player
    rel = npc.get_relationship(player.id)
    inv_ids = [getattr(it, "id", str(it)) for it in npc.inventory]
    traits = ", ".join(npc.personality.get("traits", [])) or "plain"
    goals = "; ".join(npc.goals[:3])

    # Per-NPC memory: retrieval-scored memories, settled opinions,
    # verbatim recent exchanges (P3.2)
    from engine.npc_memory import retrieve, opinions, recent_exchanges
    memories = retrieve(npc, player_message, engine.world.time, k=4)
    mem_block = "\n".join(f"- {m}" for m in memories) or "- (nothing yet)"
    op_block = "\n".join(f"- {o}" for o in opinions(npc))
    convo = "\n".join(recent_exchanges(npc, k=4))

    parts = [
        f"FACTS\n"
        f"You are {npc.name}, a {npc.race.value} "
        f"{npc.character_class.value}. Traits: {traits}.\n"
        f"Your goals: {goals}\n"
        f"YOUR INVENTORY (the only items you can give): {inv_ids}\n"
        f"Your feelings toward {player.name}: {rel} on a -100..100 scale "
        f"({npc.get_relationship_description(player.id)}).\n"
        f"Time: {engine.world.get_formatted_time()}  "
        f"Weather: {engine.current_weather()}",
        f"YOUR MEMORIES (most relevant to what they just said)\n"
        f"{mem_block}",
    ]
    if op_block:
        parts.append(f"YOUR SETTLED OPINIONS\n{op_block}")
    try:
        from engine.secrets import prompt_block
        secrets_block = prompt_block(engine, npc)
        if secrets_block:
            parts.append(secrets_block)
    except Exception:
        pass
    try:
        topics_block = engine.topic_journal.prompt_block(
            npc, player_message)
        if topics_block:
            parts.append(topics_block)
    except Exception:
        pass
    if convo:
        parts.append(f"EARLIER IN THIS ACQUAINTANCE\n{convo}")
    parts.append(f"{player.name.upper()} SAYS: \"{player_message}\"\n\n"
                 f"Reply with the JSON object only.")
    return "\n\n".join(parts)


def parse_response(raw: str) -> Dict[str, Any]:
    """Extract the JSON contract; degrade to plain dialogue on failure."""
    fallback = {"dialogue": raw.strip(), "mood": "", "action": "",
                "action_args": {}}
    if not raw or not raw.strip():
        return {"dialogue": "...", "mood": "", "action": "",
                "action_args": {}}
    # Mine the first {...} block (handles markdown fences + chatter)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return fallback
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
    if not isinstance(data, dict) or not data.get("dialogue"):
        return fallback
    action = data.get("action") or ""
    if action not in ALLOWED_ACTIONS:
        action = ""
    args = data.get("action_args")
    return {
        "dialogue": str(data["dialogue"]).strip(),
        "mood": str(data.get("mood", "")).strip(),
        "action": action,
        "action_args": args if isinstance(args, dict) else {},
    }


def execute_action(engine, npc, parsed: Dict[str, Any]) -> Optional[str]:
    """Validate + apply the proposed action. Returns a note for the log."""
    action = parsed.get("action")
    args = parsed.get("action_args", {})
    player = engine.player

    if action == "adjust_affinity":
        try:
            delta = int(args.get("delta", 0))
        except (TypeError, ValueError):
            return None
        delta = max(-MAX_AFFINITY_DELTA, min(MAX_AFFINITY_DELTA, delta))
        if delta:
            npc.modify_relationship(player.id, delta)
        return None

    if action == "give_item":
        item_id = str(args.get("item_id", ""))
        for it in list(npc.inventory):
            iid = getattr(it, "id", str(it))
            if iid == item_id:
                npc.inventory.remove(it)
                player.inventory.append(it)
                name = getattr(it, "name", str(it))
                return f"{npc.name} hands you {name}."
        logger.debug(f"{npc.name} tried to give '{item_id}' "
                     f"but doesn't have it")
        return None

    if action == "reveal_secret":
        from engine.secrets import reveal
        return reveal(engine, npc, str(args.get("secret_id", "")))

    if action == "end":
        return f"{npc.name} turns back to their business."

    # "refuse" and unknown/absent actions change nothing
    return None


def run_dialog(engine, npc, player_message: str,
               recent_history: List[str]) -> Optional[Tuple[str, str]]:
    """Full protocol round-trip. Returns (dialogue, extra_note) or None
    when no LLM provider is active (caller falls back to legacy path)."""
    iface = getattr(engine, "llm_interface", None)
    if iface is None or getattr(iface, "provider_name", "heuristic") == \
            "heuristic":
        return None
    prompt = build_prompt(engine, npc, player_message, recent_history)
    raw = iface.generate_response(prompt, SYSTEM_PROMPT,
                                  max_tokens=300, temperature=0.8)
    parsed = parse_response(raw)
    note = execute_action(engine, npc, parsed)
    return (parsed["dialogue"], note or "")
