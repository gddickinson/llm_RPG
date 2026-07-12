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

        from engine.presence import npc_adjacent_to_player
        if not npc_adjacent_to_player(self.engine, target):
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

        # Companions focus-fire the player's current target (P7.3)
        self.engine.player_target_id = target.id
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

        # Assault has consequences: a peaceful NPC the player attacks
        # turns hostile (fight back or flee — heuristic provider) and
        # word of it costs villager goodwill (P7 follow-up, George)
        if attacker.id == self.engine.player.id:
            kls = getattr(getattr(defender, "character_class", None),
                          "value", "")
            if kls not in ("brigand", "monster", "troll") and \
                    not defender.metadata.get("provoked"):
                defender.metadata["provoked"] = True
                self.engine.memory_manager.add_event(
                    f"{defender.name} turns on you!")
                try:
                    from characters.factions import Faction, modify_rep
                    delta = modify_rep(self.engine.player,
                                       Faction.VILLAGERS, -3)
                    self.engine.memory_manager.add_event(
                        f"Reputation with villagers: -3 ({delta})")
                except Exception:
                    pass

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

        # Flanked defenders are OFF-GUARD (-2 AC) — P12.2 replaces
        # the old attacker-side +2 with a visible condition
        from characters.status_effects import (ac_penalty,
                                               apply_effect,
                                               attack_penalty)
        if self._flanking_bonus(attacker, defender) > 0:
            apply_effect(defender, "off_guard", duration=1)

        # Roll attack
        roll = self.rng.randint(1, 20)
        natural_crit = (roll == 20)
        natural_fumble = (roll == 1)
        total_to_hit = roll + atk_mod + prof + \
            attack_penalty(attacker)
        ac = effective_ac(defender) + ac_penalty(defender)

        if natural_fumble or (not natural_crit and total_to_hit < ac):
            kind = "fumbles" if natural_fumble else "misses"
            return f"{attacker.name} {verb} {defender.name} but {kind}!"

        if natural_crit:
            # a perfect strike opens a wound (P12.2)
            apply_effect(defender, "persistent_damage", duration=99,
                         data={"amount": 2, "kind": "bleeding"})
            if defender.id == self.engine.player.id:
                try:   # a deep cut can turn (P12.12)
                    from engine.infection import maybe_infect
                    maybe_infect(self.engine, 0.15, "the deep cut")
                except Exception:
                    pass
        # Damage roll: weapon-base + ability + enchant + status mod
        weapon_dmg = self._best_weapon_damage(attacker)
        enchant_dmg = effective_weapon_damage_bonus(attacker)
        try:
            from characters.status_effects import attack_damage_modifier
            from characters.needs import (exhaustion_attack_penalty,
                                          hunger_attack_penalty)
            from engine.wounds import attack_penalty as wound_atk
            stat_mod = attack_damage_modifier(attacker) + \
                hunger_attack_penalty(attacker) + \
                exhaustion_attack_penalty(attacker) + \
                wound_atk(attacker)          # arm wounds (P15.9)
        except Exception:
            stat_mod = 0
        base = max(1, weapon_dmg + max(0, atk_mod) + enchant_dmg + stat_mod)
        roll_dmg = self.rng.randint(1, max(1, weapon_dmg or 4))
        damage = max(1, roll_dmg + max(0, atk_mod) + enchant_dmg + stat_mod)
        if natural_crit:
            damage *= 2

        # Damage-type vs target weakness (e.g. silver vs trolls)
        from engine.combat_math import damage_type_modifier
        damage = damage_type_modifier(attacker, defender, damage)

        defender.take_damage(damage)
        try:   # damage forces the keep-it check (P12.7)
            from engine.combat_depth import concentration_check
            concentration_check(self.engine, defender, damage)
        except Exception:
            pass
        try:   # serious wounds splash blood (P14.2a)
            from engine.surfaces import BLOOD_THRESHOLD
            if damage >= BLOOD_THRESHOLD and \
                    self.engine.active_zone() is None:
                self.engine.surfaces_layer.splash_blood(
                    *defender.position)
        except Exception:
            pass
        try:   # and it may break a body part (P15.9)
            from engine.wounds import maybe_wound
            maybe_wound(self.engine, damage, defender)
        except Exception:
            pass
        try:   # a boss may cross a phase threshold (P15.6)
            from engine.bosses import boss_on_damaged, is_boss
            if defender.is_alive() and is_boss(defender):
                boss_on_damaged(self.engine, defender)
        except Exception:
            pass
        self._wear_gear(attacker, defender)

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
        # The player's defeat is a story beat, not always a game over
        if defender.id == self.engine.player.id:
            return self._handle_player_defeat(attacker, damage)

        # An elite you strike down may escape as a nemesis instead (P19.6)
        # — before the person/monster split, so it works for either.
        if attacker.id == self.engine.player.id:
            try:
                escape = self.engine.nemesis.intercept_death(defender)
                if escape is not None:
                    return escape
            except Exception:
                pass

        # People are knocked out; monsters die (P12.4, Kenshi)
        try:
            from engine.dying import is_person, ko_person
            person = is_person(defender)
        except Exception:
            person = False
        if person:
            msg = ko_person(self.engine, attacker, defender)
            kls = getattr(getattr(defender, "character_class", None),
                          "value", "")
            if self.engine.quest_manager:
                self.engine.quest_manager.on_npc_defeated(
                    defender.id, kls)
            if attacker.id == self.engine.player.id:
                self._award_xp(defender)
                self._update_faction_rep(kls)
                try:
                    from engine.player_deeds import record_deed
                    record_deed(self.engine,
                                f"beat {defender.name} senseless")
                except Exception:
                    pass
            return msg

        defender.defeat()
        defender.last_position = defender.position
        msg = (
            f"{attacker.name} attacks {defender.name} for {damage} damage. "
            f"{defender.name} is defeated!"
        )
        seen = (attacker.id == self.engine.player.id or
                defender.id == self.engine.player.id)
        if not seen:
            try:   # only report a defeat the player could see (P15.11)
                from engine.discovery import can_witness
                seen = can_witness(self.engine, defender.position)
            except Exception:
                from engine.presence import in_earshot
                seen = in_earshot(self.engine, defender.position)
        if seen:
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

        self.engine.world.map.remove_character(defender)
        kls = getattr(getattr(defender, "character_class", None),
                      "value", "")
        # Notify quest manager
        if hasattr(self.engine, "quest_manager") and self.engine.quest_manager:
            self.engine.quest_manager.on_npc_defeated(defender.id, kls)
        try:   # a slain raider beats its tribe back (P19.4)
            if (defender.metadata or {}).get("tribe"):
                self.engine.monster_tribes.on_defeat(defender)
        except Exception:
            pass
        # XP + faction rep changes for player kills
        if attacker.id == self.engine.player.id:
            self._award_xp(defender)
            self._update_faction_rep(kls)
            try:   # felling a wild beast trains Hunting (P15.9b)
                from engine.skill_progression import train_hunting
                train_hunting(self.engine, defender)
            except Exception:
                pass
            try:
                self.engine.collection_log.record_kill(defender)
                from engine.player_deeds import record_deed
                record_deed(self.engine, f"slew {defender.name}")
            except Exception:
                pass
            # A fallen DM creation becomes legend (P6.7)
            try:
                parts = defender.id.split("_")
                tid = "_".join(parts[1:-1]) if \
                    defender.id.startswith("enc_") and len(parts) > 2 \
                    else ""
                if tid in self.engine.dm.defined_monsters:
                    from engine.dm_library import record_legend
                    record_legend({
                        "name": defender.name,
                        "kind": "monster",
                        "story": self.engine.dm.defined_monsters[tid]
                        .get("description", ""),
                        "slain_by": self.engine.player.name,
                        "day": self.engine.dm._day()})
            except Exception:
                pass

        return msg

    def _handle_player_defeat(self, attacker, damage: int) -> str:
        """0 HP: the dying ladder first (P12.4), then the story
        outcomes (P4.7) when it resolves."""
        try:
            from engine.dying import enter_dying, is_dying, worsen
            if is_dying(self.engine.player):
                return worsen(self.engine, attacker)
            self.engine.memory_manager.add_event(
                f"{attacker.name} strikes you down!")
            return enter_dying(self.engine, attacker)
        except Exception as e:
            logger.warning(f"Dying layer error: {e}")
            from engine.defeat import handle_player_defeat
            survived, msg = handle_player_defeat(
                self.engine, attacker, rng=self.rng)
            if not survived:
                self.engine.player.defeat()
                self.engine.player_dead = True
                if not getattr(self.engine, "_has_gui", False):
                    self.engine.end_game()
            return msg

    def _award_xp(self, defeated) -> None:
        from engine.leveling import award_xp
        xp = 20 + 30 * getattr(defeated, "level", 1)
        actor = self.engine.player
        msgs = award_xp(actor, xp)
        # an adventurer NPC (P-M.6) driven through this path gains the XP,
        # but the player-phrased "You gain … / You reached level …" would
        # misattribute to the player — give it a quiet third-person beat
        if (getattr(actor, "metadata", {}) or {}).get("adventurer"):
            if msgs:
                self.engine.memory_manager.add_event(
                    f"[Realm] {actor.name} grows more seasoned in the craft.")
            return
        self.engine.memory_manager.add_event(f"You gain {xp} XP.")
        for m in msgs:
            self.engine.memory_manager.add_event(m)

    def _update_faction_rep(self, victim_class: str) -> None:
        try:
            from characters.factions import on_defeat
            actor = self.engine.player
            deltas = on_defeat(actor, victim_class)
            if (getattr(actor, "metadata", {}) or {}).get("adventurer"):
                return              # an adventurer's rep is its own, not shown
            for faction, delta in deltas.items():
                sign = "+" if delta > 0 else ""
                self.engine.memory_manager.add_event(
                    f"Reputation with {faction}: {sign}{delta}")
        except Exception as e:
            logger.warning(f"Faction rep update failed: {e}")

    # --------------------------------------------------------- helpers

    def _wear_gear(self, attacker, defender) -> None:
        """Landed hits wear the attacker's weapon and defender's armor."""
        try:
            from characters.equipment import equipped_weapon, get_equipment
            from engine.durability import degrade
            notes = []
            w = equipped_weapon(attacker)
            if w is not None:
                notes.append(degrade(w))
            eq = get_equipment(defender)
            for slot in ("armor", "shield"):
                if eq.get(slot) is not None:
                    notes.append(degrade(eq[slot]))
            for note in notes:
                if note:
                    self.engine.memory_manager.add_event(note)
        except Exception:
            pass

    def _best_weapon_damage(self, char) -> int:
        # Prefer equipped weapon
        try:
            from characters.equipment import equipped_weapon
            from engine.durability import is_broken
            w = equipped_weapon(char)
            if w is not None and w.is_weapon():
                return 1 if is_broken(w) else int(w.damage)
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

    def _step_toward(self, attacker, target) -> bool:
        # Approach the nearest FREE tile beside the target rather than
        # its exact square — packs fan out and surround (P7.3)
        from engine.squad_tactics import surround_step, greedy_step
        wmap = self.engine.world.map
        goal = surround_step(wmap, attacker, target) or target.position
        return greedy_step(wmap, attacker, goal)
