"""Read-only views of the game's content for the web pages: bestiary, spellbook, items + recipes, the authored adventures.

Everything is loaded with the game's own loaders (items.data_loader) from data/*.json, so the pages show exactly the
content the game uses. Nothing here is computed or invented beyond picking fields and joining ids to names.
"""
from functools import lru_cache

from items.data_loader import load_data_dir, load_data_file

ADVENTURE_FILES = ["adventure_tome.json", "emberfell.json", "blackbanner.json", "wychwood.json", "ravenmoor.json"]
# adventure_tome.json and ravenmoor.json predate the generic seeder and carry no id/title/rumor; these come from the
# seeder modules' own docstrings (engine/adventure_tome.py, engine/ravenmoor.py) and README.md.
_LEGACY = {"adventure_tome.json": {"id": "tome", "title": "The Sunken Tome of Vael'Zhur"},
           "ravenmoor.json": {"id": "ravenmoor"}}
_THEMES = {"tome": "drowned / undead", "emberfell": "dragon", "blackbanner": "outlaw war", "wychwood": "witch / curse",
           "ravenmoor": "barrow undead"}                 # README.md, "The built-in adventures"


@lru_cache(maxsize=None)
def monsters() -> list:
    out = []
    for mid, m in load_data_file("monsters.json").items():
        beh = m.get("behavior", {}) or {}
        out.append({
            "id": mid, "name": m["name"], "level": m.get("level", 1), "hp": m.get("hp"), "race": m.get("race"),
            "description": m.get("description", ""), "damage": m.get("natural_damage"), "speed": m.get("speed", 1.0),
            "stats": m.get("stats", {}), "goals": m.get("goals", []), "undead": m.get("undead_type") if m.get("undead") else None,
            "active": m.get("active"), "terrain": m.get("spawn_terrain", []), "dungeon": bool(m.get("dungeon")),
            "min_depth": m.get("min_depth"), "boss": bool(beh.get("boss") or m.get("boss_depth")),
            "flying": bool(beh.get("flying")), "breath": beh.get("breath"),
            "group": m.get("group"), "preys_on": m.get("preys_on", []), "drops": m.get("guaranteed_drops", []),
            "traits": sorted(k for k, v in beh.items() if v and k not in ("boss", "flying", "breath")),
            "wandering": m.get("encounter_weight", 0) > 0,
        })
    return sorted(out, key=lambda r: (r["level"], r["name"]))


@lru_cache(maxsize=None)
def spells() -> list:
    out = []
    for sid, s in load_data_file("spells.json").items():
        out.append({
            "id": sid, "name": s["name"], "school": s.get("school"), "tier": s.get("tier"), "mana": s.get("mana_cost"),
            "range": s.get("range"), "damage": s.get("damage"), "heal": s.get("heal"), "area": s.get("area"),
            "status": s.get("status_effect"), "duration": s.get("duration"), "classes": s.get("classes", []),
            "concentration": bool(s.get("concentration")), "requires": s.get("requires"),
            "world": bool(s.get("world_effect")), "shapeshift": bool(s.get("shapeshift")),
            "description": s.get("description", ""),
        })
    return sorted(out, key=lambda r: (r["tier"] or 0, r["school"] or "", r["name"]))


@lru_cache(maxsize=None)
def _items_raw() -> dict:
    return load_data_dir("items")


@lru_cache(maxsize=None)
def items() -> list:
    out = []
    for iid, it in _items_raw().items():
        meta = it.get("metadata", {}) or {}
        out.append({
            "id": iid, "name": it["name"], "type": it.get("item_type"), "rarity": it.get("rarity") or "common",
            "value": it.get("value"), "damage": it.get("damage"), "damage_kind": it.get("damage_kind"),
            "weapon_kind": it.get("weapon_kind"), "armor": it.get("armor"), "heal": it.get("heal_amount"),
            "two_handed": bool(it.get("two_handed")), "bonuses": it.get("equip_bonuses") or {},
            "spell": (it.get("use_effect") or {}).get("spell"), "charges": meta.get("charges"),
            "description": it.get("description", ""),
        })
    return sorted(out, key=lambda r: (r["type"] or "", r["name"]))


