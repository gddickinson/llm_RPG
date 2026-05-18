"""Mixin holding the user-facing API methods added in Bundle A.

Keeps `engine/game_engine.py` under 500 LOC by housing the spell /
equipment / banking / crafting / party / interior wrappers separately.
"""

from typing import Any, Dict


class GameAPIMixin:
    """Mixin: thin wrappers that delegate to subsystems."""

    # ---- party ------------------------------------------------------

    def recruit(self, npc_id: str) -> str:
        return self.companion_manager.recruit(npc_id)

    def dismiss_companion(self, npc_id: str) -> str:
        return self.companion_manager.dismiss(npc_id)

    def party_members(self):
        return self.companion_manager.members()

    # ---- interiors --------------------------------------------------

    def enter_building(self) -> str:
        if self.current_interior:
            return "You are already inside."
        loc = self.world.get_location_at(*self.player.position)
        if not loc:
            return "There's no building here."
        inter = self.interiors.get(loc.name)
        if not inter:
            return f"You can't enter the {loc.name}."
        self.exterior_return_pos = self.player.position
        self.current_interior = inter
        self.player.position = inter.door
        msg = f"You enter the {loc.name}. {inter.description}"
        self.memory_manager.add_event(msg)
        return msg

    def exit_building(self) -> str:
        if not self.current_interior:
            return "You are already outside."
        name = self.current_interior.name
        self.current_interior = None
        if self.exterior_return_pos:
            self.player.position = self.exterior_return_pos
            self.world.map.place_character(self.player, *self.player.position)
            self.exterior_return_pos = None
        msg = f"You leave the {name}."
        self.memory_manager.add_event(msg)
        return msg

    # ---- quest board ------------------------------------------------

    def quest_board_at_player(self):
        return self.quest_board_manager.board_at_player()

    def accept_quest_from_board(self, quest_id: str) -> bool:
        ok = self.quest_board_manager.accept_from_board(quest_id)
        if ok:
            self.memory_manager.add_event(
                f"Accepted quest from board: {quest_id}")
        return ok

    # ---- spells -----------------------------------------------------

    def cast_spell(self, spell_id: str, target_name: str = None) -> str:
        if not hasattr(self, "spell_system"):
            from engine.spells import SpellSystem
            self.spell_system = SpellSystem(self)
        return self.spell_system.cast(self.player, spell_id, target_name)

    def get_player_mana(self):
        from engine.spells import get_mana
        return get_mana(self.player)

    def get_player_spells(self):
        from engine.spells import get_known_spells
        return get_known_spells(self.player)

    # ---- equipment --------------------------------------------------

    def equip_item(self, item_name: str) -> str:
        from characters.equipment import equip
        for it in self.player.inventory:
            name = it.name if hasattr(it, "name") else str(it)
            if item_name.lower() in name.lower():
                msg = equip(self.player, it)
                self.memory_manager.add_event(msg)
                return msg
        return f"You don't have {item_name}."

    def unequip_slot(self, slot_name: str) -> str:
        from characters.equipment import unequip, EquipSlot
        try:
            slot = EquipSlot(slot_name.lower())
        except ValueError:
            return f"Unknown slot: {slot_name}"
        msg = unequip(self.player, slot)
        self.memory_manager.add_event(msg)
        return msg

    def get_equipment(self) -> Dict[str, Any]:
        from characters.equipment import get_equipment
        return get_equipment(self.player)

    # ---- foraging / weather / dungeons -------------------------------

    def forage(self) -> str:
        return self.forage_manager.forage()

    def current_weather(self) -> str:
        return self.weather_system.state.current.value

    def enter_dungeon(self) -> str:
        from world.world_map import TerrainType
        from world.dungeon import generate_dungeon, populate_dungeon
        x, y = self.player.position
        terrain = self.world.map.get_terrain_at(x, y)
        if terrain != TerrainType.CAVE:
            return "There's no cave entrance here."
        loc = self.world.get_location_at(x, y)
        name = loc.name if loc else f"cave_{x}_{y}"
        if name not in self.dungeons:
            dungeon = generate_dungeon(name=f"{name} (Depths)",
                                       seed=hash(name) & 0xFFFFFFFF)
            populate_dungeon(dungeon, self)
            self.dungeons[name] = dungeon
        self.current_dungeon = self.dungeons[name]
        self.dungeon_return_pos = self.player.position
        self.player.position = self.current_dungeon.exit_pos
        msg = (f"You descend into {self.current_dungeon.name}. "
               f"{self.current_dungeon.description}")
        self.memory_manager.add_event(msg)
        return msg

    def exit_dungeon(self) -> str:
        if not self.current_dungeon:
            return "You aren't in a dungeon."
        name = self.current_dungeon.name
        self.current_dungeon = None
        if self.dungeon_return_pos:
            self.player.position = self.dungeon_return_pos
            self.world.map.place_character(self.player, *self.player.position)
            self.dungeon_return_pos = None
        msg = f"You emerge from {name} into daylight."
        self.memory_manager.add_event(msg)
        return msg

    # ---- banking + crafting -----------------------------------------

    def deposit_gold(self, amount: int) -> str:
        return self.bank.deposit(amount)

    def withdraw_gold(self, amount: int) -> str:
        return self.bank.withdraw(amount)

    def bank_balance(self) -> int:
        return self.bank.balance()

    def can_craft_at_player(self, output_id: str) -> str:
        from items.crafting import can_craft
        loc = self.world.get_location_at(*self.player.position)
        props = dict(loc.properties) if loc else {}
        return can_craft(self.player, output_id, props)

    def craft(self, output_id: str) -> str:
        from items.crafting import craft
        loc = self.world.get_location_at(*self.player.position)
        props = dict(loc.properties) if loc else {}
        msg = craft(self.player, output_id, props)
        self.memory_manager.add_event(msg)
        return msg
