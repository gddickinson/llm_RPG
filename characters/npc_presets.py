"""Preset NPCs — loaded from `data/npcs/*.json` (one file per settlement).

Adding a named NPC = adding a JSON entry (stats, position, inventory,
personality, goals, relationships, memories, home_location, faction).
`all_presets()` and `make_npc(id)` build fresh Character instances.
"""

import logging
from typing import Dict, List, Optional, Tuple

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace

logger = logging.getLogger("llm_rpg.npc_presets")


def _load_specs() -> Dict[str, dict]:
    from items.data_loader import load_data_dir
    return load_data_dir("npcs")


NPC_SPECS: Dict[str, dict] = _load_specs()


def make_npc(npc_id: str,
             position: Optional[Tuple[int, int]] = None) -> Character:
    """Build a fresh Character from its data spec."""
    spec = NPC_SPECS[npc_id]
    stats = spec.get("stats", {})
    hp = spec.get("hp", 10)
    npc = Character(
        id=npc_id,
        name=spec["name"],
        character_class=CharacterClass(spec.get("class", "villager")),
        race=CharacterRace(spec.get("race", "human")),
        level=spec.get("level", 1),
        strength=stats.get("strength", 10),
        dexterity=stats.get("dexterity", 10),
        constitution=stats.get("constitution", 10),
        intelligence=stats.get("intelligence", 10),
        wisdom=stats.get("wisdom", 10),
        charisma=stats.get("charisma", 10),
        hp=hp, max_hp=hp,
        position=tuple(position or spec.get("position", (0, 0))),
        inventory=list(spec.get("inventory", [])),
        gold=spec.get("gold", 0),
        symbol=spec.get("symbol", "N"),
        description=spec.get("description", ""),
        personality=dict(spec.get("personality", {})),
        goals=list(spec.get("goals", [])),
        relationships=dict(spec.get("relationships", {})),
    )
    for mem in spec.get("memories", []):
        npc.add_memory(mem["event"], mem.get("importance", 1))
    npc.home_location = spec.get("home_location", "")
    npc.faction = spec.get("faction", "neutral")
    for key, val in spec.get("metadata", {}).items():
        npc.metadata[key] = val
    return npc


def all_presets() -> List[Character]:
    """The world roster (peaceful first, then hostiles). Zone-bound
    residents (P18.2: castle staff etc.) are EXCLUDED — the structure
    populator seats them in their zone, not the open world."""
    open_world = {nid: s for nid, s in NPC_SPECS.items()
                  if not s.get("zone_bound")}
    peaceful = [nid for nid, s in open_world.items()
                if s.get("class") not in ("brigand", "troll", "monster")]
    hostile = [nid for nid in open_world if nid not in peaceful]
    return [make_npc(nid) for nid in peaceful + hostile]


def make_troll_brigand(position=(25, 10)) -> Character:
    """Kept for callers that place Gorkash at a custom position."""
    return make_npc("troll_brigand_01", position=position)
