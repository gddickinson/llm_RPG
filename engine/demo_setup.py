"""Demo game world setup — player + initial quest offerings.

Extracted from GameEngine to keep that file under the 500-line budget.
"""

import logging
from typing import Any

from characters.character import Character
from characters.character_types import CharacterClass, CharacterRace
from items.item_registry import create_item, item_by_name

logger = logging.getLogger("llm_rpg.demo_setup")


def upgrade_item_string(item_or_str: Any) -> Any:
    """Convert a bare string inventory entry to a real Item where possible."""
    if not isinstance(item_or_str, str):
        return item_or_str
    item = create_item(item_or_str)
    if item:
        return item
    item = create_item(item_or_str.replace(" ", "_").lower())
    if item:
        return item
    item = item_by_name(item_or_str)
    return item if item else item_or_str


def create_default_player(spec=None) -> Character:
    """Build the starting player character.

    Parameters
    ----------
    spec : CharacterSpec | dict | None
        Optional spec from the character creator. If None, builds the
        legacy default warrior.
    """
    if spec is None:
        name = "Player"
        race = CharacterRace.HUMAN
        klass = CharacterClass.WARRIOR
        stats = {"strength": 14, "dexterity": 12, "constitution": 14,
                 "intelligence": 10, "wisdom": 10, "charisma": 12}
        starters = ["sword", "shield", "potion", "bow", "arrow"]
        gold = 50
    else:
        # Spec may be a CharacterSpec dataclass or a dict
        name = getattr(spec, "name", None) or spec.get("name", "Player")
        race = getattr(spec, "race", None) or CharacterRace(spec.get("race", "human"))
        klass = getattr(spec, "character_class", None) or \
                CharacterClass(spec.get("class", "warrior"))
        stats = getattr(spec, "stats", None) or spec.get("stats", {})
        # Starting items by class
        try:
            from ui.character_creator import CLASS_STARTERS
            starter_ids, _ = CLASS_STARTERS.get(klass, (["sword"], "@"))
        except Exception:
            starter_ids = ["sword"]
        starters = starter_ids
        gold = 50

    # P28.1a — every hero starts with a Wayfarer's Ring for the waystones
    starters = list(starters) + ["teleport_ring"]

    # Build inventory from item ids
    inventory = []
    for item_id in starters:
        qty = 1
        if item_id == "potion":
            qty = 2
        elif item_id in ("arrow", "bolt", "stone"):
            qty = 20
        item = create_item(item_id, quantity=qty)
        if item:
            from items.inventory_ops import stack_add
            stack_add(inventory, item)      # merge duplicate stackables (P25.1)

    # HP from CON
    con = stats.get("constitution", 10)
    max_hp = 18 + 2 * max(0, (con - 10) // 2) + 5  # baseline 23-31

    player = Character(
        id="player",
        name=name,
        character_class=klass,
        race=race,
        level=1,
        strength=stats.get("strength", 10),
        dexterity=stats.get("dexterity", 10),
        constitution=con,
        intelligence=stats.get("intelligence", 10),
        wisdom=stats.get("wisdom", 10),
        charisma=stats.get("charisma", 10),
        hp=max_hp, max_hp=max_hp,
        position=(15, 5),
        inventory=inventory,
        gold=gold,
        symbol="@",
        description=f"A brave {race.value} {klass.value}",
        personality={"traits": ["brave", "curious"]},
        goals=["Explore the world", "Find adventure"],
    )
    player.metadata = {
        "xp": 0,
        "faction_rep": {
            "villagers": 0, "guards": 0, "merchants": 0,
            "brigands": -10, "monsters": -10, "temple": 0,
        },
        "bank": 0,
    }
    # Auto-equip starter gear (first weapon + first armor + first shield)
    try:
        from characters.equipment import equip
        for it in list(player.inventory):
            if it.is_equippable():
                equip(player, it)
                # Stop after first item per slot type
    except Exception:
        pass
    return player


def _resolve_npc_spawn(engine, npc) -> tuple:
    """Compute a sensible spawn position for an NPC based on home_location.

    Walks outward from the home's center to find a walkable tile not already
    occupied. Falls back to the NPC's hardcoded position if there's no home.
    """
    from world.world_map import TerrainType

    home_name = getattr(npc, "home_location", "")
    if not home_name:
        return npc.position

    loc = None
    for candidate in engine.world.locations:
        if candidate.name == home_name:
            loc = candidate
            break
    if loc is None:
        return npc.position

    cx, cy = loc.center()
    wmap = engine.world.map
    # Try expanding ring around the location's center
    occupied = set(wmap.characters.keys())
    blocked = (TerrainType.WATER, TerrainType.MOUNTAIN)
    for radius in range(0, 6):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, y = cx + dx, cy + dy
                if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                    continue
                if wmap.terrain[y][x] in blocked:
                    continue
                if (x, y) in occupied:
                    continue
                return (x, y)
    return (cx, cy)


def _resolve_player_spawn(engine) -> tuple:
    """Player starts at the edge of Oakvale Village (or fallback)."""
    from world.world_map import TerrainType
    wmap = engine.world.map
    oakvale = next((l for l in engine.world.locations
                    if l.name == "Oakvale Village"), None)
    if oakvale is None:
        return (15, 5)
    cx, cy = oakvale.center()
    # Step a few tiles north to "arrive at the outskirts"
    occupied = set(wmap.characters.keys())
    for offset in range(2, 8):
        candidate_y = cy - offset
        for dx in (0, 1, -1, 2, -2):
            x, y = cx + dx, candidate_y
            if not (0 <= x < wmap.width and 0 <= y < wmap.height):
                continue
            if wmap.terrain[y][x] in (TerrainType.WATER, TerrainType.MOUNTAIN,
                                      TerrainType.BUILDING):
                continue
            if (x, y) in occupied:
                continue
            return (x, y)
    return (cx, cy)


def initialize_demo_world(engine, player_spec=None,
                          world_kind="default") -> None:
    """Populate `engine` with world terrain, NPCs, player, and starter
    quests. `world_kind="castle"` plants the Bloodstone realm (P18.5)."""
    castle = (world_kind == "castle")
    oakvale = (world_kind == "oakvale")
    # World generation
    if oakvale:
        from world.town_region import build_oakvale_region
        engine._oakvale_region = build_oakvale_region(engine.world)
    elif castle:
        from world.castle_region import build_castle_region
        build_castle_region(engine.world)
    else:
        try:
            from world.world_generator import WorldGenerator
            mode = "realistic" if world_kind == "realistic" else "classic"
            WorldGenerator(engine.world, mode=mode).generate()
        except Exception as e:
            logger.warning(f"Procedural worldgen failed ({e}); using legacy.")
            engine.world.create_simple_world()

    # EVERY new game begins at MORNING, not midnight — you wake in a sunlit
    # town, seeing the world (and its terrain detail), not a black screen with
    # a tiny torch-pool in a sea of unexplored fog (George 2026-07-15: "the
    # tiles are still mainly black"). Night falls later, once you've explored
    # and the widened torch-pool (ui/lighting.py) keeps it playable. A loaded
    # save restores its own clock; this only sets the fresh-start time.
    try:
        engine.world.time = 8 * 60              # 08:00
    except Exception:
        pass

    # Revival shrine + back-references
    try:
        engine.world.add_revival_shrine(2, 12, radius=2)
    except Exception:
        pass
    engine.world.npc_manager = engine.npc_manager
    engine.world.memory_manager = engine.memory_manager
    # P36.3 a realistic world carries a deep-history chronicle → the Y-journal
    try:
        saga = getattr(engine.world, "history_chronicle", None)
        if saga and getattr(engine, "chronicle", None) is not None:
            engine.chronicle.seed_pregame(saga)
    except Exception:
        pass

    # NPCs — placed at their home_location (auto-adjusts to world size).
    # OAKVALE T6: the large-town region gets its own role-based population
    # (keepers/townsfolk/street folk) instead of the classic preset cast whose
    # home locations don't exist in the region.
    if oakvale:
        from world.town.population import populate_town
        try:
            n = populate_town(engine, "Oakvale", seed=7)
            logger.info(f"Oakvale populated with {n} townsfolk.")
        except Exception as e:
            logger.warning(f"Oakvale population failed: {e}")
    else:
        npcs = engine.npc_manager.create_simple_npcs()
        for npc in npcs:
            npc.inventory = [upgrade_item_string(it) for it in npc.inventory]
            npc.position = _resolve_npc_spawn(engine, npc)
            engine.world.map.place_character(npc, *npc.position)

    # Player — at the castle gate (P18.5) or near Oakvale's center
    engine.player = create_default_player(spec=player_spec)
    spawn = None
    if oakvale:
        from world.town_region import oakvale_spawn
        spawn = oakvale_spawn(engine.world)
    elif castle:
        from world.castle_region import gate_approach
        spawn = gate_approach(engine.world)
    engine.player.position = spawn or _resolve_player_spawn(engine)
    engine.world.map.place_character(engine.player, *engine.player.position)

    # P31.1/P31.1b — post guards at the walled town's gates AND corner towers
    if not castle:
        try:
            from world.fortify import post_guards, post_towers
            oak = next((l for l in engine.world.locations
                        if l.name == "Oakvale Village"), None)
            if oak is None:                # OAKVALE T5b region: the town marker
                oak = next((l for l in engine.world.locations
                            if l.get_property("town")), None)
            gates = (oak.get_property("gates") if oak else None) or []
            post_guards(engine, [tuple(g) for g in gates])
            towers = (oak.get_property("towers") if oak else None) or []
            post_towers(engine, [tuple(c) for c in towers])
        except Exception as e:
            logger.debug(f"gate/tower guards: {e}")

    engine.memory_manager.add_event(
        "You stand before the gates of Bloodstone Castle." if castle
        else "You arrive at the outskirts of Oakvale Village.")

    # Offer every authored quest (locked ones hide behind their prereqs)
    if engine.quest_manager:
        from quests.quest_templates import all_quest_ids
        for qid in all_quest_ids():
            engine.quest_manager.offer_quest(qid)

    # Build interiors for every building
    try:
        from world.interiors import build_interiors_for_world
        engine.interiors = build_interiors_for_world(engine.world)
    except Exception as e:
        logger.warning(f"Interior build failed: {e}")

    # Simulate pre-game history (lore + ruined keep + faction shifts)
    try:
        from world.history_sim import simulate, apply_history
        events = simulate(years=5)
        apply_history(engine, events)
    except Exception as e:
        logger.warning(f"History sim failed: {e}")
