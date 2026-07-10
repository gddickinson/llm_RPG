"""Player-driven actions: pickup/drop/use/attack.

Extracted from the legacy monolithic game_engine.py.
"""

import logging
from typing import Optional

logger = logging.getLogger("llm_rpg.player_actions")


class PlayerActions:
    """All actions the player can take, separated from engine internals."""

    def __init__(self, engine):
        self.engine = engine

    # ---- inventory ----------------------------------------------------

    def pickup(self, item_name: str = None) -> str:
        player = self.engine.player
        x, y = player.position
        ground = self.engine.world.get_items_at(x, y)
        if not ground:
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
        player.inventory.append(item)
        self.engine.world.remove_item_from_ground(item, x, y)
        msg = f"You pick up {item_name_str}."
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
        if not item_name:
            return "Specify which item to use."
        player = self.engine.player
        for it in player.inventory:
            it_name = it.name if hasattr(it, "name") else str(it)
            if item_name.lower() not in it_name.lower():
                continue

            # Scroll: cast embedded spell
            use_eff = getattr(it, "use_effect", None) or {}
            if "spell" in use_eff:
                spell_id = use_eff["spell"]
                try:
                    msg = self.engine.cast_spell(spell_id)
                except Exception:
                    msg = f"You read the {it_name}."
                self._remove_one(player, it)
                self.engine.memory_manager.add_event(
                    f"You read the {it_name}.")
                self.engine.advance_turn()
                return msg

            # Spell-teaching tome
            if "teach_spell" in use_eff:
                spell_id = use_eff["teach_spell"]
                from engine.spells import SPELL_REGISTRY, ensure_mana
                spell = SPELL_REGISTRY.get(spell_id)
                if spell is None:
                    return f"The {it_name} is gibberish."
                ensure_mana(player)
                known = player.metadata.setdefault("spells_known", [])
                if spell_id in known:
                    return f"You already know {spell.name}."
                known.append(spell_id)
                player.inventory.remove(it)
                msg = (f"You study the {it_name} and learn "
                       f"{spell.name}!")
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg

            # Permanent stat increase (training manual)
            if "permanent_stat" in use_eff:
                stat = use_eff["permanent_stat"]
                amount = int(use_eff.get("amount", 1))
                old = getattr(player, stat, 10)
                setattr(player, stat, old + amount)
                player.inventory.remove(it)
                msg = (f"You study the {it_name}. "
                       f"{stat.upper()[:3]} {old} -> {old + amount}.")
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg

            # Temporary buff (potion of might / speed)
            if "effect" in use_eff:
                try:
                    from characters.status_effects import apply_effect
                    apply_effect(player, use_eff["effect"],
                                 int(use_eff.get("duration", 5)))
                except Exception:
                    pass
                self._remove_one(player, it)
                msg = f"You drink the {it_name}."
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg

            if "cure" in use_eff:
                try:
                    from characters.status_effects import remove_effect
                    remove_effect(player, use_eff["cure"])
                except Exception:
                    pass
                self._remove_one(player, it)
                msg = f"You drink the {it_name}."
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg

            # The right remedy clears a disease (P8.2)
            try:
                from engine.disease import try_cure_with_item
                cured = try_cure_with_item(self.engine, player, it)
                if cured:
                    self._remove_one(player, it)
                    self.engine.advance_turn()
                    return cured
            except Exception:
                pass

            heal = getattr(it, "heal_amount", 0)
            if heal:
                from characters.needs import get_hunger, feed
                hungry = get_hunger(player) > 10
                if player.hp >= player.max_hp and not hungry:
                    return "You're already at full health."
                player.heal(heal)
                # Eating also satisfies hunger (bread -32, jerky -24, ...)
                feed(player, amount=heal * 8)
                self._remove_one(player, it)
                msg = f"You consume {it_name}" + (
                    f" and heal {heal} HP." if player.hp <= player.max_hp
                    else ".")
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg
            else:
                # Generic use — e.g. for quest items / keys
                msg = f"You use {it_name}."
                self.engine.memory_manager.add_event(msg)
                self.engine.advance_turn()
                return msg
        return f"You don't have {item_name}."

    def _remove_one(self, char, item) -> None:
        """Decrement stack by 1, removing if depleted."""
        if getattr(item, "stackable", False) and item.quantity > 1:
            item.quantity -= 1
        else:
            try:
                char.inventory.remove(item)
            except ValueError:
                pass

    # ---- combat -------------------------------------------------------

    def attack(self, target_name: str) -> str:
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

        loc = self.engine.world.get_location_at(nx, ny)
        loc_name = loc.name if loc else "wilderness"
        self.engine.memory_manager.add_event(
            f"You move to {loc_name} ({nx}, {ny}).")

        # Quest hooks
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager and loc:
            self.engine.quest_manager.on_location_entered(loc.name)

        self._weather_travel_penalty(nx, ny)
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
            return self._take_stairs(zone.level_above, up=True)
        if getattr(zone, "stairs_down", None) == (nx, ny) and \
                getattr(zone, "level_below", None) is not None:
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
            landing = level.door
        engine.current_interior = level
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

    def _weather_travel_penalty(self, x: int, y: int) -> None:
        """Storms/snow — and swamp muck — slow travel: +1 min per step."""
        try:
            from world.weather import Weather
            from world.world_map import TerrainType
            terrain = self.engine.world.map.get_terrain_at(x, y)
            if terrain == TerrainType.SWAMP:
                self.engine.world.advance_time(1)
                return
            current = self.engine.weather_system.state.current
            if current not in (Weather.STORM, Weather.SNOW):
                return
            if terrain == TerrainType.ROAD:
                return
            self.engine.world.advance_time(1)
            self._slow_steps = getattr(self, "_slow_steps", 0) + 1
            if self._slow_steps % 10 == 1:
                self.engine.memory_manager.add_event(
                    f"The {current.value} slows your travel.")
        except Exception:
            pass
