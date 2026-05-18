"""Ranged-combat projectile system.

Adapted from autonomous_world/game/systems/projectiles.py.

A projectile is a turn-tracked entity that:
- Flies toward a target position over several turns.
- Hits if the target is still close to where we aimed; otherwise misses.
- Applies damage through the standard combat damage path on hit.

The renderer can show in-flight projectiles by reading
`engine.projectile_manager.active` (list of CombatProjectile, each with
`.x`, `.y`, `.kind` for sprite selection).
"""

import logging
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("llm_rpg.projectiles")


# Turn-based flight: tiles per turn. Larger = faster arrows.
PROJECTILE_SPEED_PER_TURN = {
    "bow": 6.0,
    "longbow": 7.0,
    "crossbow": 5.0,
    "sling": 4.0,
    "thrown_knife": 5.0,
    "javelin": 5.0,
    "spell": 5.0,
    "boulder": 3.0,
}

# Kind string used by the renderer to pick a sprite
PROJECTILE_VISUAL_KIND = {
    "bow": "arrow",
    "longbow": "arrow",
    "crossbow": "bolt",
    "sling": "stone",
    "thrown_knife": "blade",
    "javelin": "arrow",
    "spell": "spell",
    "boulder": "stone",
}

# How far a target can move from the aim point before the projectile misses
MISS_THRESHOLD = 2.0


@dataclass
class CombatProjectile:
    start_x: float
    start_y: float
    target_orig_x: float
    target_orig_y: float
    x: float
    y: float
    speed: float                # tiles per turn
    damage: int
    shooter_id: str
    target_id: str
    weapon_type: str
    kind: str
    elapsed: float = 0.0
    flight_time: float = 1.0    # turns until arrival
    arrived: bool = False

    def update(self, dt: float = 1.0) -> bool:
        """Advance position by `dt` turns. Return True when arrived."""
        if self.arrived:
            return True
        self.elapsed += dt
        if self.elapsed >= self.flight_time:
            self.x = self.target_orig_x
            self.y = self.target_orig_y
            self.arrived = True
            return True
        t = self.elapsed / self.flight_time
        self.x = self.start_x + (self.target_orig_x - self.start_x) * t
        self.y = self.start_y + (self.target_orig_y - self.start_y) * t
        return False


@dataclass
class HitResult:
    hit: bool
    damage: int
    shooter_id: str
    target_id: str
    x: float
    y: float
    weapon_type: str
    message: str


class ProjectileManager:
    """Tracks all in-flight projectiles."""

    def __init__(self, engine):
        self.engine = engine
        self.active: List[CombatProjectile] = []
        self.rng = random.Random()

    # ------------------------------------------------------------------

    def spawn(self, shooter, target, damage: int,
              weapon_type: str = "bow") -> CombatProjectile:
        speed = PROJECTILE_SPEED_PER_TURN.get(weapon_type, 5.0)
        kind = PROJECTILE_VISUAL_KIND.get(weapon_type, "arrow")
        sx, sy = shooter.position
        tx, ty = target.position
        dx, dy = tx - sx, ty - sy
        distance = max(0.5, math.sqrt(dx * dx + dy * dy))
        flight_time = max(0.5, distance / speed)
        proj = CombatProjectile(
            start_x=sx, start_y=sy,
            target_orig_x=tx, target_orig_y=ty,
            x=sx, y=sy, speed=speed,
            damage=damage,
            shooter_id=shooter.id, target_id=target.id,
            weapon_type=weapon_type, kind=kind,
            flight_time=flight_time,
        )
        self.active.append(proj)
        return proj

    def tick(self, dt: float = 1.0) -> List[HitResult]:
        """Advance all projectiles. Resolve arrivals."""
        results: List[HitResult] = []
        survivors: List[CombatProjectile] = []
        for proj in self.active:
            arrived = proj.update(dt)
            if arrived:
                results.append(self._resolve(proj))
            else:
                survivors.append(proj)
        self.active = survivors
        return results

    # ------------------------------------------------------------------

    def _resolve(self, proj: CombatProjectile) -> HitResult:
        shooter = self._find_character(proj.shooter_id)
        target = self._find_character(proj.target_id)
        shooter_name = shooter.name if shooter else "Someone"
        target_name = target.name if target else "the target"

        # Miss if target has moved beyond threshold or died
        if target is None or not target.is_alive():
            return HitResult(
                hit=False, damage=0,
                shooter_id=proj.shooter_id, target_id=proj.target_id,
                x=proj.target_orig_x, y=proj.target_orig_y,
                weapon_type=proj.weapon_type,
                message=f"{shooter_name}'s {proj.weapon_type} finds no target.",
            )

        tx, ty = target.position
        moved = math.hypot(tx - proj.target_orig_x, ty - proj.target_orig_y)
        if moved > MISS_THRESHOLD:
            return HitResult(
                hit=False, damage=0,
                shooter_id=proj.shooter_id, target_id=proj.target_id,
                x=proj.target_orig_x, y=proj.target_orig_y,
                weapon_type=proj.weapon_type,
                message=f"{shooter_name}'s {proj.weapon_type} misses "
                        f"{target_name} — they sidestepped.",
            )

        # Hit roll — 75% base chance, modified by shooter DEX vs target DEX
        dex_diff = (getattr(shooter, "dexterity", 10) -
                    getattr(target, "dexterity", 10))
        hit_chance = max(0.2, min(0.95, 0.75 + 0.04 * dex_diff))
        if self.rng.random() > hit_chance:
            return HitResult(
                hit=False, damage=0,
                shooter_id=proj.shooter_id, target_id=proj.target_id,
                x=tx, y=ty,
                weapon_type=proj.weapon_type,
                message=f"{shooter_name}'s {proj.weapon_type} just misses "
                        f"{target_name}.",
            )

        # Apply damage
        armor = self._armor_of(target)
        actual = max(1, proj.damage + self.rng.randint(-1, 1) - armor)
        target.take_damage(actual)
        msg = (f"{shooter_name}'s {proj.weapon_type} hits {target_name} "
               f"for {actual} damage!")

        # Trigger visual effects if available
        try:
            if hasattr(self.engine, "combat_effects"):
                self.engine.combat_effects.on_damage_dealt(
                    target, actual, is_kill=not target.is_alive())
        except Exception:
            pass

        # Death handling — delegate to combat_system
        if not target.is_alive():
            try:
                self.engine.combat_system._handle_defeat(shooter, target, actual)
            except Exception:
                logger.warning(f"defeat handler error", exc_info=True)

        return HitResult(
            hit=True, damage=actual,
            shooter_id=proj.shooter_id, target_id=proj.target_id,
            x=tx, y=ty,
            weapon_type=proj.weapon_type, message=msg,
        )

    # ------------------------------------------------------------------

    def _find_character(self, char_id: str):
        if char_id == self.engine.player.id:
            return self.engine.player
        return self.engine.npc_manager.get_npc(char_id)

    def _armor_of(self, char) -> int:
        try:
            from characters.equipment import total_armor
            armor = total_armor(char)
            if armor:
                return armor
        except Exception:
            pass
        from items.item import Item
        total = 0
        for it in getattr(char, "inventory", []):
            if isinstance(it, Item) and it.is_armor():
                total += it.armor
        return total

    @property
    def count(self) -> int:
        return len(self.active)