def _name(item_id: str) -> str:
    it = _items_raw().get(item_id)
    return it["name"] if it else item_id.replace("_", " ")


@lru_cache(maxsize=None)
def recipes() -> list:
    out = []
    for rid, r in load_data_file("recipes.json").items():
        out.append({
            "id": rid, "output": _name(r.get("output_id", rid)), "output_id": r.get("output_id", rid),
            "ingredients": [{"id": k, "name": _name(k), "qty": v} for k, v in r.get("ingredients", {}).items()],
            "gold": r.get("gold_cost", 0), "skill": r.get("skill"), "min_skill": r.get("min_skill"),
            "station": r.get("required_property"),
        })
    return out


def _quest_chain(quests: dict, cast: set) -> list:
    """The adventure's quests: those its own cast gives, in prerequisite order."""
    mine = {qid: q for qid, q in quests.items() if q.get("giver_id") in cast}
    order, seen = [], set()

    def visit(qid):
        if qid in seen or qid not in mine:
            return
        seen.add(qid)
        visit(mine[qid].get("prereq_quest"))
        order.append(qid)
    for qid in mine:
        visit(qid)
    out = []
    for qid in order:
        q = mine[qid]
        out.append({
            "id": qid, "title": q.get("title", qid), "description": q.get("description", ""),
            "objectives": [o.get("description", "") for o in q.get("objectives", [])],
            "giver": q.get("giver_id"), "gold": q.get("reward_gold", 0), "xp": q.get("reward_xp", 0),
            "choices": [{"label": c.get("label", ""), "text": c.get("legend", ""), "gold": c.get("gold"),
                         "xp": c.get("xp"), "items": [_name(i) for i in c.get("items", [])]}
                        for c in q.get("reward_choices", [])],
            "finale": bool(q.get("resolves_adventure") or q.get("reward_choices")),
        })
    return out


@lru_cache(maxsize=None)
def adventures() -> list:
    quests = load_data_file("quests.json")
    mons = load_data_file("monsters.json")
    out = []
    for fname in ADVENTURE_FILES:
        d = load_data_file(fname)
        meta = {**_LEGACY.get(fname, {}), **{k: d[k] for k in ("id", "title") if k in d}}
        aid = meta.get("id", fname[:-5])
        cast = d.get("npcs", {})
        chain = _quest_chain(quests, set(cast))
        foes = []
        for f in d.get("foes", []):
            m = mons.get(f.get("template"), {})
            foes.append({"name": m.get("name", f.get("template")), "level": m.get("level"), "count": f.get("count", 1),
                         "boss": bool(f.get("boss")), "area": f.get("area")})
        out.append({
            "id": aid, "file": f"data/{fname}", "theme": _THEMES.get(aid, ""),
            "title": meta.get("title") or (d.get("title") or aid.title()),
            "rumor": (d.get("rumor") or "").replace("[Realm] ", ""),
            "areas": [{"id": a.get("id"), "name": a.get("name"), "kind": a.get("kind"), "near": a.get("near"),
                       "legend": a.get("legend", "")} for a in d.get("areas", [])],
            "cast": [{"id": k, "name": v.get("name"), "class": v.get("class"), "race": v.get("race"),
                      "level": v.get("level"), "description": v.get("description", ""),
                      "traits": (v.get("personality") or {}).get("traits", []), "goals": v.get("goals", []),
                      "quest_giver": bool((v.get("metadata") or {}).get("quest_giver"))} for k, v in cast.items()],
            "clues": [{"item": _name(c.get("item")), "area": c.get("area")} for c in d.get("clues", [])],
            "foes": foes, "quests": chain, "resolved": d.get("resolved", ""),
        })
    return out


def info() -> dict:
    from engine.topics import TOPICS
    from characters.npc_presets import NPC_SPECS
    return {
        "title": "LLM-RPG",
        "tagline": "A D&D-style RPG with a living world, LLM-powered NPCs, and heroes that adventure on their own.",
        "counts": {"monsters": len(monsters()), "spells": len(spells()), "items": len(items()),
                   "recipes": len(recipes()), "adventures": len(adventures()), "npcs": len(NPC_SPECS),
                   "topics": len(TOPICS), "quests": len(load_data_file("quests.json")),
                   "schools": len({s["school"] for s in spells()})},
    }
