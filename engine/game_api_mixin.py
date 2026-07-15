"""Mixin holding the user-facing API methods added in Bundle A.

Keeps `engine/game_engine.py` under 500 LOC by housing the spell /
equipment / banking / crafting / party / interior wrappers separately.
"""

from typing import Any, Dict, Optional


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

    def _sync_ground_items(self) -> None:
        """Point `world.ground_items` at the ACTIVE grid's own item store,
        so items dropped in a zone stay on THAT floor and don't bleed onto
        every level (bug-fix 2026-07-12). The overworld's items are parked
        on `world._overworld_ground_items` while you are inside. Idempotent
        — safe to call after any zone transition."""
        world = self.world
        zone = self.current_interior or self.current_dungeon
        if zone is None:
            parked = getattr(world, "_overworld_ground_items", None)
            if parked is not None:
                world.ground_items = parked
                world._overworld_ground_items = None
            return
        if getattr(world, "_overworld_ground_items", None) is None:
            world._overworld_ground_items = getattr(world, "ground_items", {}) or {}
        if getattr(zone, "ground_items", None) is None:
            zone.ground_items = {}
        world.ground_items = zone.ground_items

    def enter_building(self, loc=None, via_breach: bool = False) -> str:
        if self.current_interior:
            return "You are already inside."
        if loc is None:
            loc = self.world.get_location_at(*self.player.position)
        if not loc:
            return "There's no building here."
        inter = self.interiors.get(loc.name)
        if not inter:
            return f"You can't enter the {loc.name}."
        # The door has a say (P9A.1) — unless you made your own door
        if via_breach:
            allowed, note = True, "You clamber through the breach. "
        else:
            allowed, note = self.door_manager.try_enter(loc.name)
        if not allowed:
            self.memory_manager.add_event(note)
            return note
        self.exterior_return_pos = self.player.position
        self.current_interior = inter
        self._sync_ground_items()
        self.player.position = inter.door
        # Everyone inside appears inside (P9A.7)
        try:
            from engine.presence import assign_visitors
            assign_visitors(self, inter, loc.name)
        except Exception:
            pass
        # Exterior breaches show inside too (P10.4)
        try:
            self._sync_breaches(loc, inter)
        except Exception:
            pass
        try:
            self.structures.on_enter_level(inter)   # P9.1
        except Exception:
            pass
        # Whose place is this? (P9A.3b nameplate)
        plate = ""
        try:
            if self.homes.is_derelict(loc.name):
                plate = " Long abandoned."
            else:
                owner = self.homes.owner_of(loc.name)
                if owner is not None:
                    plate = f" This is {owner.name}'s place."
        except Exception:
            pass
        msg = f"{note}You enter the {loc.name}.{plate} " \
              f"{inter.description}"
        self.memory_manager.add_event(msg)
        # Entering counts as visiting (VISIT quest objectives)
        try:
            if self.quest_manager:
                self.quest_manager.on_location_entered(loc.name)
        except Exception:
            pass
        # Uninvited? Witnessed? (P9A.4)
        try:
            self.trespass.on_enter(loc)
        except Exception:
            pass
        return msg

    def _sync_breaches(self, loc, inter) -> None:
        from engine.earthworks import sync_breaches
        sync_breaches(self, loc, inter)

    def force_door(self) -> str:
        """SHIFT+TAB: force the door of the building underfoot."""
        loc = self.world.get_location_at(*self.player.position)
        if not loc or loc.name not in self.interiors:
            return "There's no door here to force."
        broke, msg = self.door_manager.force(loc.name)
        if broke and "gives way" in msg:
            return self.enter_building()
        return msg

    def exit_building(self) -> str:
        if not self.current_interior:
            return "You are already outside."
        # Not on the ground floor? Head back to it first (P9A.5)
        zone = self.current_interior
        if not getattr(zone, "ground", True):
            level = zone.level_below or zone.level_above
            if level is not None:
                landing = (zone.level_below and level.stairs_up) or \
                    (zone.level_above and level.stairs_down) or \
                    level.door
                self.current_interior = level
                self._sync_ground_items()
                self.player.position = landing
                msg = "You make your way back to the ground floor."
                self.memory_manager.add_event(msg)
                return msg
        name = self.current_interior.name
        self.current_interior = None
        self._sync_ground_items()
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

    def board_overlay_lines(self) -> list:
        """A-board: the numbered notice list for the E-key board overlay."""
        return self.quest_board_manager.overlay_lines()

    def board_accept_index(self, index: int) -> str:
        """A-board: accept the i-th notice the board overlay listed."""
        msg = self.quest_board_manager.accept_index(index)
        self.memory_manager.add_event(msg)
        return msg

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

    def shoot_ranged(self, target_name: str = None,
                     aimed: bool = False) -> str:
        from engine.ranged import shoot_ranged
        return shoot_ranged(self, target_name, aimed)

    def _nearest_hostile(self):
        from engine.ranged import _nearest_hostile
        return _nearest_hostile(self)

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
        node without tool -> teach the tool requirement. A gather node
        on cooldown falls through to herb foraging where the terrain
        allows (playtest finding: an axe must not lock you out of the
        forest's herbs)."""
        gm = self.gathering_manager
        node = gm.node_at(*self.player.position)
        x, y = self.player.position
        # A ripe field beats everything (P8.3)
        crop = self.farm_manager.harvest(x, y)
        if crop:
            return crop
        from world.foraging import TERRAIN_FORAGE_TABLE
        terrain = self.world.map.get_terrain_at(x, y)
        foragable = terrain in TERRAIN_FORAGE_TABLE

        if node is not None and gm.has_tool_for(node):
            skill_id, spec, pos = node
            if gm._cooldown_ok(skill_id, spec, pos):
                return gm.gather()
            if foragable:
                return self.forage_manager.forage()
            return "This spot is picked clean. Come back later."
        if foragable:
            return self.forage_manager.forage()
        if node is not None:
            return gm.tool_message(node)
        return self.forage_manager.forage()

    def pray(self) -> str:
        """SHIFT+P at a shrine/temple: prayer and (maybe) a miracle."""
        return self.pantheon.pray()

    def melee_or_shoot(self) -> str:
        """Smart F (P8.7 UX): adjacent enemy -> melee; otherwise a
        ranged weapon fires at the lock."""
        from engine.presence import npc_adjacent_to_player
        for npc in self.npc_manager.npcs.values():
            if not npc.is_active():
                continue
            klass = getattr(npc.character_class, "value", "")
            hostile = klass in ("brigand", "monster", "troll") or \
                npc.metadata.get("provoked")
            if hostile and npc_adjacent_to_player(self, npc):
                return self.attack_character(npc.name)
        try:
            from characters.equipment import equipped_weapon
            weapon = equipped_weapon(self.player)
            if weapon is not None and weapon.is_ranged_weapon() and \
                    self.targeting.current() is not None:
                return self.shoot_ranged()
        except Exception:
            pass
        msg = "No enemy adjacent."
        self.memory_manager.add_event(msg)
        return msg

    def player_location(self):
        """The Location the player occupies — interior-aware (P9A.6):
        inside a building (any level), that building's location."""
        if self.current_interior is not None:
            zone = self.current_interior
            for key, inter in self.interiors.items():
                if inter is zone or inter.level_above is zone or \
                        inter.level_below is zone:
                    for loc in self.world.locations:
                        if loc.name == key:
                            return loc
            return None
        return self.world.get_location_at(*self.player.position)

    def use_furniture(self) -> Optional[str]:
        """E beside interior furniture (P9A.2). None = nothing here."""
        from engine.furniture import interact
        return interact(self)

    # ---- Stable / mounts (P28.2d) -------------------------------------

    def at_stable(self) -> bool:
        from engine import mounts
        return mounts.stable_here(self)

    def mount_stable_lines(self) -> list:
        from engine import mounts
        return mounts.stable_overlay_lines(self)

    def mount_stable_buy(self, index: int) -> str:
        from engine import mounts
        msg = mounts.buy_index(self, index)
        self.memory_manager.add_event(msg)
        return msg

    # ---- Claim a home (P15.7) -----------------------------------------

    def home_action(self) -> Optional[str]:
        """E inside a ruin/home: buy the derelict, or repair your own."""
        from engine.homestead import home_action
        return home_action(self)

    def home_deposit(self, item_name: str) -> str:
        """Store a carried item in your home chest (from the I-panel)."""
        from engine.homestead import deposit
        return deposit(self, item_name)

    def home_withdraw(self, item_name: str) -> str:
        from engine.homestead import withdraw
        return withdraw(self, item_name)

    def current_weather(self) -> str:
        return self.weather_system.state.current.value

    def active_zone(self):
        """The alternate grid the player is inside (dungeon/interior)."""
        return getattr(self, "current_dungeon", None) or \
            getattr(self, "current_interior", None)

    def effective_visibility(self) -> int:
        """Visibility range in tiles, shrunk by fog / rain / snow /
        storm — and collapsed to 1 while blinded (P12.2)."""
        import config
        try:
            from characters.status_effects import has_effect
            if has_effect(self.player, "blinded"):
                return 1
        except Exception:
            pass
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
            from world.dungeon import generate_multilevel
            dungeon = generate_multilevel(
                name=f"{name} (Depths)",
                seed=hash(name) & 0xFFFFFFFF, engine=self)
            self.dungeons[name] = dungeon
        self.current_dungeon = self.dungeons[name]
        self._sync_ground_items()
        self.dungeon_return_pos = self.player.position
        self.player.position = self.current_dungeon.exit_pos
        msg = (f"You descend into {self.current_dungeon.name}. "
               f"{self.current_dungeon.description}")
        self.memory_manager.add_event(msg)
        return msg

    def exit_dungeon(self) -> str:
        if not self.current_dungeon:
            return "You aren't in a dungeon."
        # Deeper floors climb back up first (P9.5)
        above = getattr(self.current_dungeon, "level_above", None)
        if above is not None:
            landing = above.stairs_down or above.exit_pos
            self.current_dungeon = above
            self._sync_ground_items()
            self.player.position = landing
            msg = "You climb back toward the light."
            self.memory_manager.add_event(msg)
            return msg
        name = self.current_dungeon.name
        self.current_dungeon = None
        self._sync_ground_items()
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
        loc = self.player_location()
        props = dict(loc.properties) if loc else {}
        return can_craft(self.player, output_id, props)

    def craft(self, output_id: str) -> str:
        from items.crafting import craft, find_recipe
        loc = self.player_location()
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
