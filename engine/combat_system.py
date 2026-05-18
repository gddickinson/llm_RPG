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

        # If the player has a ranged weapon equipped, melee uses fists
        # (less damage). Otherwise use the equipped melee weapon.
        try:
            from characters.equipment import equipped_weapon
            w = equipped_weapon(self.engine.player)
            if w is not None and w.is_ranged_weapon():
                self.engine.memory_manager.add_event(
                    f"You strike with the butt of your {w.name}.")
        except Exception:
            pass

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
        """Roll an attack, apply damage, possibly defeat the target.

        D&D-style:
          - Attack roll = 1d20 + ability_mod + proficiency_bonus
          - vs target effective_ac.
          - Nat 20 = crit (double damage).
          - Nat 1 = fumble (auto miss).
          - Flanking adjacent ally on opposite side: +2 to hit.
        """
        from engine.effects import (
            effective_ac, effective_ability_mod, proficiency_bonus,
            effective_weapon_damage_bonus,
        )

        # Determine ability + verb by action type
        if action_type == "cast":
            atk_ability = "intelligence"
            verb = "casts a spell at"
        elif action_type in ("shoot",):
            atk_ability = "dexterity"
            verb = "shoots at"
        else:
            atk_ability = "strength"
            verb = "attacks"

        atk_mod = effective_ability_mod(attacker, atk_ability)
        prof = proficiency_bonus(attacker)

        # Flanking bonus
        flanking = self._flanking_bonus(attacker, defender)

        # Roll attack
        roll = self.rng.randint(1, 20)
        natural_crit = (roll == 20)
        natural_fumble = (roll == 1)
        total_to_hit = roll + atk_mod + prof + flanking
        ac = effective_ac(defender)

        if natural_fumble or (not natural_crit and total_to_hit < ac):
            kind = "fumbles" if natural_fumble else "misses"
            return f"{attacker.name} {verb} {defender.name} but {kind}!"

        # Damage roll: weapon-base + ability + enchant + status mod
        weapon_dmg = self._best_weapon_damage(attacker)
        enchant_dmg = effective_weapon_damage_bonus(attacker)
        try:
            from characters.status_effects import attack_damage_modifier
            stat_mod = attack_damage_modifier(attacker)
        except Exception:
            stat_mod = 0
        base = max(1, weapon_dmg + max(0, atk_mod) + enchant_dmg + stat_mod)
        roll_dmg = self.rng.randint(1, max(1, weapon_dmg or 4))
        damage = max(1, roll_dmg + max(0, atk_mod) + enchant_dmg + stat_mod)
        if natural_crit:
            damage *= 2

        # Damage-type vs target weakness (e.g. silver vs trolls)
        damage = self._apply_damage_type_modifier(attacker, defender, damage)

        defender.take_damage(damage)

        # Visual effects (damage popup + hit flash + death FX)
        try:
            ce = getattr(self.engine, "combat_effects", None)
            if ce:
                ce.on_damage_dealt(defender, damage, is_kill=not defender.is_alive())
        except Exception:
            pass

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
        # Prefer equipped weapon
        try:
            from characters.equipment import equipped_weapon
            w = equipped_weapon(char)
            if w is not None and w.is_weapon():
                return int(w.damage)
        except Exception:
            pass
        # Fallback: best weapon in inventory (unarmed strikes deal 1)
        from items.item import Item
        best = 0
        for it in getattr(char, "inventory", []):
            if isinstance(it, Item) and it.is_weapon() and it.damage > best:
                best = it.damage
        return best  # 0 -> unarmed (still does 1 minimum via base clamp)

    def _total_armor(self, char) -> int:
        # Prefer effects-aware AC contribution
        try:
            from engine.effects import total_armor_value
            return total_armor_value(char)
        except Exception:
            pass
        from items.item import Item
        total = 0
        for it in getattr(char, "inventory", []):
            if isinstance(it, Item) and it.is_armor():
                total += it.armor
        return total

    def _flanking_bonus(self, attacker, defender) -> int:
        """+2 to hit if an attacker has an ally on the opposite side of the
        defender. Compares positions; checks both axes.
        """
        try:
            ax, ay = attacker.position
            dx, dy = defender.position
            # Look for any active ally adjacent to the defender on the
            # opposite side of attacker
            opp_x = dx + (dx - ax)
            opp_y = dy + (dy - ay)
            # Use party + other non-hostile NPCs as allies-of-player
            allies_iter = []
            try:
                if attacker.id == self.engine.player.id:
                    allies_iter = self.engine.companion_manager.members()
                else:
                    klass = getattr(attacker.character_class, "value", "")
                    # Hostile attackers can flank with other hostile NPCs
                    if klass in ("brigand", "troll", "monster"):
                        allies_iter = [
                            n for n in self.engine.npc_manager.npcs.values()
                            if n.id != attacker.id and n.is_active()
                            and getattr(n.character_class, "value", "") in
                            ("brigand", "troll", "monster")
                        ]
            except Exception:
                allies_iter = []
            for ally in allies_iter:
                if not ally.is_active():
                    continue
                if ally.position == (opp_x, opp_y):
                    return 2
        except Exception:
            pass
        return 0

    def _apply_damage_type_modifier(self, attacker, defender, damage: int) -> int:
        """Silver vs trolls/undead, fire vs trolls, etc."""
        try:
            from characters.equipment import equipped_weapon
            w = equipped_weapon(attacker)
            if w is None:
                return damage
            kind = (w.damage_kind or "slash").lower()
            target_class = getattr(defender.character_class, "value", "")
            target_race = getattr(defender.race, "value", "")

            # Silver / holy vs troll, monster
            if "silver" in (w.id or "") or "silver" in (w.name.lower() or ""):
                if target_race == "troll" or target_class in ("troll", "monster"):
                    return int(damage * 1.5)
            if kind == "holy" and target_class in ("monster", "brigand"):
                return int(damage * 1.3)
            # Fire vs troll (regenerator)
            if kind == "fire" and target_race == "troll":
                return int(damage * 1.5)
            # Frost mildly weaker vs frost-naturalish? skip
        except Exception:
            pass
        return damage

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
