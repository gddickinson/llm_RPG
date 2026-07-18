"""Validate all game content data files and their cross-references.

Run directly:  python -m items.data_validate   (exit 1 if problems)
Or call `validate_all()` — returns a list of problem strings (empty = OK).

Rules:
- recipes: output + every ingredient is a known item id
- shop catalogs / forage tables / loot tables: known item ids
- monsters: class + race are valid enums; encounter table non-empty
- spells: status effects valid; scroll items cast known spells
- quests: giver is a preset NPC; FETCH targets are item ids; KILL/TALK
  targets are preset NPCs or monster templates; DELIVER "item:npc" resolve
- NPCs: class/race valid; relationships point at preset NPCs; every
  inventory string resolves to a real item
"""

from typing import List

from items.validate_battles import check_battles
from items.validate_packs import check_module_packs


def validate_all() -> List[str]:
    problems: List[str] = []
    problems += _check_recipes()
    problems += _check_shops()
    problems += _check_forage()
    problems += _check_monsters()
    problems += _check_spells()
    problems += _check_quests()
    problems += _check_npcs()
    problems += _check_gathering()
    problems += _check_diaries()
    problems += _check_secrets()
    problems += _check_heart_events()
    problems += check_module_packs()
    problems += _check_diseases()
    problems += _check_pantheon()
    problems += _check_structures()
    problems += _check_traversal()
    problems += check_battles()
    from items.validate_economy import (check_production,
                                        check_building_types,
                                        check_resource_nodes)
    problems += check_production()
    problems += check_building_types()
    problems += check_resource_nodes()
    from items.validate_world import (check_adventurers, check_guildhalls,
                                       check_wildlife, check_building_styles,
                                       check_activities, check_skill_combat,
                                       check_worldcraft, check_enchantments)
    problems += check_adventurers()
    problems += check_guildhalls()
    problems += check_wildlife()
    problems += check_building_styles()
    problems += check_activities()
    problems += check_skill_combat()
    problems += check_worldcraft()
    problems += check_enchantments()
    return problems


def _check_traversal() -> List[str]:
    """traversal.json: known terrain values, classes, lattice skills."""
    import json
    from pathlib import Path
    from world.world_map import TerrainType
    problems = []
    path = Path(__file__).resolve().parent.parent / "data" / \
        "traversal.json"
    if not path.exists():
        return problems
    try:
        rules = json.loads(path.read_text())
    except Exception as e:
        return [f"traversal.json unparseable: {e}"]
    terrains = {t.value for t in TerrainType}
    try:
        from engine.skill_progression import SKILLS
    except Exception:
        SKILLS = {}
    for terrain, rule in rules.items():
        if terrain not in terrains:
            problems.append(f"traversal: unknown terrain '{terrain}'")
        if rule.get("class") not in ("swim", "climb", "slog"):
            problems.append(
                f"traversal[{terrain}]: bad class "
                f"'{rule.get('class')}'")
        skill = rule.get("skill")
        if skill and SKILLS and skill not in SKILLS:
            problems.append(
                f"traversal[{terrain}]: unknown skill '{skill}'")
    return problems


def _check_structures() -> List[str]:
    from world.structures import STRUCTURES, CELL_FURNITURE
    from world.monsters import MONSTER_TEMPLATES
    known = set("WFD.<>KGL") | set(CELL_FURNITURE)   # L = lever (P21.3)
    out = []
    for sid, spec in STRUCTURES.items():
        if not spec.get("attach_to"):
            out.append(f"structure {sid}: needs attach_to")
        levels = spec.get("levels", [])
        if not levels:
            out.append(f"structure {sid}: needs levels")
        for i, lv in enumerate(levels):
            rows = lv.get("grid", [])
            if not rows:
                out.append(f"structure {sid} level {i}: empty grid")
                continue
            for row in rows:
                bad = set(row) - known
                if bad:
                    out.append(f"structure {sid} level {i}: unknown "
                               f"cells {sorted(bad)}")
            for spawn in lv.get("monsters", []):
                if spawn.get("template") not in MONSTER_TEMPLATES:
                    out.append(f"structure {sid} level {i}: unknown "
                               f"monster '{spawn.get('template')}'")
            from characters.npc_presets import NPC_SPECS
            for occ in lv.get("occupants", []):   # P18.2 residents
                if occ.get("npc") not in NPC_SPECS:
                    out.append(f"structure {sid} level {i}: unknown "
                               f"occupant '{occ.get('npc')}'")
            puzzle = lv.get("puzzle")
            if puzzle:
                sigils = sum(r.count("G") for r in rows)
                order = puzzle.get("order", [])
                if sorted(order) != list(range(sigils)):
                    out.append(f"structure {sid} level {i}: puzzle "
                               f"order must permute {sigils} sigils")
                if puzzle.get("wards") not in ("up", "down"):
                    out.append(f"structure {sid} level {i}: puzzle "
                               f"wards must be 'up' or 'down'")
                if len(puzzle.get("names", [])) < sigils:
                    out.append(f"structure {sid} level {i}: puzzle "
                               f"needs a name per sigil")
            if lv.get("chest_loot"):
                from items.item_registry import ITEM_REGISTRY
                for iid in lv["chest_loot"]:
                    if iid not in ITEM_REGISTRY:
                        out.append(f"structure {sid} level {i}: "
                                   f"unknown chest_loot '{iid}'")
                if not any("C" in r for r in rows):
                    out.append(f"structure {sid} level {i}: "
                               f"chest_loot without a Chest cell")
            if i > 0:
                up = any("<" in r for r in rows)
                down = any(">" in r for r in
                           levels[i - 1].get("grid", []))
                if lv.get("position", "below") == "below" and \
                        not (up and down):
                    out.append(f"structure {sid} level {i}: below-"
                               f"level needs '<' and prior '>'")
    return out


