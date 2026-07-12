"""Module-pack validator (split from data_validate.py, P17.4).

The heftiest single cross-reference check — campaign packs must be
installable on any brand-new level-1 game (valid enums, resolvable
giver, charter-sized rewards, allowed beat commands, ≤ MAX_OPS,
shipped structures obeying the same shapes). Lifted to its own
module to keep the main validator under the file-size line.
"""

from typing import List


def check_module_packs() -> List[str]:
    """Packs must be installable on any new game: valid enums, resolvable
    giver, charter-sized rewards, allowed beat commands, ≤ MAX_OPS."""
    from engine.module_packs import discover_packs
    from engine.dm_modules import _count_ops, MAX_OPS
    from engine.dm_bridge import ALLOWED_COMMANDS
    from engine.dm_api import MAX_ITEM_VALUE, MAX_QUEST_GOLD_BASE
    from characters.npc_presets import NPC_SPECS
    from characters.character_types import CharacterClass, CharacterRace
    out = []
    for pack in discover_packs():
        pid = pack.get("module_id", "(unnamed)")
        if not pack.get("module_id") or not pack.get("title"):
            out.append(f"pack {pid}: needs module_id and title")
        if _count_ops(pack) > MAX_OPS:
            out.append(f"pack {pid}: too large ({_count_ops(pack)} ops)")
        for tid, spec in pack.get("monsters", {}).items():
            if not spec.get("name"):
                out.append(f"pack {pid}: monster {tid} needs a name")
            if spec.get("level", 1) > 3:
                out.append(f"pack {pid}: monster {tid} over level 3 — "
                           f"packs install for brand-new level-1 players")
            try:
                CharacterClass(spec.get("class", "monster"))
                CharacterRace(spec.get("race", "goblin"))
            except ValueError as e:
                out.append(f"pack {pid}: monster {tid}: {e}")
        for iid, spec in pack.get("items", {}).items():
            if not spec.get("name"):
                out.append(f"pack {pid}: item {iid} needs a name")
            if spec.get("value", 1) > MAX_ITEM_VALUE:
                out.append(f"pack {pid}: item {iid} over value cap")
        known = set(pack.get("monsters", {}))
        for spawn in pack.get("spawns", []):
            if spawn.get("template_id") not in known and \
                    "position" not in spawn and \
                    spawn.get("anchor") != "wilderness":
                out.append(f"pack {pid}: spawn needs a position or "
                           f"anchor")
        for qid, spec in pack.get("quests", {}).items():
            giver = spec.get("giver_id", "")
            if not giver or giver not in NPC_SPECS:
                out.append(f"pack {pid}: quest {qid} giver "
                           f"'{giver}' is not a preset NPC")
            if spec.get("reward_gold", 0) > MAX_QUEST_GOLD_BASE:
                out.append(f"pack {pid}: quest {qid} over the level-1 "
                           f"reward cap ({MAX_QUEST_GOLD_BASE})")
        for beat in pack.get("beats", []):
            if beat.get("command") not in ALLOWED_COMMANDS:
                out.append(f"pack {pid}: beat command "
                           f"'{beat.get('command')}' not allowed")
            if beat.get("day_offset", 0) < 1:
                out.append(f"pack {pid}: beats need day_offset >= 1")
        # P14.2b: shipped structures obey the same charter shapes
        from world.structures import CELL_FURNITURE
        from world.monsters import MONSTER_TEMPLATES as MT
        from items.item_registry import ITEM_REGISTRY as IR
        known = set("WFD.<>KGL") | set(CELL_FURNITURE)   # L = lever (P21.3)
        for sid, sspec in pack.get("structures", {}).items():
            for i, lv in enumerate(sspec.get("levels", [])):
                bad = set("".join(lv.get("grid", []))) - known
                if bad:
                    out.append(f"pack {pid}: structure {sid} level "
                               f"{i} unknown cells {sorted(bad)}")
                for spawn in lv.get("monsters", []):
                    if spawn.get("template") not in MT:
                        out.append(f"pack {pid}: structure {sid} "
                                   f"unknown monster "
                                   f"'{spawn.get('template')}'")
                for iid in lv.get("chest_loot", []):
                    if iid not in IR:
                        out.append(f"pack {pid}: structure {sid} "
                                   f"unknown item '{iid}'")
    return out
