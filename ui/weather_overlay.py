"""Weather particle overlay — rain / snow / fog / storm.

A small, stateful particle system that the main renderer calls each
frame. Particles live in screen-space (not world-space) so they sweep
through the view regardless of camera motion.
"""

import logging
import math
import random
from dataclasses import dataclass
from typing import List

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.weather_overlay")


# How many active particles per weather type
PARTICLE_COUNTS = {
    "clear": 0,
    "cloudy": 0,
    "fog": 40,
    "rain": 90,
    "storm": 140,
    "snow": 70,
}


@dataclass
class WeatherParticle:
    x: float
    y: float
    vx: float
    vy: float
    length: float
    alpha: int
    age: float = 0.0
    max_age: float = 4.0


class WeatherOverlay:
    """Particle overlay for weather visual flavor."""

    def __init__(self):
        self.kind = "clear"
        self.particles: List[WeatherParticle] = []
        self.rng = random.Random()
        self._fog_surf = None
        self._fog_for_size = (0, 0)
        self._frame_counter = 0

    # ------------------------------------------------------------------

    def update(self, dt: float, weather_kind: str, view_rect) -> None:
        if self.kind != weather_kind:
            self.kind = weather_kind
            self.particles = []

        target_count = PARTICLE_COUNTS.get(weather_kind, 0)
        if target_count == 0:
            self.particles = []
            return

        # Top up
        while len(self.particles) < target_count:
            self.particles.append(self._spawn(view_rect, fresh=False))

        # Advance
        out: List[WeatherParticle] = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.age += dt
            if not view_rect.collidepoint(int(p.x), int(p.y)):
                continue
            if p.age >= p.max_age:
                continue
            out.append(p)
        # Replace any that drifted out / expired
        while len(out) < target_count:
            out.append(self._spawn(view_rect, fresh=True))
        self.particles = out

    def draw(self, target, view_rect) -> None:
        if not PYGAME_OK or self.kind == "clear":
            return
        if self.kind == "fog":
            self._draw_fog(target, view_rect)
            return

        for p in self.particles:
            if not view_rect.collidepoint(int(p.x), int(p.y)):
                continue
            if self.kind in ("rain", "storm"):
                pygame.draw.line(
                    target,
                    (150, 170, 220) if self.kind == "rain"
                    else (180, 200, 250),
                    (int(p.x), int(p.y)),
                    (int(p.x + p.vx * 0.05),
                     int(p.y + p.vy * 0.05)),
                    1,
                )
            elif self.kind == "snow":
                pygame.draw.circle(target, (240, 245, 255),
                                   (int(p.x), int(p.y)), 1)

        if self.kind == "storm" and self._frame_counter % 90 == 0:
            self._draw_lightning(target, view_rect)
        self._frame_counter += 1

    # ------------------------------------------------------------------

    def _spawn(self, view_rect, fresh: bool) -> WeatherParticle:
        x = self.rng.uniform(view_rect.left, view_rect.right)
        if fresh:
            y = view_rect.top - self.rng.uniform(0, 30)
        else:
            y = self.rng.uniform(view_rect.top, view_rect.bottom)
        if self.kind == "rain":
            return WeatherParticle(
                x=x, y=y, vx=-30, vy=320,
                length=8, alpha=160, max_age=3.0)
        if self.kind == "storm":
            return WeatherParticle(
                x=x, y=y, vx=-90, vy=420,
                length=12, alpha=200, max_age=3.0)
        if self.kind == "snow":
            return WeatherParticle(
                x=x, y=y,
                vx=self.rng.uniform(-25, 25),
                vy=self.rng.uniform(35, 70),
                length=3, alpha=200, max_age=10.0)
        if self.kind == "fog":
            return WeatherParticle(
                x=x, y=y,
                vx=self.rng.uniform(-8, 8),
                vy=self.rng.uniform(-4, 4),
                length=20,
                alpha=self.rng.randint(40, 90), max_age=8.0)
        return WeatherParticle(x=x, y=y, vx=0, vy=0, length=1, alpha=0)

    def _draw_fog(self, target, view_rect) -> None:
        # Cache a fog surface, drift it slightly to suggest motion
        size = (view_rect.width, view_rect.height)
        if self._fog_surf is None or self._fog_for_size != size:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            for _ in range(120):
                x = self.rng.randint(0, size[0])
                y = self.rng.randint(0, size[1])
                r = self.rng.randint(20, 60)
                a = self.rng.randint(20, 50)
                pygame.draw.circle(surf, (220, 225, 235, a), (x, y), r)
            self._fog_surf = surf
            self._fog_for_size = size
        target.blit(self._fog_surf, view_rect.topleft)

    def _draw_lightning(self, target, view_rect) -> None:
        # Brief screen flash + jagged white line
        flash = pygame.Surface((view_rect.width, view_rect.height),
                               pygame.SRCALPHA)
        flash.fill((255, 255, 255, 60))
        target.blit(flash, view_rect.topleft)
        # Jagged bolt
        start_x = self.rng.randint(view_rect.left + 50, view_rect.right - 50)
        x = start_x
        points = [(x, view_rect.top)]
        y = view_rect.top
        while y < view_rect.bottom - 20:
            y += self.rng.randint(8, 18)
            x += self.rng.randint(-12, 12)
            points.append((x, y))
        if len(points) > 1:
            pygame.draw.lines(target, (255, 255, 255), False, points, 2)
