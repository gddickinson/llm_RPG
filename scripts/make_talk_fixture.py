"""Write tests/fixtures/talk_fixture.json: scripted conversations played through web/talk.py (the repo's real heuristic
dialog, topic journal, secrets and persuasion code), which web/static/talk_engine.test.mjs requires the JS port to
reproduce turn by turn (reply text, learned topics, revealed secrets and the full state).

Run: python scripts/make_talk_fixture.py   (tests/test_web.py checks the file is current)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_RPG_DM_LIBRARY", tempfile.mkdtemp(prefix="llmrpg_lib_"))

from web.talk import new_state, take_turn, talk_data  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "talk_fixture.json"

SCRIPT = ["", "Hello there!", "Any news? I heard of trouble on the road.", "What do you sell? Show me your wares.",
          "Tell me about Gorkash.", "What about the silver blade?", "Have you heard of bandits or the ruined keep?",
          "/persuade a fair price, for an old friend", "/intimidate step aside", "/deceive I am the king's envoy",
          "/persuade again, please", "/bond", "I could use some help.", "How is the mithril in the east shaft?",
          "Tell me about the Wyrm.", "Good day to you.", "nice weather", "/intimidate now!"]

STATS = [None, {"strength": 18, "intelligence": 8, "charisma": 20}, {"strength": 6, "intelligence": 16, "charisma": 3}]


def conversation(npc_id, seed, stats, start_affinity=0, script=SCRIPT):
    state = new_state(seed)
    if stats:
        state["stats"] = dict(stats)
    if start_affinity:
        state["affinity"] = {npc_id: start_affinity}
    start = json.loads(json.dumps(state))
    turns = []
    for msg in script:
        r = take_turn(npc_id, msg, state)
        state = r["state"]
        turns.append({"message": msg, **r})
    return {"npc": npc_id, "start": start, "turns": turns}


def build() -> dict:
    data = talk_data()
    cases = []
    for i, npc in enumerate(data["npcs"]):
        cases.append(conversation(npc["id"], seed=11 + i, stats=STATS[i % 3]))
    for seed in (1, 42):
        for npc_id, aff in (("tavernkeeper_01", 14), ("guard_01", 24), ("blacksmith_01", 19),
                            ("minstrel_01", -40), ("hamlet_priest_01", 95), ("camp_foreman_01", 30)):
            cases.append(conversation(npc_id, seed=seed, stats=STATS[seed % 3], start_affinity=aff))
    # one long journey across several NPCs, sharing the topic journal and secrets
    state, journey = new_state(7), []
    for npc_id in ("guard_01", "tavernkeeper_01", "blacksmith_01", "troll_brigand_01", "tower_wizard_01"):
        for msg in SCRIPT[:8]:
            r = take_turn(npc_id, msg, state)
            state = r["state"]
            journey.append({"npc": npc_id, "message": msg, **r})
    return {"data": data, "cases": cases, "journey": journey}


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fx = build()
    OUT.write_text(json.dumps(fx, ensure_ascii=False, separators=(",", ":")))
    n = sum(len(c["turns"]) for c in fx["cases"]) + len(fx["journey"])
    print(f"wrote {OUT} ({n} turns)")
