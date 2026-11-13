"""One conversation turn with a preset NPC, through the game's own offline (heuristic) dialog code.

The game's `DialogSystem.player_to_npc` needs a whole running world (positions, quests, gossip). The web demo keeps the
parts that make a conversation, and calls the repo's real code for each:

- the NPC's line: `llm.providers.heuristic.HeuristicProvider.generate_npc_dialog` (seeded per turn);
- authored topic answers and topic learning: `engine.topics.TopicJournal` on a real `MemoryManager`;
- gated secrets: `engine.secrets.unlocked_secrets` / `locked_count` / `reveal`;
- `/persuade` `/intimidate` `/deceive`: `engine.persuasion.PersuasionSystem.attempt` (the dice judge, DC 14);
- friendly talk builds trust (+2), as in `DialogSystem`.

Left out on purpose (they need a live world): quest offers in the reply, deeds comments, gossip, cached greetings,
bonds/romance/hiring commands. The conversation state travels with every call (the API is stateless), and every random
draw is seeded from (seed, turn), so `static/talk_engine.js` reproduces each turn exactly in the browser.
"""
from types import SimpleNamespace

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from characters.npc_presets import NPC_SPECS, make_npc
from engine.memory_manager import MemoryManager
from engine.persuasion import PersuasionSystem, parse_command
from engine.secrets import SECRETS, locked_count, reveal, unlocked_secrets
from engine.topics import TOPICS, TopicJournal
from llm.providers.heuristic import HeuristicProvider

HOSTILE = ("brigand", "troll", "monster")
DEFAULT_STATS = {"strength": 14, "intelligence": 10, "charisma": 12}  # the game's default warrior
PLAYER_NAME = "Traveller"


def turn_seed(seed: int, turn: int) -> int:
    """The per-turn RNG seed (kept below 2**32 so the JS port seeds identically)."""
    return (int(seed) * 1000 + int(turn)) % 4294967296


def new_state(seed: int = 1) -> dict:
    return {"seed": int(seed), "turn": 0, "affinity": {}, "topics": [], "secrets": [], "locks": {},
            "stats": dict(DEFAULT_STATS)}


class _Table:
    """The smallest engine stand-in the dialog components need: a player, a clock, an event log."""

    def __init__(self, state: dict):
        stats = {**DEFAULT_STATS, **(state.get("stats") or {})}
        self.player = Character(
            id="player", name=PLAYER_NAME, character_class=CharacterClass.WARRIOR, race=CharacterRace.HUMAN,
            level=1, strength=int(stats["strength"]), dexterity=12, constitution=14,
            intelligence=int(stats["intelligence"]), wisdom=10, charisma=int(stats["charisma"]), hp=23, max_hp=23)
        self.player.metadata["topics_known"] = list(state.get("topics", []))
        self.player.metadata["secrets_known"] = list(state.get("secrets", []))
        self.player.metadata["persuasion_locks"] = dict(state.get("locks", {}))
        self.world = SimpleNamespace(time=0)          # no clock: a lockout lasts the whole web conversation
        self.quest_manager = None                     # quest-gated secrets stay locked here
        self.llm_interface = SimpleNamespace(provider_name="heuristic")
        self.memory_manager = MemoryManager()
        self.topic_journal = TopicJournal(self)
        self.memory_manager.on_event = self.topic_journal.scan


def _extras(table: _Table, npc, base: str, message):
    """The heuristic part of DialogSystem._append_quest_prompts: topic answers, then one secret or a tell."""
    out = [base]
    if message:
        out += [f"  {line}" for line in table.topic_journal.heuristic_lines(npc, message)]
    unlocked = unlocked_secrets(table, npc)
    if unlocked:
        reveal(table, npc, unlocked[0]["id"])
        out.append(f"  (leaning close) {unlocked[0]['text']}")
    elif locked_count(table, npc):
        out.append("  (They seem to be holding something back.)")
    return "\n".join(out)


