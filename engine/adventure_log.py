"""Adventure Leads — the player-facing discoverability of the seeded adventures
(George: with rival heroes now racing to clear them, the player needs to SEE
what deeds are abroad and where). `leads(engine)` enumerates each seeded
adventure's state — OPEN (find the giver), ACTIVE (you've begun it), RIVAL (an
NPC is closing on it — hurry!), or ENDED — with the giver, their settlement,
and a compass bearing from the hero; `lines(engine)` renders the block the
Y-journal shows beside the topics and chronicle. Pure reads over engine state.
"""

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("llm_rpg.adventure_log")

# (engine attribute, finale quest id, the act-1 quest whose status ⇒ 'begun')
_ADVENTURES = (
    ("emberfell", "q_emberfell_reckoning", "q_emberfell_raids"),
    ("blackbanner", "q_blackbanner_reckoning", "q_blackbanner_raids"),
    ("wychwood", "q_wychwood_reckoning", "q_wychwood_vanishings"),
    ("ravenmoor", "q_ravenmoor_reckoning", "q_ravenmoor_hollow"),
)

_COMPASS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")


def _bearing(frm, to) -> str:
    import math
    dx, dy = to[0] - frm[0], frm[1] - to[1]     # screen y grows downward
    if dx == 0 and dy == 0:
        return "here"
    ang = math.degrees(math.atan2(dy, dx)) % 360
    return _COMPASS[int((ang + 22.5) % 360 // 45)]


def _title(adv_id: str) -> str:
    from items.data_loader import load_data_file
    try:
        return (load_data_file(f"{adv_id}.json") or {}).get(
            "title", adv_id.title())
    except Exception:
        return adv_id.title()


def _giver(engine, finale_qid: str):
    """The finale quest's giver — (name, position) — or (None, None)."""
    q = engine.quest_manager.quests.get(finale_qid) if \
        engine.quest_manager else None
    gid = getattr(q, "giver_id", None) if q else None
    npc = engine.npc_manager.get_npc(gid) if gid else None
    if npc is None:
        return None, None
    return npc.name, tuple(npc.position)


def _rival_advs(engine) -> set:
    na = getattr(engine, "npc_adventuring", None)
    if na is None:
        return set()
    return {st.get("adv") for st in na.active.values()}


def _begun(engine, act1_qid: str) -> bool:
    from quests.quest import QuestStatus
    q = engine.quest_manager.quests.get(act1_qid) if \
        engine.quest_manager else None
    return q is not None and q.status in (
        QuestStatus.ACTIVE, QuestStatus.COMPLETED, QuestStatus.TURNED_IN)


def leads(engine) -> List[dict]:
    rivals = _rival_advs(engine)
    try:
        ppos = tuple(engine.player.position)
    except Exception:
        ppos = (0, 0)
    out = []
    for adv_id, finale, act1 in _ADVENTURES:
        sub = getattr(engine, adv_id, None)
        if sub is None or not sub.is_active():
            continue
        if getattr(sub, "is_resolved", lambda: False)():
            status = "ended"
        elif _begun(engine, act1):
            status = "active"
        elif adv_id in rivals:
            status = "rival"
        else:
            status = "open"
        giver, gpos = _giver(engine, finale)
        out.append({"id": adv_id, "title": _title(adv_id), "status": status,
                    "giver": giver,
                    "bearing": _bearing(ppos, gpos) if gpos else None})
    return out


def lines(engine) -> List[str]:
    ls = leads(engine)
    if not ls:
        return []
    out = ["", "Adventure Leads", "(deeds abroad in the land)", ""]
    for l in ls:
        if l["status"] == "ended":
            out.append(f"  {l['title']} — ended.")
            continue
        where = ""
        if l["giver"]:
            where = f" — seek {l['giver']}"
            if l["bearing"] and l["bearing"] != "here":
                where += f" ({l['bearing']})"
        if l["status"] == "rival":
            out.append(f"  {l['title']} — a rival hero is closing in!{where}")
        elif l["status"] == "active":
            out.append(f"  {l['title']} — underway.{where}")
        else:
            out.append(f"  {l['title']}{where}.")
    return out
