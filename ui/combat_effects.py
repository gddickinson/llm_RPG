"""Combat visual effects.

Adapted from autonomous_world/game/ui/combat_effects.py + renderer_effects.py.

Provides:
- DamagePopup, HitFlash, DeathEffect dataclasses (transient visuals).
- Particle (for spell bursts).
- CombatEffects manager that the renderer queries each frame.

All effects live in world coordinates (tile units). The renderer converts
to screen pixels using the camera offset.
"""

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.combat_effects")


@dataclass
class DamagePopup:
    x: float
    y: float
    value: int
    color: Tuple[int, int, int] = (255, 60, 60)
    age: float = 0.0
    max_age: float = 1.0
    vy: float = -2.0    # tiles per second upward


@dataclass
class HitFlash:
    entity_id: str
    x: float
    y: float
    color: Tuple[int, int, int] = (255, 220, 220)
    age: float = 0.0
    max_age: float = 0.18


@dataclass
class DeathEffect:
    x: float
    y: float
    age: float = 0.0
    max_age: float = 0.9
    particles: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    size: int = 3
    life: float = 0.6
    max_life: float = 0.6
    gravity: float = 0.0


# Spell -> particle colors (RGB triples)
SPELL_PARTICLE_COLORS = {
    "fireball":      [(255, 120, 30), (255, 80, 30), (220, 60, 30)],
    "magic_missile": [(120, 160, 255), (140, 180, 255), (180, 200, 255)],
    "frost_ray":     [(160, 220, 255), (200, 240, 255), (220, 250, 255)],
    "shock":         [(255, 255, 140), (240, 240, 200), (255, 255, 200)],
    "heal":          [(120, 240, 120), (180, 255, 180), (200, 255, 200)],
    "bless":         [(255, 240, 180), (255, 220, 140), (255, 255, 200)],
    "poison_dart":   [(120, 200, 80), (140, 220, 100), (100, 180, 60)],
}


