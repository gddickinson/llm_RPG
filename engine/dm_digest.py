"""The world digest (P6.2) — what the Dungeon Master sees.

`build_digest(engine)` produces one compact, JSON-serializable dict:
the player's sheet, the named-NPC roster with feelings and opinions,
world systems state (factions, shortages, rumors, board), the monster
census, recent events, and the DM's own notebook/schedule/budget.

Every DM driver (session bridge, autonomous LLM) reads exactly this.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("llm_rpg.dm_digest")

RECENT_EVENTS = 15
NOTEBOOK_TAIL = 15
MAX_NPCS = 25


def build_digest(engine) -> Dict[str, Any]:
    return {
        "meta": _meta(engine),
        "player": _player(engine),
        "npcs": _npcs(engine),
        "world": _world(engine),
        "recent_events": [
            str(e) for e in
            engine.memory_manager.get_recent_history(RECENT_EVENTS)],
        "dm": _dm(engine),
    }


def _meta(engine) -> Dict[str, Any]:
    return {
        "day": engine.world.time // (24 * 60),
        "time": engine.world.get_formatted_time(),
        "weather": engine.current_weather(),
        "in_zone": getattr(getattr(engine, "active_zone", lambda: None)()
                           , "name", None),
    }


def _player(engine) -> Dict[str, Any]:
    p = engine.player
    if p is None:
        return {}
    meta = p.metadata or {}
    loc = engine.world.get_location_at(*p.position)
    from engine.skill_progression import (all_skill_ids,
                                          get_skill_level)
    qm = engine.quest_manager
    active_quests = []
    if qm:
        for q in qm.active():
            objs = [f"{o.description} ({o.progress}/{o.required})"
                    for o in q.objectives]
            active_quests.append({"id": q.id, "title": q.title,
                                  "objectives": objs})
    from characters.equipment import get_equipment
    eq = {slot: (it.name if it else None)
          for slot, it in get_equipment(p).items()}
    return {
        "name": p.name,
        "class": p.character_class.value,
        "race": p.race.value,
        "level": p.level,
        "hp": [p.hp, p.max_hp],
        "gold": p.gold,
        "bank": meta.get("bank", 0),
        "position": list(p.position),
        "location": loc.name if loc else "wilderness",
        "skills": {sid: get_skill_level(p, sid)
                   for sid in all_skill_ids()},
        "quest_points": engine.guild.quest_points(),
        "guild_rank": engine.guild.rank(),
        "active_quests": active_quests,
        "equipment": eq,
        "recent_deeds": meta.get("recent_deeds", [])[-5:],
        "topics_known": list(meta.get("topics_known", [])),
        "legends_found": list(meta.get("legends_known", [])),
        "pets": list(meta.get("pets", [])),
    }


def _npcs(engine) -> List[Dict[str, Any]]:
    from engine.npc_memory import opinions
    out = []
    player_id = engine.player.id if engine.player else ""
    for npc in engine.npc_manager.npcs.values():
        if npc.id.startswith(("enc_", "tut_")):
            continue
        loc = engine.world.get_location_at(*npc.position)
        ops = opinions(npc)
        out.append({
            "id": npc.id,
            "name": npc.name,
            "class": npc.character_class.value,
            "alive": npc.is_active(),
            "location": loc.name if loc else "wilderness",
            "feeling_toward_player":
                npc.get_relationship(player_id),
            "latest_opinion": ops[-1] if ops else None,
        })
        if len(out) >= MAX_NPCS:
            break
    return out


def _world(engine) -> Dict[str, Any]:
    monsters: Dict[str, int] = {}
    for npc in engine.npc_manager.npcs.values():
        if npc.id.startswith("enc_") and npc.is_active():
            monsters[npc.name] = monsters.get(npc.name, 0) + 1
    board = []
    try:
        b = engine.quest_board_manager.board_at("Oakvale Tavern")
        if b:
            for qid in b.posted_quest_ids:
                q = engine.quest_manager.get(qid)
                if q and q.status.value == "available":
                    board.append({"id": qid, "title": q.title})
    except Exception:
        pass
    now = engine.world.time
    shortages = {}
    try:
        shortages = {iid: exp - now for iid, exp in
                     engine.world_director.shortages.items()
                     if exp > now}
    except Exception:
        pass
    return {
        "locations": [{"name": loc.name,
                       "type": (loc.properties or {}).get("type", "")}
                      for loc in engine.world.locations],
        "factions": getattr(engine.faction_ticker, "state", {}),
        "player_faction_rep":
            (engine.player.metadata or {}).get("faction_rep", {}),
        "shortages_minutes_left": shortages,
        "rumors": list(getattr(engine.world_director, "rumors", [])),
        "board_notices": board,
        "monsters_at_large": monsters,
    }


def _dm(engine) -> Dict[str, Any]:
    dm = engine.dm
    return {
        "budget_remaining": dm.budget_remaining(),
        "notebook_tail": dm.notebook[-NOTEBOOK_TAIL:],
        "scheduled_beats": list(dm.scheduled),
        "defined_monsters": list(dm.defined_monsters),
        "defined_items": list(dm.defined_items),
    }
