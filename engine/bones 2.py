"""Bones (P12.13) — your failures become the world's content.

NetHack's bones files, single-player: when a campaign truly ends —
slain at the bottom of the dying ladder — the site is SNAPSHOT
into the Legendarium (`bones.json` beside the DM's library, same
LLM_RPG_DM_LIBRARY root): who fell, where, to what, at what level,
carrying what.

Every NEW campaign rolls 1-in-3 to load one bones entry: a hostile
GHOST of the fallen hero rises at (near) the spot they died —
level-scaled, and it FLIES (P11.4) — guarding the dead one's gear
scattered on the ground. Most of that gear rises HAUNTED: equip a
haunted piece and the curse settles on you (P12.2's cursed status)
until it fades. Slay the ghost and the legend is laid to rest
(recorded in the Legendarium's tail like any DM creation).
"""

import json
import logging
import os
import random
from typing import Optional

logger = logging.getLogger("llm_rpg.bones")

BONES_CAP = 10
LOAD_CHANCE = 1.0 / 3.0
HAUNT_CHANCE = 0.7
CURSE_TURNS = 30


def _bones_file() -> str:
    from engine.dm_library import library_root
    return os.path.join(library_root(), "bones.json")


def load_all() -> list:
    try:
        with open(_bones_file()) as f:
            return json.load(f)
    except Exception:
        return []


def _save_all(entries: list) -> None:
    try:
        os.makedirs(os.path.dirname(_bones_file()), exist_ok=True)
        with open(_bones_file(), "w") as f:
            json.dump(entries[-BONES_CAP:], f, indent=2)
    except Exception as e:
        logger.warning(f"bones save failed: {e}")


def record_bones(engine, slayer=None) -> dict:
    """A campaign ends in death: snapshot the site."""
    player = engine.player
    gear = [getattr(it, "id", "") for it in player.inventory
            if getattr(it, "id", "")]
    try:
        from characters.equipment import get_equipment
        gear += [it.id for it in get_equipment(player).values()
                 if it is not None]
    except Exception:
        pass
    entry = {
        "name": player.name,
        "level": getattr(player, "level", 1),
        "klass": getattr(getattr(player, "character_class", None),
                         "value", "adventurer"),
        "position": list(player.position),
        "day": engine.world.time // (24 * 60),
        "slayer": getattr(slayer, "name", "their wounds"),
        "gear": gear[:8],
    }
    entries = load_all()
    entries.append(entry)
    _save_all(entries)
    logger.info(f"bones recorded for {player.name}")
    return entry


def maybe_load_bones(engine, rng: random.Random = None,
                     chance: float = LOAD_CHANCE) -> Optional[str]:
    """New campaign: 1-in-3, a past failure haunts this world."""
    rng = rng or random.Random()
    entries = load_all()
    if not entries or rng.random() >= chance:
        return None
    bone = rng.choice(entries)
    spot = _landing(engine, bone.get("position", [10, 10]))
    if spot is None:
        return None
    ghost = _raise_ghost(engine, bone, spot)
    _scatter_gear(engine, bone, spot, rng)
    msg = (f"[Legend] A restless shade walks this land — "
           f"{bone['name']}, who fell to {bone['slayer']} on "
           f"day {bone['day']} of another story.")
    engine.memory_manager.add_event(msg)
    return msg


def _landing(engine, pos) -> Optional[tuple]:
    from world.world_map import TerrainType
    wmap = engine.world.map
    bx = max(1, min(wmap.width - 2, int(pos[0])))
    by = max(1, min(wmap.height - 2, int(pos[1])))
    for r in range(0, 8):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = bx + dx, by + dy
                if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                    continue
                if wmap.terrain[y][x] in (TerrainType.GRASS,
                                          TerrainType.ROAD,
                                          TerrainType.SCORCHED) and \
                        wmap.get_character_at(x, y) is None:
                    return (x, y)
    return None


def _raise_ghost(engine, bone, spot):
    from characters.character import Character
    from characters.character_types import (CharacterClass,
                                            CharacterRace)
    level = max(1, int(bone.get("level", 1)))
    hp = 10 + 4 * level
    ghost = Character(
        id=f"ghost_{bone['name'].lower().replace(' ', '_')}",
        name=f"Ghost of {bone['name']}",
        character_class=CharacterClass("monster"),
        race=CharacterRace("goblin"),
        level=level + 1,
        hp=hp, max_hp=hp,
        position=spot,
        symbol="G",
        description=(f"The shade of {bone['name']} the "
                     f"{bone.get('klass', 'adventurer')}, slain by "
                     f"{bone['slayer']}. It does not rest."),
        personality={"traits": ["hostile", "mournful"]},
        goals=["Guard what was mine"],
        inventory=[],
        strength=10 + level, dexterity=12, constitution=10,
        intelligence=8, wisdom=8, charisma=6,
        metadata={"behavior": {"flying": True, "ghost": True},
                  "home_pos": list(spot)},
    )
    engine.npc_manager.add_npc(ghost)
    engine.world.map.place_character(ghost, *spot)
    return ghost


def _scatter_gear(engine, bone, spot, rng) -> None:
    from items.item_registry import create_item
    x, y = spot
    for i, item_id in enumerate(bone.get("gear", [])):
        item = create_item(item_id)
        if item is None:
            continue
        if rng.random() < HAUNT_CHANCE:
            item.name = f"Haunted {item.name}"
            eff = getattr(item, "use_effect", None)
            if isinstance(eff, dict):
                eff["haunted"] = True
        engine.world.add_item_to_ground(
            item, x + (i % 3) - 1, y + (i // 3) - 1)


def on_equip_haunted(character, item) -> Optional[str]:
    """Equipping the gear of the dead invites their misfortune."""
    if not (getattr(item, "use_effect", None) or {}).get("haunted"):
        return None
    try:
        from characters.status_effects import apply_effect
        apply_effect(character, "cursed", duration=CURSE_TURNS)
    except Exception:
        return None
    return (f"A cold that isn't weather settles into your arms — "
            f"the {item.name} remembers its dead.")