class CombatEffects:
    """Visual-effects manager owned by the engine."""

    def __init__(self, engine):
        self.engine = engine
        self.damage_popups: List[DamagePopup] = []
        self.hit_flashes: List[HitFlash] = []
        self.death_effects: List[DeathEffect] = []
        self.particles: List[Particle] = []
        self._font_dmg = None
        self.rng = random.Random()

    # ------------------------------------------------------------------ public spawn API

    def on_damage_dealt(self, target, damage: int, is_kill: bool = False) -> None:
        if damage <= 0:
            return
        tx, ty = target.position
        self.spawn_damage_popup(tx, ty, damage, color=(255, 60, 60))
        self.spawn_hit_flash(target)
        if is_kill:
            self.spawn_death_effect(tx, ty)

    def on_heal(self, target, amount: int) -> None:
        tx, ty = target.position
        self.spawn_damage_popup(tx, ty, amount, color=(80, 220, 80))

    def on_miss_at(self, x: float, y: float) -> None:
        """A grey 'miss' popup where a shot went wide (BLD/ranged effects)."""
        self.damage_popups.append(
            DamagePopup(x, y - 0.2, "miss", (205, 210, 220), max_age=0.7))

    def spawn_damage_popup(self, x: float, y: float, value: int,
                           color: Tuple[int, int, int] = (255, 60, 60)) -> None:
        jx = x + self.rng.uniform(-0.2, 0.2)
        jy = y - 0.2 + self.rng.uniform(-0.1, 0.1)
        self.damage_popups.append(DamagePopup(jx, jy, value, color))

    def spawn_hit_flash(self, entity, color=(255, 220, 220)) -> None:
        eid = getattr(entity, "id", "?")
        # Refresh if already flashing
        for f in self.hit_flashes:
            if f.entity_id == eid:
                f.age = 0.0
                f.color = color
                return
        self.hit_flashes.append(HitFlash(
            entity_id=eid, x=entity.position[0], y=entity.position[1],
            color=color))

    def spawn_death_effect(self, x: float, y: float) -> None:
        parts: List[Dict[str, Any]] = []
        for _ in range(5):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(1.5, 3.5)
            gray = self.rng.randint(80, 180)
            is_red = self.rng.random() < 0.6
            color = ((self.rng.randint(160, 220), 30, 30) if is_red
                     else (gray, gray, gray))
            parts.append({
                "dx": 0.0, "dy": 0.0,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 1.5,
                "color": color,
                "size": self.rng.randint(2, 4),
            })
        self.death_effects.append(DeathEffect(x=x, y=y, particles=parts))

    def spawn_spell_burst(self, spell_id: str, x: float, y: float) -> None:
        colors = SPELL_PARTICLE_COLORS.get(spell_id,
                                            SPELL_PARTICLE_COLORS["magic_missile"])
        count = 12 if spell_id in ("fireball", "shock") else 8
        for _ in range(count):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(0.8, 2.4)
            color = self.rng.choice(colors)
            life = self.rng.uniform(0.5, 1.0)
            self.particles.append(Particle(
                x=x, y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 0.6,
                color=color,
                size=self.rng.randint(2, 4),
                life=life, max_life=life,
                gravity=0.7 if spell_id != "heal" else -0.3,
            ))

    # ------------------------------------------------------------------ frame update / draw

    def update(self, dt: float) -> None:
        # Popups
        survivors: List[DamagePopup] = []
        for p in self.damage_popups:
            p.age += dt
            if p.age >= p.max_age:
                continue
            p.y += p.vy * dt
            p.vy *= 0.92
            survivors.append(p)
        self.damage_popups = survivors

        # Flashes
        self.hit_flashes = [
            f for f in self.hit_flashes
            if (setattr(f, "age", f.age + dt) or True) and f.age < f.max_age
        ]

        # Death effects
        for d in self.death_effects:
            d.age += dt
            for part in d.particles:
                part["dx"] += part["vx"] * dt
                part["dy"] += part["vy"] * dt
                part["vy"] += 4.0 * dt  # gravity
                part["vx"] *= 0.96
        self.death_effects = [d for d in self.death_effects if d.age < d.max_age]

        # Particles
        psurv: List[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += p.gravity * dt
            psurv.append(p)
        self.particles = psurv

    def draw(self, target: "pygame.Surface", view_rect,
             cam_x: int, cam_y: int, tile_size: int) -> None:
        """Top-down draw: a grid camera maps world tiles → screen."""
        def to_screen(x, y):
            return self._world_to_screen(x, y, view_rect, cam_x, cam_y,
                                         tile_size)
        self.draw_with(target, view_rect, to_screen, tile_size)

    def draw_with(self, target, view_rect, to_screen, tile_size) -> None:
        """Projection-agnostic draw (P41.12): `to_screen(x, y) -> (sx, sy)` maps
        a world tile to screen — the grid for top-down, the IsoProjection for the
        3D view — so damage popups / hit flashes / death particles read in both."""
        if not PYGAME_OK:
            return
        self._ensure_font()
        for p in self.damage_popups:
            self._draw_popup(target, view_rect, p, to_screen, tile_size)
        for f in self.hit_flashes:
            self._draw_flash(target, view_rect, f, to_screen, tile_size)
        for d in self.death_effects:
            self._draw_death(target, view_rect, d, to_screen, tile_size)
        for p in self.particles:
            self._draw_particle(target, view_rect, p, to_screen, tile_size)

    # ------------------------------------------------------------------ internals

    def _ensure_font(self):
        if self._font_dmg is None:
            try:
                pygame.font.init()
                self._font_dmg = pygame.font.SysFont("monospace", 14, bold=True)
            except Exception:
                self._font_dmg = None

    def _world_to_screen(self, x: float, y: float, view_rect,
                         cam_x: int, cam_y: int, tile_size: int):
        sx = view_rect.x + (x - cam_x) * tile_size + tile_size // 2
        sy = view_rect.y + (y - cam_y) * tile_size + tile_size // 2
        return int(sx), int(sy)

    def _on_screen(self, sx: int, sy: int, view_rect) -> bool:
        return view_rect.collidepoint(sx, sy)

    def _draw_popup(self, surf, view_rect, p, to_screen, tile_size):
        if not self._font_dmg:
            return
        sx, sy = to_screen(p.x, p.y)
        if not self._on_screen(sx, sy, view_rect):
            return
        alpha = max(0, int(255 * (1 - p.age / p.max_age)))
        text = self._font_dmg.render(str(p.value), True, p.color)
        text.set_alpha(alpha)
        surf.blit(text, (sx - text.get_width() // 2, sy - 18))

    def _draw_flash(self, surf, view_rect, f, to_screen, tile_size):
        sx, sy = to_screen(f.x, f.y)
        if not self._on_screen(sx, sy, view_rect):
            return
        alpha = max(0, int(180 * (1 - f.age / f.max_age)))
        r = tile_size // 2
        overlay = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (*f.color, alpha), (r, r), r)
        surf.blit(overlay, (sx - r, sy - r))

    def _draw_death(self, surf, view_rect, d, to_screen, tile_size):
        sx, sy = to_screen(d.x, d.y)
        if not self._on_screen(sx, sy, view_rect):
            return
        # Red flash for first 0.15s
        if d.age < 0.15:
            alpha = int(160 * (1 - d.age / 0.15))
            overlay = pygame.Surface((tile_size, tile_size),
                                     pygame.SRCALPHA)
            overlay.fill((220, 30, 30, alpha))
            surf.blit(overlay, (sx - tile_size // 2, sy - tile_size // 2))
        # Particles
        for part in d.particles:
            px = sx + int(part["dx"] * 4)
            py = sy + int(part["dy"] * 4)
            pygame.draw.rect(surf, part["color"],
                             (px, py, part["size"], part["size"]))

    def _draw_particle(self, surf, view_rect, p, to_screen, tile_size):
        sx, sy = to_screen(p.x, p.y)
        if not self._on_screen(sx, sy, view_rect):
            return
        alpha = max(0, int(220 * (p.life / p.max_life)))
        size = max(1, p.size)
        overlay = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (*p.color, alpha), (size, size), size)
        surf.blit(overlay, (sx - size, sy - size))
