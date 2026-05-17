"""Combat system — attack rolls, damage, defeat, looting.

Extracted from the legacy monolithic game_engine.py.
"""

import logging
import random
from typing import Any, Optional, Tuple

logger = logging.getLogger("llm_rpg.combat")


class CombatSystem:
    """Resolves combat between any two characters."""

    def __init__(self, engine):
        self.engine = engine
        self.rng = random.Random()

    # --------------------------------------------------------- player attack

    def player_attack(self, target_name: str) -> str:
        target = self.engine.find_character(target_name)
        if not target:
            return f"You don't see {target_name} here."

        px, py = self.engine.player.position
        tx, ty = target.position
        if ((px - tx) ** 2 + (py - ty) ** 2) ** 0.5 > 1.5:
            return f"{target.name} is too far away to attack."

        return self._resolve(self.engine.player, target, "attack")

    # --------------------------------------------------------- npc attack

    def npc_attack(self, attacker, target_text: str, action_type: str = "attack") -> bool:
        target = self.engine.find_character(target_text)
        if not target:
            return False
        if target.id == attacker.id:
            return False

        ax, ay = attacker.position
        tx, ty = target.position
        dist = ((ax - tx) ** 2 + (ay - ty) ** 2) ** 0.5

        attack_range = 5.0 if action_type in ("shoot", "cast") else 1.5
        if dist > attack_range:
            # Move toward
            return self._step_toward(attacker, target)

        result = self._resolve(attacker, target, action_type)
        self.engine.memory_manager.add_event(result)
        return True

    # --------------------------------------------------------- internals

    def _resolve(self, attacker, defender, action_type: str = "attack") -> str:
        """Roll an attack, apply damage, possibly defeat the target."""
        # Choose stats
        if action_type == "cast":
            atk_stat = attacker.intelligence
            def_stat = defender.wisdom
            verb = "casts a spell at"
        elif action_type == "shoot":
            atk_stat = attacker.dexterity
            def_stat = defender.dexterity
            verb = "shoots at"
        else:
            atk_stat = attacker.strength
            def_stat = defender.constitution
            verb = "attacks"

        # Weapon damage bonus from inventory
        weapon_dmg = self._best_weapon_damage(attacker)
        armor_red = self._total_armor(defender)

        # Hit chance
        hit_chance = max(0.1, min(0.9, 0.5 + 0.05 * (atk_stat - def_stat)))
        if self.rng.random() > hit_chance:
            return f"{attacker.name} {verb} {defender.name} but misses!"

        base = max(1, atk_stat // 3) + weapon_dmg
        damage = max(1, base + self.rng.randint(-1, 1) - armor_red)
        defender.take_damage(damage)

        attacker.add_memory(
            f"I attacked {defender.name} and dealt {damage} damage", 2)
        if attacker.id != defender.id:
            defender.modify_relationship(attacker.id, -20)
            attacker.modify_relationship(defender.id, -10)

        if not defender.is_alive():
            return self._handle_defeat(attacker, defender, damage)
        return f"{attacker.name} {verb} {defender.name} for {damage} damage!"

    def _handle_defeat(self, attacker, defender, damage: int) -> str:
        defender.defeat()
        defender.last_position = defender.position
        msg = (
            f"{attacker.name} attacks {defender.name} for {damage} damage. "
            f"{defender.name} is defeated!"
        )
        self.engine.memory_manager.add_event(msg)

        # Drops via loot tables
        try:
            from items.loot_tables import generate_loot
            drops = generate_loot(defender, rng=self.rng)
            for item in drops:
                self.engine.world.add_item_to_ground(
                    item, defender.position[0], defender.position[1]
                )
            if drops:
                names = ", ".join(str(i) for i in drops)
                self.engine.memory_manager.add_event(
                    f"{defender.name} drops: {names}"
                )
        except Exception as e:
            logger.warning(f"Loot generation error: {e}")

        # Body marker for revival shrines
        self.engine.world.add_item_to_ground(
            f"{defender.name}'s body", defender.position[0], defender.position[1]
        )

        # Player defeated — flag for UI; UIs that don't handle it
        # fall back to end_game (terminal mode).
        if defender.id == self.engine.player.id:
            self.engine.memory_manager.add_event("You have been defeated!")
            self.engine.player_dead = True
            # The GUI catches `player_dead` and shows a restart/quit menu.
            # The terminal UI doesn't, so end the game as a safety net.
            if not getattr(self.engine, "_has_gui", False):
                self.engine.end_game()
        else:
            self.engine.world.map.remove_character(defender)
            kls = getattr(getattr(defender, "character_class", None),
                          "value", "")
            # Notify quest manager
            if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
                self.engine.quest_manager.on_npc_defeated(defender.id, kls)
            # XP + faction rep changes for player kills
            if attacker.id == self.engine.player.id:
                self._award_xp(defender)
                self._update_faction_rep(kls)

        return msg

    def _award_xp(self, defeated) -> None:
        from engine.leveling import award_xp
        xp = 20 + 30 * getattr(defeated, "level", 1)
        msgs = award_xp(self.engine.player, xp)
        self.engine.memory_manager.add_event(f"You gain {xp} XP.")
        for m in msgs:
            self.engine.memory_manager.add_event(m)

    def _update_faction_rep(self, victim_class: str) -> None:
        try:
            from characters.factions import on_defeat
            deltas = on_defeat(self.engine.player, victim_class)
            for faction, delta in deltas.items():
                sign = "+" if delta > 0 else ""
                self.engine.memory_manager.add_event(
                    f"Reputation with {faction}: {sign}{delta}")
        except Exception as e:
            logger.warning(f"Faction rep update failed: {e}")

    # --------------------------------------------------------- helpers

    def _best_weapon_damage(self, char) -> int:
        from items.item import Item
        best = 0
        for it in char.inventory:
            if isinstance(it, Item) and it.is_weapon() and it.damage > best:
                best = it.damage
        return best

    def _total_armor(self, char) -> int:
        from items.item import Item
        total = 0
        for it in char.inventory:
            if isinstance(it, Item) and it.is_armor():
                total += it.armor
        return total

    def _step_toward(self, attacker, target) -> bool:
        dx = target.position[0] - attacker.position[0]
        dy = target.position[1] - attacker.position[1]
        dx = (dx > 0) - (dx < 0)
        dy = (dy > 0) - (dy < 0)
        if dx and dy:
            if abs(target.position[0] - attacker.position[0]) > \
                    abs(target.position[1] - attacker.position[1]):
                dy = 0
            else:
                dx = 0
        nx = attacker.position[0] + dx
        ny = attacker.position[1] + dy
        return self.engine.world.map.move_character(attacker, nx, ny)