def _check_pantheon() -> List[str]:
    from engine.pantheon import GODS
    kinds = ("heal", "bless", "fortune", "cure", "insight")
    out = []
    for gid, god in GODS.items():
        for field in ("name", "title", "domain", "answer", "omen"):
            if not god.get(field):
                out.append(f"god {gid}: missing {field}")
        if god.get("miracle") not in kinds:
            out.append(f"god {gid}: unknown miracle "
                       f"'{god.get('miracle')}'")
        if not god.get("keywords"):
            out.append(f"god {gid}: needs deed keywords")
    return out


def _check_diseases() -> List[str]:
    from engine.disease import DISEASES
    from items.item_registry import ITEM_REGISTRY
    seasons = ("any", "spring", "summer", "autumn", "winter")
    out = []
    for did, spec in DISEASES.items():
        if not spec.get("name") or not spec.get("symptom"):
            out.append(f"disease {did}: needs name + symptom")
        if spec.get("cure_item") not in ITEM_REGISTRY:
            out.append(f"disease {did}: cure_item "
                       f"'{spec.get('cure_item')}' is not a real item")
        if spec.get("season", "any") not in seasons:
            out.append(f"disease {did}: bad season "
                       f"'{spec.get('season')}'")
        if not (1 <= spec.get("duration_days", 0) <= 30):
            out.append(f"disease {did}: duration_days out of range")
        if not (0.0 < spec.get("spread_chance", 0) <= 1.0):
            out.append(f"disease {did}: spread_chance out of range")
    return out


def _check_heart_events() -> List[str]:
    from engine.heart_events import HEART_EVENTS
    from characters.npc_presets import NPC_SPECS
    out = []
    seen = set()
    for npc_id, events in HEART_EVENTS.items():
        if npc_id not in NPC_SPECS:
            out.append(f"heart_events: unknown NPC '{npc_id}'")
        for e in events:
            eid = e.get("id", "")
            if eid in seen:
                out.append(f"heart_events: duplicate id '{eid}'")
            seen.add(eid)
            if not e.get("outline"):
                out.append(f"heart event {eid}: missing outline")
            perk = e.get("perk", {})
            if "item" in perk and not _known_item(perk["item"]):
                out.append(f"heart event {eid}: unknown perk item "
                           f"'{perk['item']}'")
    return out


def _check_secrets() -> List[str]:
    from engine.secrets import SECRETS
    from characters.npc_presets import NPC_SPECS
    from quests.quest_templates import QUEST_TEMPLATES
    from engine.skill_progression import SKILLS
    out = []
    seen_ids = set()
    for npc_id, secrets in SECRETS.items():
        if npc_id not in NPC_SPECS:
            out.append(f"secrets: unknown NPC '{npc_id}'")
        for s in secrets:
            sid = s.get("id", "")
            if sid in seen_ids:
                out.append(f"secrets: duplicate secret id '{sid}'")
            seen_ids.add(sid)
            cond = s.get("condition", {})
            if "quest" in cond and cond["quest"] not in QUEST_TEMPLATES:
                out.append(f"secret {sid}: unknown quest "
                           f"'{cond['quest']}'")
            if "item" in cond and not _known_item(cond["item"]):
                out.append(f"secret {sid}: unknown item '{cond['item']}'")
            if "skill" in cond and cond["skill"] not in SKILLS:
                out.append(f"secret {sid}: unknown skill "
                           f"'{cond['skill']}'")
    return out


