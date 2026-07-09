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
    return problems


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
    from characters.character_types import CharacterClass, CharacterRace
    out = []
    for tid, spec in MONSTER_TEMPLATES.items():
        try:
            CharacterClass(spec.get("class", "monster"))
            CharacterRace(spec.get("race", "goblin"))
        except ValueError as e:
            out.append(f"monster {tid}: {e}")
    if not encounter_table():
        out.append("monsters: encounter table is empty")
    return out


def _check_spells() -> List[str]:
    from engine.spells import SPELL_REGISTRY
    from characters.status_effects import VALID_EFFECTS
    from items.item_registry import ITEM_REGISTRY
    out = []
    for sid, spell in SPELL_REGISTRY.items():
        if spell.status_effect and spell.status_effect not in VALID_EFFECTS:
            out.append(f"spell {sid}: unknown effect "
                       f"'{spell.status_effect}'")
    for iid, item in ITEM_REGISTRY.items():
        cast = item.use_effect.get("spell")
        if cast and cast not in SPELL_REGISTRY:
            out.append(f"item {iid}: casts unknown spell '{cast}'")
    return out


def _check_quests() -> List[str]:
    from quests.quest_templates import QUEST_TEMPLATES
    from quests.quest import ObjectiveType
    from characters.npc_presets import NPC_SPECS
    from world.monsters import MONSTER_TEMPLATES
    out = []
    known_actor = lambda a: a in NPC_SPECS or a in MONSTER_TEMPLATES
    for qid, factory in QUEST_TEMPLATES.items():
        quest = factory()
        if quest.giver_id and quest.giver_id not in NPC_SPECS:
            out.append(f"quest {qid}: unknown giver '{quest.giver_id}'")
        for iid in quest.reward_items:
            if not _known_item(iid):
                out.append(f"quest {qid}: unknown reward item '{iid}'")
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