def take_turn(npc_id: str, message: str, state: dict, provider=None) -> dict:
    """Play one turn. message '' = greet. Returns {reply, kind, learned, revealed, state}."""
    if npc_id not in NPC_SPECS:
        raise KeyError(npc_id)
    state = {**new_state(), **(state or {})}
    message = (message or "").strip()
    table = _Table(state)
    npc = make_npc(npc_id)
    npc.relationships[table.player.id] = int(state["affinity"].get(npc_id, 0))
    known_before = list(table.topic_journal.known())
    secrets_before = set(table.player.metadata["secrets_known"])
    seed = turn_seed(state["seed"], state["turn"])
    speaker = provider or HeuristicProvider(seed=seed)
    mm = table.memory_manager
    if message.startswith("/") and parse_command(message) is None:
        return {"reply": "Only /persuade, /intimidate and /deceive (with an argument) work here; the other "
                         "slash commands need the full game.", "kind": "note", "learned": [], "revealed": [],
                "state": state}
    cmd = parse_command(message) if message else None
    if not message:
        kind = "greet"
        reply = _extras(table, npc, speaker.generate_npc_dialog(npc, "Hello", []) or "Hello there, traveler.", None)
        mm.add_event(f'{npc.name} says: "{reply}"')
    elif cmd:
        kind = "check"
        verb, argument = cmd
        mm.add_event(f'You try to {verb} {npc.name}: "{argument}"')
        reply = PersuasionSystem(table, seed=seed).attempt(npc, verb, argument)
    else:
        kind = "say"
        mm.add_event(f'You say to {npc.name}: "{message}"')
        reply = _extras(table, npc, speaker.generate_npc_dialog(npc, message, []) or "...", message)
        mm.add_event(f'{npc.name} says: "{reply}"')
        if npc.character_class.value not in HOSTILE:
            npc.modify_relationship(table.player.id, 2)
    known = table.topic_journal.known()
    new = {**state, "turn": state["turn"] + 1,
           "affinity": {**state["affinity"], npc_id: npc.get_relationship(table.player.id)},
           "topics": list(known), "secrets": list(table.player.metadata["secrets_known"]),
           "locks": dict(table.player.metadata["persuasion_locks"])}
    return {"reply": reply, "kind": kind,
            "learned": [TOPICS[t]["name"] for t in known if t not in known_before],
            "revealed": [s for s in new["secrets"] if s not in secrets_before], "state": new}


def _other_conditions_met(npc_id: str, condition: dict) -> bool:
    """A secret's non-affinity conditions (quest / item / skill), evaluated on the web demo's fresh player."""
    rest = {k: v for k, v in condition.items() if k != "affinity"}
    if not rest:
        return True
    from engine.secrets import _condition_met
    return _condition_met(_Table(new_state()), make_npc(npc_id), rest)


def talk_data() -> dict:
    """Everything static/talk_engine.js needs, taken from the repo's data and the heuristic provider's own lines."""
    from llm.providers import heuristic as h
    from engine.persuasion import DC, FAIL_AFFINITY, VERBS
    import os
    from items.data_loader import _SYNC_DUP, DATA_ROOT, load_data_file
    origin = {nid: fname[:-5] for fname in sorted(os.listdir(os.path.join(DATA_ROOT, "npcs")))
              if fname.endswith(".json") and not _SYNC_DUP.search(fname[:-5])
              for nid in load_data_file(f"npcs/{fname}")}
    npcs = []
    for nid, spec in NPC_SPECS.items():
        npcs.append({
            "origin": origin.get(nid, ""), "likes": (spec.get("personality") or {}).get("likes", []),
            "id": nid, "name": spec["name"], "class": spec.get("class", "villager"), "race": spec.get("race", "human"),
            "level": spec.get("level", 1), "description": spec.get("description", ""),
            "personality": spec.get("personality", {}), "goals": spec.get("goals", []),
            "zone_bound": bool(spec.get("zone_bound")), "hostile": spec.get("class") in HOSTILE,
            "secret_count": len(SECRETS.get(nid, [])),
            "topics": [TOPICS[t]["name"] for t in TOPICS if nid in TOPICS[t].get("responses", {})],
        })
    secrets = {nid: [{"id": s["id"], "text": s["text"], "affinity": s.get("condition", {}).get("affinity", -1000),
                      "other_ok": _other_conditions_met(nid, s.get("condition", {})),
                      "needs": sorted(k for k in s.get("condition", {}) if k != "affinity")} for s in lst]
               for nid, lst in SECRETS.items() if nid in NPC_SPECS}
    topics = [{"id": tid, "name": t["name"], "hint": t.get("hint", ""), "keywords": t.get("keywords", []),
               "responses": t.get("responses", {}), "default_response": t.get("default_response")}
              for tid, t in TOPICS.items()]
    return {
        "npcs": npcs, "topics": topics, "secrets": secrets, "default_stats": DEFAULT_STATS,
        "lines": {"greetings": h._GREETINGS, "generic": h._GENERIC_REPLIES, "goal_replies": h._GOAL_REPLIES,
                  "greet_words": list(h._GREET_WORDS), "trade_words": list(h._TRADE_WORDS),
                  "rumor_words": list(h._RUMOR_WORDS), "rumors": h._RUMORS,
                  "trade_merchant": h._TRADE_REPLY_MERCHANT, "trade_other": h._TRADE_REPLY_OTHER},
        "persuasion": {"verbs": VERBS, "dc": DC, "fail_affinity": FAIL_AFFINITY},
    }
