"""Adventure modules (P6.5) — the DM's atomic bundles.

A module is one coherent adventure: new monsters and items, an optional
building, spawns, placements, a quest chain, scheduled beats, and a
diegetic announcement. It installs ATOMICALLY: a prevalidation pass
checks every piece against the charter before anything mutates, and if
execution still fails partway, everything applied is rolled back and
the budget refunded. Installed modules are recorded in the notebook.

Module spec (all sections optional except module_id + title):
{
  "module_id": "the_rot_court", "title": "The Rot Court",
  "announcement": "rumor the villagers start repeating",
  "monsters": {template_id: spec}, "items": {item_id: spec},
  "building": {name,x,y,w,h,description,properties},
  "spawns": [{"template_id": ..., "position": [x,y]}],
  "placements": [{"item_id": ..., "position": [x,y]}],
  "quests": {quest_id: spec},
  "beats": [{"day_offset": 2, "command": ..., "args": {...}}]
}
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("llm_rpg.dm_modules")

MAX_OPS = 12


def _count_ops(module: dict) -> int:
    return (len(module.get("monsters", {})) +
            len(module.get("items", {})) +
            (1 if module.get("building") else 0) +
            len(module.get("spawns", [])) +
            len(module.get("placements", [])) +
            len(module.get("quests", {})) +
            len(module.get("beats", [])))


def prevalidate(engine, module: dict) -> List[str]:
    """Every problem found, or [] when the module may install."""
    from world.monsters import MONSTER_TEMPLATES
    from items.item_registry import ITEM_REGISTRY
    from engine.dm_api import MAX_ITEM_VALUE, MAX_QUEST_GOLD_BASE
    from characters.character_types import CharacterClass, CharacterRace
    problems = []
    if not module.get("module_id") or not module.get("title"):
        problems.append("module needs module_id and title")
    ops = _count_ops(module)
    if ops == 0:
        problems.append("module is empty")
    if ops > MAX_OPS:
        problems.append(f"module too large ({ops} ops, max {MAX_OPS})")
    if ops > engine.dm.budget_remaining():
        problems.append(f"needs {ops} ops but only "
                        f"{engine.dm.budget_remaining()} budget left")

    new_monsters = set(module.get("monsters", {}))
    new_items = set(module.get("items", {}))
    level_cap = engine.player.level + 2
    for tid, spec in module.get("monsters", {}).items():
        if tid in MONSTER_TEMPLATES:
            problems.append(f"monster '{tid}' already exists")
        if spec.get("level", 1) > level_cap:
            problems.append(f"monster '{tid}' over level cap "
                            f"{level_cap}")
        if not spec.get("name"):
            problems.append(f"monster '{tid}' needs a name")
        try:
            CharacterClass(spec.get("class", "monster"))
            CharacterRace(spec.get("race", "goblin"))
        except ValueError as e:
            problems.append(f"monster '{tid}': {e}")
    for iid, spec in module.get("items", {}).items():
        if iid in ITEM_REGISTRY:
            problems.append(f"item '{iid}' already exists")
        if spec.get("value", 1) > MAX_ITEM_VALUE:
            problems.append(f"item '{iid}' over value cap")
        if not spec.get("name"):
            problems.append(f"item '{iid}' needs a name")

    wmap = engine.world.map
    px, py = engine.player.position
    for spawn in module.get("spawns", []):
        tid = spawn.get("template_id", "")
        if tid not in MONSTER_TEMPLATES and tid not in new_monsters:
            problems.append(f"spawn of unknown monster '{tid}'")
        x, y = spawn.get("position", (-1, -1))
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            problems.append(f"spawn '{tid}' out of bounds")
        elif abs(x - px) + abs(y - py) < 6:
            problems.append(f"spawn '{tid}' too close to the player")
    for placement in module.get("placements", []):
        iid = placement.get("item_id", "")
        if iid not in ITEM_REGISTRY and iid not in new_items:
            problems.append(f"placement of unknown item '{iid}'")
        x, y = placement.get("position", (-1, -1))
        if not (0 <= x < wmap.width and 0 <= y < wmap.height):
            problems.append(f"placement '{iid}' out of bounds")

    building = module.get("building")
    if building:
        if any(loc.name == building.get("name")
               for loc in engine.world.locations):
            problems.append(f"building '{building.get('name')}' "
                            f"already exists")

    qm = engine.quest_manager
    gold_cap = MAX_QUEST_GOLD_BASE + 25 * engine.player.level
    for qid, spec in module.get("quests", {}).items():
        if qm is None:
            problems.append("quests disabled")
            break
        if qid in qm.quests:
            problems.append(f"quest '{qid}' already exists")
        if spec.get("reward_gold", 0) > gold_cap:
            problems.append(f"quest '{qid}' over reward cap")
        giver = spec.get("giver_id", "")
        if giver and engine.npc_manager.get_npc(giver) is None:
            problems.append(f"quest '{qid}' has unknown giver "
                            f"'{giver}'")

    from engine.dm_bridge import ALLOWED_COMMANDS
    for beat in module.get("beats", []):
        if beat.get("day_offset", 0) < 1:
            problems.append("beats need day_offset >= 1")
        if beat.get("command") not in ALLOWED_COMMANDS:
            problems.append(f"beat command "
                            f"'{beat.get('command')}' not allowed")
    return problems


def install_module(engine, module: dict) -> Tuple[bool, str]:
    """Atomic install: prevalidate, execute, roll back on any failure."""
    dm = engine.dm
    problems = prevalidate(engine, module)
    mid = module.get("module_id", "(unnamed)")
    if problems:
        return dm._log("install_module", False,
                       f"{mid}: " + "; ".join(problems[:4]))

    undo = []
    spent_before = dict(dm._spent)

    def fail(step_note: str) -> Tuple[bool, str]:
        for action in reversed(undo):
            try:
                action()
            except Exception as e:
                logger.warning(f"rollback step failed: {e}")
        dm._spent = spent_before
        return dm._log("install_module", False,
                       f"{mid}: rolled back — {step_note}")

    from world.monsters import MONSTER_TEMPLATES
    from items.item_registry import ITEM_REGISTRY

    for tid, spec in module.get("monsters", {}).items():
        ok, note = dm.define_monster(tid, spec)
        if not ok:
            return fail(note)
        undo.append(lambda t=tid: (MONSTER_TEMPLATES.pop(t, None),
                                   dm.defined_monsters.pop(t, None)))
    for iid, spec in module.get("items", {}).items():
        ok, note = dm.define_item(iid, spec)
        if not ok:
            return fail(note)
        undo.append(lambda i=iid: (ITEM_REGISTRY.pop(i, None),
                                   dm.defined_items.pop(i, None)))
    building = module.get("building")
    if building:
        ok, note = dm.add_building(**building)
        if not ok:
            return fail(note)
        bname = building["name"]

        def _unbuild(name=bname):
            engine.world.locations[:] = [
                loc for loc in engine.world.locations
                if loc.name != name]
        undo.append(_unbuild)
    for spawn in module.get("spawns", []):
        ok, note = dm.spawn_npc(spawn["template_id"],
                                tuple(spawn["position"]))
        if not ok:
            return fail(note)
        name = MONSTER_TEMPLATES[spawn["template_id"]]["name"]

        def _unspawn(monster_name=name):
            for nid, npc in list(engine.npc_manager.npcs.items()):
                if npc.name == monster_name and \
                        nid.startswith("enc_"):
                    engine.npc_manager.npcs.pop(nid)
                    break
        undo.append(_unspawn)
    for placement in module.get("placements", []):
        ok, note = dm.place_item(placement["item_id"],
                                 tuple(placement["position"]))
        if not ok:
            return fail(note)
    for qid, spec in module.get("quests", {}).items():
        ok, note = dm.create_quest(qid, spec)
        if not ok:
            return fail(note)
        undo.append(lambda q=qid: (
            engine.quest_manager.quests.pop(q, None),
            engine.radiant_quests._unpost(q)))
    day = dm._day()
    for beat in module.get("beats", []):
        ok, note = dm.schedule_beat(day + beat["day_offset"],
                                    beat["command"],
                                    beat.get("args", {}))
        if not ok:
            return fail(note)

    announcement = module.get("announcement")
    if announcement:
        try:
            engine.world_director.rumors.append(announcement)
            del engine.world_director.rumors[:-5]
        except Exception:
            pass
        dm.narrate(announcement)
    return dm._log("install_module", True,
                   f"{mid}: '{module['title']}' installed "
                   f"({_count_ops(module)} pieces)")
