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

    def move(self, dx: int, dy: int) -> bool:
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

        old_pos = player.position
        if not wmap.move_character(player, nx, ny):
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
        # Blocked by an active character standing there
        for npc in self.engine.npc_manager.npcs.values():
            if npc.is_active() and npc.position == (nx, ny):
                return False

        old_pos = player.position
        player.position = (nx, ny)
        try:
            self.engine.pet_system.on_player_moved(old_pos)
        except Exception:
            pass
        self.engine.advance_turn()
        return True

    def _weather_travel_penalty(self, x: int, y: int) -> None:
        """Storms and snow slow off-road travel: one extra minute per step."""
        try:
            from world.weather import Weather
            from world.world_map import TerrainType
            current = self.engine.weather_system.state.current
            if current not in (Weather.STORM, Weather.SNOW):
                return
            terrain = self.engine.world.map.get_terrain_at(x, y)
            if terrain == TerrainType.ROAD:
                return
            self.engine.world.advance_time(1)
            self._slow_steps = getattr(self, "_slow_steps", 0) + 1
            if self._slow_steps % 10 == 1:
                self.engine.memory_manager.add_event(
                    f"The {current.value} slows your travel.")
        except Exception:
            pass