def _check_diaries() -> List[str]:
    from engine.diaries import DIARIES
    from engine.skill_progression import SKILLS
    from items.crafting import RECIPES
    out = []
    for region, spec in DIARIES.items():
        for tier, tspec in spec.get("tiers", {}).items():
            for task in tspec.get("tasks", []):
                ttype, target = task.get("type"), task.get("target", "")
                where = f"diary {region}/{tier}"
                if ttype == "collect" and not _known_item(target):
                    out.append(f"{where}: unknown item '{target}'")
                elif ttype == "craft" and target not in RECIPES:
                    out.append(f"{where}: unknown recipe '{target}'")
                elif ttype == "skill" and target not in SKILLS:
                    out.append(f"{where}: unknown skill '{target}'")
                elif ttype not in ("collect", "craft", "skill", "place",
                                   "kill", "quest"):
                    out.append(f"{where}: unknown task type '{ttype}'")
            for iid in tspec.get("reward", {}).get("items", []):
                if not _known_item(iid):
                    out.append(f"diary {region}/{tier}: unknown reward "
                               f"item '{iid}'")
    return out


def _check_gathering() -> List[str]:
    from world.gathering import GATHER_NODES
    from world.world_map import TerrainType
    from engine.skill_progression import SKILLS
    out = []
    for skill_id, spec in GATHER_NODES.items():
        if skill_id not in SKILLS:
            out.append(f"gathering: '{skill_id}' is not a defined skill")
        for t in spec.get("terrain", []):
            try:
                TerrainType(t)
            except ValueError:
                out.append(f"gathering {skill_id}: unknown terrain '{t}'")
        if not _known_item(spec.get("tool", "")) and \
                spec.get("tool") != "axe":
            out.append(f"gathering {skill_id}: unknown tool "
                       f"'{spec.get('tool')}'")
        for tier in spec.get("tiers", []):
            if not _known_item(tier["item"]):
                out.append(f"gathering {skill_id}: unknown tier item "
                           f"'{tier['item']}'")
    return out


def _known_item(item_id: str) -> bool:
    from items.item_registry import ITEM_REGISTRY
    return item_id in ITEM_REGISTRY


def _check_recipes() -> List[str]:
    from items.crafting import RECIPES
    out = []
    for rid, r in RECIPES.items():
        if not _known_item(r.output_id):
            out.append(f"recipe {rid}: unknown output '{r.output_id}'")
        for iid in r.ingredients:
            if not _known_item(iid):
                out.append(f"recipe {rid}: unknown ingredient '{iid}'")
    return out


def _check_shops() -> List[str]:
    from engine.shop import SHOP_CATALOGS
    return [f"shop catalog {cat}: unknown item '{iid}'"
            for cat, ids in SHOP_CATALOGS.items()
            for iid in ids if not _known_item(iid)]


def _check_forage() -> List[str]:
    from world.foraging import TERRAIN_FORAGE_TABLE
    return [f"forage table {terrain}: unknown item '{iid}'"
            for terrain, table in TERRAIN_FORAGE_TABLE.items()
            for iid, _ in table if not _known_item(iid)]


def _check_monsters() -> List[str]:
    from world.monsters import MONSTER_TEMPLATES, encounter_table
    from world.world_map import TerrainType
    from characters.character_types import CharacterClass, CharacterRace
    out = []
    for tid, spec in MONSTER_TEMPLATES.items():
        try:
            CharacterClass(spec.get("class", "monster"))
            CharacterRace(spec.get("race", "goblin"))
        except ValueError as e:
            out.append(f"monster {tid}: {e}")
        for t in spec.get("spawn_terrain", []):
            try:
                TerrainType(t)
            except ValueError:
                out.append(f"monster {tid}: unknown spawn terrain '{t}'")
    if not encounter_table():
        out.append("monsters: encounter table is empty")
    return out


def _check_spells() -> List[str]:
    from engine.spells import SPELL_REGISTRY
    from characters.status_effects import VALID_EFFECTS
    from items.item_registry import ITEM_REGISTRY
    from characters.character_types import CharacterClass
    class_values = {c.value for c in CharacterClass}
    out = []
    for sid, spell in SPELL_REGISTRY.items():
        if spell.status_effect and spell.status_effect not in VALID_EFFECTS:
            out.append(f"spell {sid}: unknown effect "
                       f"'{spell.status_effect}'")
        if not (1 <= spell.tier <= 5):                     # M1 tier range
            out.append(f"spell {sid}: tier {spell.tier} out of 1-5")
        for cv in spell.classes:
            if cv not in class_values:
                out.append(f"spell {sid}: unknown class '{cv}'")
        prereq = (spell.requires or {}).get("prereq")
        if prereq and prereq not in SPELL_REGISTRY:
            out.append(f"spell {sid}: prereq unknown spell '{prereq}'")
    for iid, item in ITEM_REGISTRY.items():
        cast = item.use_effect.get("spell")
        if cast and cast not in SPELL_REGISTRY:
            out.append(f"item {iid}: casts unknown spell '{cast}'")
        taught = item.use_effect.get("teach_spell")
        if taught and taught not in SPELL_REGISTRY:
            out.append(f"item {iid}: teaches unknown spell '{taught}'")
    return out


