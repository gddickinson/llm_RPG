"""Player-driven actions: pickup/drop/use/attack.

Extracted from the legacy monolithic game_engine.py.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.player_actions")


def _is_private_interior(engine) -> bool:
    """Inside somebody's locked home (not derelict, not yours)."""
    inter = getattr(engine, "current_interior", None)
    if inter is None:
        return False
    try:
        # interiors are keyed by the exterior location name;
        # inter.name carries a suffix — resolve by identity
        name = next((k for k, v in engine.interiors.items()
                     if v is inter), None)
        if name is None:
            return False
        door = engine.door_manager.door(name)
        return (door.get("policy") == "locked"
                and engine.homes.owner_of(name) is not None
                and not engine.homes.is_derelict(name))
    except Exception:
        return False


class PlayerActions:
    """All actions the player can take, separated from engine internals."""

    def __init__(self, engine):
        self.engine = engine

    # ---- inventory ----------------------------------------------------

    def pickup(self, item_name: str = None) -> str:
        player = self.engine.player
        from engine import anim
        anim.emote(player, "stoop")          # bend down to take it (P33.6c)
        x, y = player.position
        ground = self.engine.world.get_items_at(x, y)
        if not ground:
            try:   # E clears rubble or digs at rock (P10.4/P10.6)
                from engine.earthworks import e_fallback
                msg = e_fallback(self.engine, x, y)
                if msg:
                    self.engine.advance_turn()
                    return msg
            except Exception:
                pass
            return "There's nothing here to pick up."

        candidates = []
        if item_name:
            for it in ground:
                it_name = it.name if hasattr(it, "name") else str(it)
                if item_name.lower() in it_name.lower():
                    candidates.append(it)
        else:
            candidates = list(ground)

        if not candidates:
            return f"You can't find {item_name} here."

        item = candidates[0]
        item_name_str = item.name if hasattr(item, "name") else str(item)
        # Plain-string ground entries are body markers — they belong
        # on the ground (shrines revive from there), and they crashed
        # the inventory panel when carried (George)
        if not hasattr(item, "id"):
            try:   # a KO'd person's body can be robbed (P12.4)
                from engine.dying import rob_body
                robbed = rob_body(self.engine, item_name_str, x, y)
                if robbed:
                    self.engine.advance_turn()
                    return robbed
            except Exception:
                pass
            return (f"You leave {item_name_str} in peace. A shrine "
                    f"may yet restore them.")
        from engine.carry import can_carry, full_message
        if not can_carry(player):
            msg = full_message(player)
            self.engine.memory_manager.add_event(msg)
            return msg
        player.inventory.append(item)
        self.engine.world.remove_item_from_ground(item, x, y)
        msg = f"You pick up {item_name_str}."
        try:   # lifting from a private home is THEFT (P12.9b)
            from engine.law import mark_stolen
            if _is_private_interior(self.engine):
                mark_stolen(item)
                msg += " (stolen)"
        except Exception:
            pass
        self.engine.memory_manager.add_event(msg)

        # Relics of history reveal their legends
        try:
            from engine.legends import on_item_picked_up
            on_item_picked_up(self.engine, item)
        except Exception:
            pass

        # Quest hook
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            item_id = getattr(item, "id", None) or item_name_str.lower().replace(" ", "_")
            self.engine.quest_manager.on_item_acquired(item_id)

        self.engine.advance_turn()
        return msg

    def drop(self, item_name: str) -> str:
        if not item_name:
            return "Specify which item to drop."
        player = self.engine.player
        if not player.inventory:
            return "You have nothing to drop."

        for it in player.inventory:
            it_name = it.name if hasattr(it, "name") else str(it)
            if item_name.lower() in it_name.lower():
                player.inventory.remove(it)
                self.engine.world.add_item_to_ground(it, *player.position)
                msg = f"You drop {it_name}."
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg
        return f"You don't have {item_name}."

    def use(self, item_name: str) -> str:
        from engine.item_use import use_item
        return use_item(self.engine, item_name)

    def attack(self, target_name: str) -> str:
        try:   # the chew delay costs tempo (P12.5)
            from engine.food import attack_gate
            gate = attack_gate(self.engine)
            if gate:
                return gate
        except Exception:
            pass
        result = self.engine.combat_system.player_attack(target_name)
        self.engine.memory_manager.add_event(result)
        self.engine.advance_turn()
        return result

    # ---- movement -----------------------------------------------------

    def _building_wall_check(self, nx: int, ny: int):
        """Enterable buildings are SOLID except their door tile.
        Returns None (not a building tile — proceed), False (wall),
        or True (entered through the door — turn consumed)."""
        engine = self.engine
        loc = engine.world.get_location_at(nx, ny)
        if loc is None or loc.name not in engine.interiors:
            return None
        door_tile = (loc.x + loc.width // 2, loc.y + loc.height - 1)
        # A breached wall is a second door (P10.2): clamber through
        # (only if the rubble is low enough — P10.4)
        from world.world_map import TerrainType as _TT
        if engine.world.map.terrain[ny][nx] == _TT.RUBBLE and \
                engine.tile_damage.depth_at(nx, ny) < 2:
            msg = engine.enter_building(loc, via_breach=True)
            if engine.current_interior is not None:
                engine.advance_turn()
                return True
            return False
        day = engine.world.time // (24 * 60)
        marks = engine.player.metadata.setdefault("door_hints", {})
        if (nx, ny) != door_tile:
            if marks.get(f"wall:{loc.name}") != day:
                marks[f"wall:{loc.name}"] = day
                engine.memory_manager.add_event(
                    f"The walls of the {loc.name}. Its door faces "
                    f"south.")
            return False
        # The door: bump to enter (locks willing)
        msg = engine.enter_building(loc)
        if engine.current_interior is not None:
            engine.advance_turn()
            return True
        if marks.get(f"locked:{loc.name}") != day:
            marks[f"locked:{loc.name}"] = day
        return False

    def move(self, dx: int, dy: int, careful: bool = False) -> bool:
        player = self.engine.player
        if not self.engine.running:
            return False
        try:   # down at 0 HP, you crawl nowhere (P12.4)
            from engine.dying import action_gate
            gate = action_gate(self.engine)
            if gate:
                self.engine.memory_manager.add_event(gate)
                self.engine.advance_turn()
                return False
        except Exception:
            pass
        nx, ny = player.position[0] + dx, player.position[1] + dy

        # Inside a dungeon/interior, the ZONE grid governs movement —
        # its walls block, and the overworld terrain is irrelevant
        zone = None
        try:
            zone = self.engine.active_zone()
        except Exception:
            pass
        if zone is not None:
            return self._move_in_zone(zone, nx, ny)

        # Region transition if walking off the world edge
        wmap = self.engine.world.map
        if (nx < 0 or ny < 0 or nx >= wmap.width or ny >= wmap.height):
            streamer = getattr(self.engine, "world_streamer", None)
            if streamer is not None:
                direction = ("west" if nx < 0 else
                             "east" if nx >= wmap.width else
                             "north" if ny < 0 else "south")
                if streamer.transit(direction):
                    self.engine.advance_turn()
                    return True
            return False

        # Deep rubble blocks until cleared (P10.4) — unless you fly
        try:
            from characters.status_effects import has_effect
            from engine.tile_damage import RUBBLE_BLOCK_DEPTH
            if self.engine.tile_damage.depth_at(nx, ny) >= \
                    RUBBLE_BLOCK_DEPTH and \
                    not has_effect(player, "flying"):
                self.engine.memory_manager.add_event(
                    "The rubble is piled too high — clear it first "
                    "([E] on it).")
                return False
        except Exception:
            pass

        # A shut town gate opens for you (P31.1d/P37): walk into it and — unless
        # a raider ALARM has barred it — it swings open, so you are never sealed
        # inside your own walled town at night. George: "no way through the four
        # main walls." Runs BEFORE the wall guard, which would else stop the
        # BUILDING tile a closed gate reverts to.
        try:
            tg = getattr(self.engine, "town_gates", None)
            if tg is not None:
                opened = tg.player_step_open((nx, ny))
                if opened:
                    self.engine.memory_manager.add_event(opened)
        except Exception:
            pass

        # Solid buildings (P9A.3b): walls block, the door tile admits.
        # George: "I can just walk onto the building tile — shouldn't
        # there be doors and walls?"
        wall = self._building_wall_check(nx, ny)
        if wall is not None:
            return wall

        pre_move = player.position
        old_pos = player.position
        if not wmap.move_character(player, nx, ny):
            # Bumping a friendly NPC swaps places — nobody can box
            # you into a dead end (George's trap report)
            occupant = wmap.get_character_at(nx, ny)
            if occupant is not None and self._can_swap(occupant):
                wmap.remove_character(occupant)
                if wmap.move_character(player, nx, ny):
                    occupant.position = old_pos
                    wmap.place_character(occupant, *old_pos)
                    self.engine.memory_manager.add_event(
                        f"You squeeze past {occupant.name}.")
                    self.engine.advance_turn()
                    return True
                wmap.place_character(occupant, nx, ny)
            # Blocked — maybe Agility can turn this into a shortcut
            try:
                msg = self.engine.travel_system.try_shortcut(nx, ny)
                if msg is not None and player.position == (nx, ny):
                    self.engine.advance_turn()
                    return True
            except Exception:
                pass
            return False
        try:
            self.engine.pet_system.on_player_moved(old_pos)
        except Exception:
            pass
        try:   # the mount trails a step behind (P15.8b mule / P28.2a roster)
            from engine.mounts import mount_follow
            mount_follow(self.engine, old_pos)
        except Exception:
            pass

        loc = self.engine.world.get_location_at(nx, ny)
        loc_name = loc.name if loc else "wilderness"
        self.engine.memory_manager.add_event(
            f"You move to {loc_name} ({nx}, {ny}).")

        # Quest hooks
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager and loc:
            self.engine.quest_manager.on_location_entered(loc.name)

        try:   # slow ground + weather tax the step (P11.1)
            self.engine.traversal.on_step(nx, ny)
        except Exception:
            pass
        # Retreating from melee: careful disengage or eat a free strike
        try:
            from engine.tactics import (opportunity_attack,
                                        disengage_cost)
            if careful:
                disengage_cost(self.engine)
            else:
                opportunity_attack(self.engine, pre_move)
        except Exception:
            pass
        try:   # haste/slow turn economics (P11.4)
            self.engine.traversal.advance_after_move()
        except Exception:
            self.engine.advance_turn()
        return True

    def _move_in_zone(self, zone, nx: int, ny: int) -> bool:
        """Movement inside a dungeon/interior grid."""
        from world.world_map import TerrainType
        player = self.engine.player
        if not (0 <= nx < zone.width and 0 <= ny < zone.height):
            return False
        terrain = zone.terrain[ny][nx]
        if terrain in (TerrainType.MOUNTAIN, TerrainType.WATER,
                       TerrainType.BUILDING):
            return False
        # Stairs between building levels (P9A.5): step on, arrive at
        # the twin stair of the linked level
        if getattr(zone, "stairs_up", None) == (nx, ny) and \
                getattr(zone, "level_above", None) is not None:
            if self._warded(zone, up=True):
                return False
            return self._take_stairs(zone.level_above, up=True)
        if getattr(zone, "stairs_down", None) == (nx, ny) and \
                getattr(zone, "level_below", None) is not None:
            if self._warded(zone, up=False):
                return False
            return self._take_stairs(zone.level_below, up=False)
        # Interior visitors block (and swap) at their DISPLAYED
        # positions — never at overworld coordinates (George: walking
        # over indoor NPCs)
        for vid, spot in getattr(zone, "visitors", {}).items():
            if tuple(spot) != (nx, ny):
                continue
            npc = self.engine.npc_manager.npcs.get(vid)
            if npc is None or not npc.is_active():
                continue
            if self._can_swap(npc):
                zone.visitors[vid] = tuple(player.position)
                player.position = (nx, ny)
                self.engine.memory_manager.add_event(
                    f"You squeeze past {npc.name}.")
                self.engine.advance_turn()
                return True
            return False
        # Zone-native characters (dungeon monsters, tutorial cast)
        # block at their real positions
        for npc in self.engine.npc_manager.npcs.values():
            if npc.is_active() and npc.position == (nx, ny) and \
                    npc.id.startswith(("enc_", "tut_")):
                return False

        old_pos = player.position
        player.position = (nx, ny)
        try:
            self.engine.pet_system.on_player_moved(old_pos)
        except Exception:
            pass
        self.engine.advance_turn()
        return True

    def _warded(self, zone, up: bool) -> bool:
        """Sigil puzzles seal stairs until solved (P9.4)."""
        try:
            if self.engine.structures.stairs_warded(zone, up):
                self.engine.memory_manager.add_event(
                    "A shimmering ward seals the stairs. "
                    "(The sigils hold the key.)")
                return True
        except Exception:
            pass
        return False

    def _can_swap(self, npc) -> bool:
        """Friendlies let you squeeze past; hostiles hold the line."""
        if not npc.is_active():
            return False
        klass = getattr(npc.character_class, "value", "")
        if klass in ("brigand", "monster", "troll"):
            return False
        return not npc.metadata.get("provoked")

    def _take_stairs(self, level, up: bool) -> bool:
        """Clean level transition: land on the linked level's twin
        stair (the AW stair code was their buggy corner — rewritten)."""
        engine = self.engine
        landing = level.stairs_down if up else level.stairs_up
        if landing is None:
            landing = getattr(level, "door", None) or \
                getattr(level, "exit_pos", (1, 1))
        if hasattr(level, "rooms"):
            engine.current_dungeon = level      # dungeon floor (P9.5)
            engine._sync_ground_items()          # items stay on their floor
            if not up:
                depth = getattr(level, "depth", 1)
                best = engine.player.metadata.get(
                    "max_dungeon_depth", 1)
                if depth > best:
                    engine.player.metadata["max_dungeon_depth"] = depth
                    engine.memory_manager.add_event(
                        f"[Collection] You have delved to depth "
                        f"{depth}.")
        else:
            engine.current_interior = level
        engine._sync_ground_items()              # items stay on their floor
        engine.player.position = landing
        verb = "climb" if up else "descend"
        engine.memory_manager.add_event(
            f"You {verb} the stairs. {level.description}")
        try:
            engine.structures.on_enter_level(level)   # P9.1
        except Exception:
            pass
        engine.advance_turn()
        return True

