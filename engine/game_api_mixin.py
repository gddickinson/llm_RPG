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

    # ---- ranged combat -----------------------------------------------

    def shoot_ranged(self, target_name: str = None) -> str:
        """Fire a ranged attack at the named target (or nearest enemy).

        Requires an equipped ranged weapon. Consumes ammo of the matching
        ammo_type. Thrown weapons fire without ammo.
        """
        from items.item import Item

        try:
            from characters.equipment import equipped_weapon
            weapon = equipped_weapon(self.player)
        except Exception:
            weapon = None
        if weapon is None or not weapon.is_ranged_weapon():
            msg = "You have no ranged weapon equipped."
            self.memory_manager.add_event(msg)
            return msg

        weapon_type = self._weapon_type_str(weapon)

        # Ammo check (thrown weapons skip)
        ammo_item = None
        if weapon.weapon_kind == "ranged" and weapon.ammo_type:
            ammo_item = self._find_ammo(weapon.ammo_type)
            if ammo_item is None:
                msg = f"You're out of {weapon.ammo_type}s!"
                self.memory_manager.add_event(msg)
                return msg

        # Resolve target
        target = None
        if target_name:
            target = self.find_character(target_name)
        if target is None:
            target = self._nearest_hostile()
        if target is None:
            return "No target in sight."

        from engine.effects import effective_weapon_damage_bonus
        dex_bonus = max(0, (self.player.dexterity - 10) // 2)
        damage = max(1, int(weapon.damage) + dex_bonus
                     + effective_weapon_damage_bonus(self.player))

        if ammo_item is not None:
            self._consume_one_ammo(ammo_item)

        proj = self.projectile_manager.spawn(
            self.player, target, damage, weapon_type=weapon_type)
        ammo_label = f" ({weapon.ammo_type} -1)" if ammo_item is not None else ""
        msg = f"You loose a {proj.weapon_type} at {target.name}{ammo_label}."
        self.memory_manager.add_event(msg)
        self.advance_turn()
        return msg

    def _weapon_type_str(self, weapon) -> str:
        name = (weapon.name or "").lower()
        for key in ("longbow", "crossbow", "thrown knife", "javelin",
                    "sling", "bow"):
            if key in name or key.replace(" ", "_") in (weapon.id or ""):
                return key.replace(" ", "_")
        return "bow"

    def _find_ammo(self, ammo_type: str):
        from items.item import Item
        for it in self.player.inventory:
            if isinstance(it, Item) and it.is_ammo() and \
                    it.ammo_type == ammo_type and it.quantity > 0:
                return it
        return None

    def _consume_one_ammo(self, ammo_item) -> None:
        ammo_item.quantity -= 1
        if ammo_item.quantity <= 0:
            try:
                self.player.inventory.remove(ammo_item)
            except ValueError:
                pass

    def _nearest_hostile(self):
        px, py = self.player.position
        best = None
        best_d = 999
        for npc in self.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            if klass not in ("brigand", "troll", "monster"):
                continue
            d = ((npc.position[0] - px) ** 2 +
                 (npc.position[1] - py) ** 2) ** 0.5
            if d < best_d:
                best_d, best = d, npc
        return best

    # ---- spell visual effects (used by spell system + UI) ------------

    def trigger_spell_visual(self, spell_id: str, x: float, y: float) -> None:
        if self.combat_effects is None:
            return
        try:
            self.combat_effects.spawn_spell_burst(spell_id, x, y)
        except Exception:
            pass

    # ---- foraging / weather / dungeons -------------------------------

    def forage(self) -> str:
        """Z key: gather (mine/chop/fish) when tooled-up; herbs otherwise.

        Priority: node + tool -> gather; foragable terrain -> herbs;
        node without tool -> teach the tool requirement."""
        gm = self.gathering_manager
        node = gm.node_at(*self.player.position)
        if node is not None and gm.has_tool_for(node):
            return gm.gather()
        x, y = self.player.position
        from world.foraging import TERRAIN_FORAGE_TABLE
        terrain = self.world.map.get_terrain_at(x, y)
        if terrain in TERRAIN_FORAGE_TABLE:
            return self.forage_manager.forage()
        if node is not None:
            return gm.tool_message(node)
        return self.forage_manager.forage()

    def current_weather(self) -> str:
        return self.weather_system.state.current.value

    def active_zone(self):
        """The alternate grid the player is inside (dungeon/interior)."""
        return getattr(self, "current_dungeon", None) or \
            getattr(self, "current_interior", None)

    def effective_visibility(self) -> int:
        """Visibility range in tiles, shrunk by fog / rain / snow / storm."""
        import config
        base = config.DEFAULT_VISIBILITY_RANGE
        try:
            mod = self.weather_system.visibility_modifier()
        except Exception:
            mod = 1.0
        return max(2, round(base * mod))

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
        from items.crafting import craft, find_recipe
        loc = self.world.get_location_at(*self.player.position)
        props = dict(loc.properties) if loc else {}
        msg = craft(self.player, output_id, props)
        self.memory_manager.add_event(msg)
        if msg.startswith("You craft"):
            self._award_craft_xp(find_recipe(output_id))
            try:
                self.collection_log.record_craft(output_id)
            except Exception:
                pass
            # Crafted output counts for FETCH objectives too
            if self.quest_manager:
                recipe = find_recipe(output_id)
                if recipe:
                    self.quest_manager.on_item_acquired(recipe.output_id)
        return msg

    def _award_craft_xp(self, recipe) -> None:
        """Each recipe trains the skill declared in its data entry."""
        from engine.skill_progression import add_skill_xp
        if recipe is None:
            return
        xp = 20 + recipe.gold_cost // 2
        for note in add_skill_xp(self.player, recipe.skill, xp):
            self.memory_manager.add_event(note)
        try:
            self.pet_system.maybe_award(recipe.skill)
        except Exception:
            pass