def _check_quests() -> List[str]:
    from quests.quest_templates import QUEST_TEMPLATES
    from quests.quest import ObjectiveType
    from characters.npc_presets import NPC_SPECS
    from world.monsters import MONSTER_TEMPLATES
    from characters.character_types import CharacterClass
    class_values = {c.value for c in CharacterClass}
    # P38.3: the Sunken Tome adventure seeds its cast from data/adventure_tome.
    # json (kept out of data/npcs/), so they are valid givers/actors too
    adv_npcs = set()
    try:
        from items.data_loader import load_data_file
        adv_npcs = set(
            (load_data_file("adventure_tome.json") or {}).get("npcs", {}))
    except Exception:
        pass
    out = []
    # KILL matches npc id OR class; TALK matches npc id
    known_actor = lambda a: (a in NPC_SPECS or a in MONSTER_TEMPLATES
                             or a in class_values or a in adv_npcs)
    for qid, factory in QUEST_TEMPLATES.items():
        quest = factory()
        if not quest.giver_id:
            out.append(f"quest {qid}: no giver — the GUI's only "
                       f"turn-in path is dialog with the giver")
        elif quest.giver_id not in NPC_SPECS and quest.giver_id not in adv_npcs:
            out.append(f"quest {qid}: unknown giver '{quest.giver_id}'")
        for iid in quest.reward_items:
            if not _known_item(iid):
                out.append(f"quest {qid}: unknown reward item '{iid}'")
        prereq = quest.metadata.get("prereq_quest")
        if prereq and prereq not in QUEST_TEMPLATES:
            out.append(f"quest {qid}: unknown prereq '{prereq}'")
        for unlock in quest.metadata.get("reward_unlocks", []):
            kind, _, key = unlock.partition(":")
            if kind == "spell":
                from engine.spells import SPELL_REGISTRY
                if key not in SPELL_REGISTRY:
                    out.append(f"quest {qid}: unlock of unknown spell "
                               f"'{key}'")
            elif kind == "topic":
                from engine.topics import TOPICS
                if key not in TOPICS:
                    out.append(f"quest {qid}: unlock of unknown topic "
                               f"'{key}'")
            elif kind == "teleport":
                from engine.travel import DESTINATIONS
                if key not in [d[0] for d in DESTINATIONS]:
                    out.append(f"quest {qid}: unlock of unknown "
                               f"teleport '{key}'")
            else:
                out.append(f"quest {qid}: unknown unlock kind "
                           f"'{unlock}'")
        for obj in quest.objectives:
            t = obj.target
            if obj.obj_type == ObjectiveType.FETCH and not _known_item(t):
                out.append(f"quest {qid}: FETCH of unknown item '{t}'")
            elif obj.obj_type in (ObjectiveType.KILL, ObjectiveType.TALK) \
                    and not known_actor(t):
                out.append(f"quest {qid}: {obj.obj_type.value} target "
                           f"'{t}' is not a preset NPC or monster")
            elif obj.obj_type == ObjectiveType.DELIVER and ":" in t:
                iid, _, npc = t.partition(":")
                if not _known_item(iid):
                    out.append(f"quest {qid}: DELIVER unknown item '{iid}'")
                if npc not in NPC_SPECS:
                    out.append(f"quest {qid}: DELIVER to unknown NPC "
                               f"'{npc}'")
    return out


def _check_npcs() -> List[str]:
    from characters.npc_presets import NPC_SPECS
    from characters.character_types import CharacterClass, CharacterRace
    from engine.demo_setup import upgrade_item_string
    out = []
    for nid, spec in NPC_SPECS.items():
        try:
            CharacterClass(spec.get("class", "villager"))
            CharacterRace(spec.get("race", "human"))
        except ValueError as e:
            out.append(f"npc {nid}: {e}")
        for other in spec.get("relationships", {}):
            if other not in NPC_SPECS:
                out.append(f"npc {nid}: relationship with unknown NPC "
                           f"'{other}'")
        for entry in spec.get("inventory", []):
            if isinstance(entry, str) and \
                    isinstance(upgrade_item_string(entry), str):
                out.append(f"npc {nid}: inventory entry '{entry}' does "
                           f"not resolve to any item")
    return out


if __name__ == "__main__":
    import sys
    issues = validate_all()
    if issues:
        print(f"{len(issues)} content problem(s):")
        for p in issues:
            print(f"  - {p}")
        sys.exit(1)
    print("All content data files validate cleanly.")
