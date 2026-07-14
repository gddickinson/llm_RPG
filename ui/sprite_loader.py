"""Procedural sprite loader.

All sprites are generated at runtime by drawing into pygame Surfaces —
no PNG/asset pipeline is required. The game stays fully self-contained.

Inspired by `autonomous_world/game/ui/sprite_loader.py` but pared down.
"""

import logging
import random
from typing import Dict, Tuple

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover
    PYGAME_OK = False

logger = logging.getLogger("llm_rpg.sprite_loader")

# Palette --------------------------------------------------------------
PALETTE = {
    "grass":      (90, 150, 70),
    "grass2":     (70, 130, 60),
    "forest":     (35, 90, 45),
    "forest2":    (20, 70, 30),
    "mountain":   (110, 100, 95),
    "mountain2":  (140, 130, 125),
    "water":      (45, 100, 180),
    "water2":     (70, 140, 210),
    "road":       (160, 130, 90),
    "bridge":     (135, 95, 55),
    "bridge2":    (100, 70, 40),
    "building":   (140, 100, 60),
    "building2":  (90, 60, 30),
    "cave":       (30, 30, 35),
    "swamp":      (62, 78, 52),
    "swamp2":     (44, 62, 48),
    "swamp_pool": (38, 58, 66),
    "farmland":   (124, 92, 56),
    "farmland2":  (100, 72, 44),
    "rubble":     (105, 100, 95),
    "rubble2":    (80, 76, 72),
    "scorched":   (48, 40, 36),
    "shrine":     (210, 200, 130),
    "shrine_glow":(255, 220, 150),
    "outline":    (10, 10, 10),
    "skin":       (230, 190, 150),
    "hair_brown": (60, 35, 20),
    "hair_grey":  (160, 160, 165),
    "armor":      (130, 130, 150),
    "robe":       (90, 60, 130),
    "leather":    (110, 70, 35),
    "blood":      (160, 30, 30),
    "gold":       (220, 180, 60),
    "potion":     (190, 60, 60),
    "shadow":     (0, 0, 0, 60),
}


class SpriteLoader:
    """Cache of procedurally-generated sprites keyed by id."""

    def __init__(self, tile_size: int = 32):
        if not PYGAME_OK:
            raise RuntimeError("pygame not installed")
        self.tile_size = tile_size
        self._tile_cache: Dict[str, pygame.Surface] = {}
        self._char_cache: Dict[str, pygame.Surface] = {}
        self._variant_cache: Dict[tuple, pygame.Surface] = {}
        self._rng = random.Random(1)
        self.tileset_dir = self._resolve_tileset()

    def tile_variant(self, terrain_name: str, wx: int, wy: int):
        """P33.1: a per-WORLD-POSITION terrain tile — one of N textured variants
        picked by a hash of (wx, wy), so neighbours differ and the grid stops
        reading as one repeated stamp. A PNG tileset or a recipe-less terrain
        falls straight back to the classic single `tile()` surface."""
        from ui import tile_variants
        if self.tileset_dir is not None or \
                terrain_name not in tile_variants.RECIPES:
            return self.tile(terrain_name)
        v = tile_variants.variant_index(wx, wy, terrain_name)
        key = (terrain_name, v)
        surf = self._variant_cache.get(key)
        if surf is None:
            surf = tile_variants.build_tile(terrain_name, v, self.tile_size)
            if surf is None:
                surf = self.tile(terrain_name)
            self._variant_cache[key] = surf
        return surf

    # -------------------------------------------- tileset (P15.1)

    def _resolve_tileset(self):
        """PNG tilesets: data/tiles/<name>/ with one image per
        terrain value (grass.png, water.png, ...) and optional
        entities/<class>.png. Pick via config.TILESET_NAME or the
        LLM_RPG_TILESET env var; None/'' = procedural sprites.
        See data/tiles/README.md for the drop-in contract."""
        import os
        name = os.environ.get("LLM_RPG_TILESET")
        if name is None:
            try:
                import config
                name = getattr(config, "TILESET_NAME", None)
            except Exception:
                name = None
        if not name:
            return None
        root = os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))),
            "data", "tiles", name)
        return root if os.path.isdir(root) else None

    def _from_tileset(self, relname: str):
        """Load + scale one tileset image; None if absent/broken —
        the procedural sprite is the graceful fallback."""
        if self.tileset_dir is None:
            return None
        import os
        path = os.path.join(self.tileset_dir, relname + ".png")
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path)
            return pygame.transform.scale(
                img, (self.tile_size, self.tile_size))
        except Exception:
            return None

    # ------------------------------------------------------------------ tiles
    def tile(self, terrain_name: str) -> pygame.Surface:
        if terrain_name in self._tile_cache:
            return self._tile_cache[terrain_name]
        loaded = self._from_tileset(terrain_name)
        if loaded is not None:
            self._tile_cache[terrain_name] = loaded
            return loaded
        surf = pygame.Surface((self.tile_size, self.tile_size))
        ts = self.tile_size
        if terrain_name == "bridge":
            surf.fill(PALETTE["water"])
            plank_h = max(2, ts // 6)
            for i in range(0, ts, plank_h + 1):
                pygame.draw.rect(
                    surf, PALETTE["bridge"],
                    (0, i, ts, plank_h))
                pygame.draw.line(
                    surf, PALETTE["bridge2"],
                    (0, i + plank_h - 1), (ts, i + plank_h - 1))
            self._tile_cache[terrain_name] = surf
            return surf
        if terrain_name == "grass":
            surf.fill(PALETTE["grass"])
            self._dither(surf, PALETTE["grass2"], 0.25)
        elif terrain_name == "rubble":
            surf.fill(PALETTE["rubble"])
            for _ in range(5):
                px = self._rng.randint(2, ts - 8)
                py = self._rng.randint(2, ts - 8)
                pygame.draw.circle(surf, PALETTE["rubble2"],
                                   (px, py), self._rng.randint(2, 4))
        elif terrain_name == "scorched":
            surf.fill(PALETTE["scorched"])
            for _ in range(3):
                px = self._rng.randint(2, ts - 6)
                py = self._rng.randint(2, ts - 6)
                pygame.draw.line(surf, (25, 20, 18),
                                 (px, py), (px + 4, py + 2), 2)
        elif terrain_name == "farmland":
            surf.fill(PALETTE["farmland"])
            for row in range(3, ts, max(3, ts // 5)):
                pygame.draw.line(surf, PALETTE["farmland2"],
                                 (1, row), (ts - 2, row), 2)
        elif terrain_name == "swamp":
            surf.fill(PALETTE["swamp"])
            self._dither(surf, PALETTE["swamp2"], 0.35)
            for _ in range(2):
                px = self._rng.randint(2, ts - 8)
                py = self._rng.randint(2, ts - 6)
                pygame.draw.ellipse(surf, PALETTE["swamp_pool"],
                                    (px, py, 7, 4))
        elif terrain_name == "forest":
            surf.fill(PALETTE["grass"])
            for _ in range(3):
                px = self._rng.randint(2, ts - 6)
                py = self._rng.randint(2, ts - 6)
                pygame.draw.circle(surf, PALETTE["forest"],
                                   (px + 2, py + 2), max(3, ts // 6))
                pygame.draw.rect(surf, PALETTE["building2"],
                                 (px + 1, py + ts // 4,
                                  2, max(2, ts // 5)))
        elif terrain_name == "mountain":
            surf.fill(PALETTE["mountain"])
            pygame.draw.polygon(surf, PALETTE["mountain2"], [
                (0, ts), (ts // 2, 2), (ts, ts),
            ])
            pygame.draw.polygon(surf, (240, 240, 245), [
                (ts // 2 - 2, 6), (ts // 2, 2), (ts // 2 + 3, 7),
            ])
        elif terrain_name == "water":
            surf.fill(PALETTE["water"])
            for y in range(0, ts, max(2, ts // 8)):
                pygame.draw.line(surf, PALETTE["water2"],
                                 (0, y), (ts, y), 1)
        elif terrain_name == "road":
            surf.fill(PALETTE["road"])
            self._dither(surf, PALETTE["building2"], 0.2)
        elif terrain_name == "building":
            surf.fill(PALETTE["building"])
            pygame.draw.rect(surf, PALETTE["building2"],
                             (0, 0, ts, ts), 2)
            pygame.draw.rect(surf, (210, 180, 60),
                             (ts // 3, ts // 2,
                              max(2, ts // 3), max(2, ts // 3)))
        elif terrain_name == "cave":
            surf.fill(PALETTE["mountain"])
            pygame.draw.circle(surf, PALETTE["cave"],
                               (ts // 2, ts // 2), ts // 3)
        elif terrain_name == "shrine":
            surf.fill(PALETTE["grass"])
            pygame.draw.circle(surf, PALETTE["shrine_glow"],
                               (ts // 2, ts // 2), ts // 3)
            pygame.draw.rect(surf, PALETTE["shrine"],
                             (ts // 3, ts // 4,
                              ts // 3, ts // 2))
        else:  # default fallback
            surf.fill((50, 50, 50))
        self._tile_cache[terrain_name] = surf
        return surf

    # ----------------------------------------------------------- character
    def character(self, klass: str, is_player: bool = False,
                  is_hostile: bool = False) -> pygame.Surface:
        key = f"char:{klass}:{is_player}:{is_hostile}"
        if key in self._char_cache:
            return self._char_cache[key]
        loaded = self._from_tileset(
            "entities/player" if is_player else f"entities/{klass}")
        if loaded is not None:
            self._char_cache[key] = loaded
            return loaded
        ts = self.tile_size
        surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
        cx, cy = ts // 2, ts // 2

        body_color = (
            (200, 60, 60) if is_hostile else
            (60, 100, 200) if is_player else
            (180, 160, 100)
        )
        if klass in ("wizard", "sorcerer", "warlock"):
            body_color = PALETTE["robe"]
        elif klass in ("warrior", "guard", "paladin", "warriior"):
            body_color = PALETTE["armor"]
        elif klass in ("rogue", "ranger"):
            body_color = PALETTE["leather"]
        elif klass == "merchant":
            body_color = (160, 140, 60)
        elif klass == "bard":
            body_color = (160, 80, 130)
        elif klass == "cleric":
            body_color = (220, 220, 220)
        elif klass in ("troll", "monster", "brigand"):
            body_color = (90, 130, 70)

        # Shadow
        shadow = pygame.Surface((ts, ts // 4), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90),
                            shadow.get_rect())
        surf.blit(shadow, (0, ts - ts // 4))

        # Body
        body_w = ts // 2
        body_h = ts // 2
        pygame.draw.rect(surf, body_color,
                         (cx - body_w // 2, cy - 1,
                          body_w, body_h), border_radius=3)
        # Head
        pygame.draw.circle(surf, PALETTE["skin"],
                           (cx, cy - body_h // 2 - 2), ts // 6)
        # Outline
        pygame.draw.rect(surf, PALETTE["outline"],
                         (cx - body_w // 2, cy - 1,
                          body_w, body_h), 1, border_radius=3)
        pygame.draw.circle(surf, PALETTE["outline"],
                           (cx, cy - body_h // 2 - 2), ts // 6, 1)

        if is_player:
            # Star marker
            pygame.draw.circle(surf, PALETTE["gold"],
                               (cx + body_w // 2, cy - body_h // 2 - 4), 2)
        self._char_cache[key] = surf
        return surf

    # ------------------------------------------------------------ furniture
    def furniture(self, name: str) -> pygame.Surface:
        """Recognizable procedural sprites for interior pieces (P9A.3b)."""
        key = f"furn:{name.lower()}"
        if key in self._tile_cache:
            return self._tile_cache[key]
        ts = self.tile_size
        surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
        low = name.lower()
        wood = PALETTE["building"]
        dark = PALETTE["building2"]
        if "bed" in low:
            pygame.draw.rect(surf, dark, (3, ts // 3, ts - 6,
                                          ts // 2), border_radius=3)
            pygame.draw.rect(surf, (200, 200, 210),
                             (5, ts // 3 + 2, ts // 3, ts // 2 - 4),
                             border_radius=2)            # pillow
            pygame.draw.rect(surf, (150, 40, 40),
                             (5 + ts // 3, ts // 3 + 2,
                              ts - 12 - ts // 3, ts // 2 - 4))  # blanket
        elif "chest" in low or "crate" in low:
            pygame.draw.rect(surf, wood, (4, ts // 3, ts - 8,
                                          ts // 2), border_radius=2)
            pygame.draw.line(surf, dark, (4, ts // 2),
                             (ts - 4, ts // 2), 2)
            pygame.draw.rect(surf, PALETTE["gold"],
                             (ts // 2 - 2, ts // 2 - 2, 4, 5))  # clasp
        elif "hearth" in low or "fire" in low:
            pygame.draw.rect(surf, PALETTE["mountain"],
                             (3, ts // 4, ts - 6, ts // 2 + 4))
            pygame.draw.polygon(surf, (240, 140, 40), [
                (ts // 2 - 5, ts // 2 + 6), (ts // 2, ts // 3),
                (ts // 2 + 5, ts // 2 + 6)])                # flame
            pygame.draw.polygon(surf, (255, 220, 90), [
                (ts // 2 - 2, ts // 2 + 5), (ts // 2, ts // 2 - 2),
                (ts // 2 + 2, ts // 2 + 5)])
        elif "anvil" in low:
            pygame.draw.rect(surf, (70, 70, 80),
                             (ts // 4, ts // 2, ts // 2, 4))
            pygame.draw.rect(surf, (100, 100, 112),
                             (ts // 4 - 3, ts // 3 + 2, ts // 2 + 6, 6))
        elif "altar" in low:
            pygame.draw.rect(surf, (200, 195, 170),
                             (ts // 4, ts // 3, ts // 2, ts // 2 - 2))
            pygame.draw.circle(surf, PALETTE["shrine_glow"],
                               (ts // 2, ts // 3), 4)      # candle glow
        elif "shel" in low or "book" in low:
            pygame.draw.rect(surf, wood, (3, 4, ts - 6, ts - 10))
            for row in range(8, ts - 8, 7):
                for bx in range(6, ts - 8, 5):
                    color = ((150, 60, 50), (60, 90, 140),
                             (170, 140, 60))[(bx + row) % 3]
                    pygame.draw.rect(surf, color, (bx, row, 3, 5))
        elif "barrel" in low:
            pygame.draw.ellipse(surf, wood, (ts // 4, ts // 4,
                                             ts // 2, ts // 2 + 4))
            pygame.draw.line(surf, dark, (ts // 4, ts // 2),
                             (3 * ts // 4, ts // 2), 2)
        elif "table" in low or "counter" in low or "bar" == low or \
                "workbench" in low:
            pygame.draw.rect(surf, wood, (4, ts // 3, ts - 8, 5))
            pygame.draw.rect(surf, dark, (6, ts // 3 + 5, 3, ts // 3))
            pygame.draw.rect(surf, dark, (ts - 9, ts // 3 + 5, 3,
                                          ts // 3))
        elif "stairs" in low:
            for i, step in enumerate(range(4, ts - 4, 5)):
                pygame.draw.rect(surf, (140 - i * 12,) * 3,
                                 (step, ts - 8 - i * 5, ts - step - 4, 4))
        elif "pew" in low or "chair" in low:
            pygame.draw.rect(surf, wood, (6, ts // 2, ts - 12, 4))
            pygame.draw.rect(surf, wood, (6, ts // 4, 3, ts // 2))
        elif "sigil" in low:
            pygame.draw.circle(surf, (90, 60, 160),
                               (ts // 2, ts // 2), ts // 3, 2)
            pygame.draw.circle(surf, (150, 110, 230),
                               (ts // 2, ts // 2), ts // 6, 2)
            for ang in range(0, 360, 90):
                import math as _m
                px2 = ts // 2 + int((ts // 3) *
                                    _m.cos(_m.radians(ang)))
                py2 = ts // 2 + int((ts // 3) *
                                    _m.sin(_m.radians(ang)))
                pygame.draw.circle(surf, (170, 140, 255),
                                   (px2, py2), 2)
        elif "inscription" in low:
            pygame.draw.rect(surf, (150, 148, 140),
                             (ts // 4, ts // 4, ts // 2, ts // 2))
            for row in range(ts // 4 + 3, 3 * ts // 4 - 2, 4):
                pygame.draw.line(surf, (90, 88, 84),
                                 (ts // 4 + 3, row),
                                 (3 * ts // 4 - 3, row), 1)
        elif "statue" in low:
            pygame.draw.rect(surf, (170, 170, 180),
                             (ts // 3, ts // 4, ts // 3, ts // 2))
            pygame.draw.circle(surf, (190, 190, 200),
                               (ts // 2, ts // 4), ts // 8)
        else:
            return self.item(name)
        self._tile_cache[key] = surf
        return surf

    # ---------------------------------------------------------------- items
    def item(self, name: str) -> pygame.Surface:
        ts = self.tile_size
        surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
        cx, cy = ts // 2, ts // 2
        name = name.lower()
        if "potion" in name or "ale" in name or "mead" in name:
            pygame.draw.rect(surf, PALETTE["potion"],
                             (cx - 4, cy - 6, 8, 12), border_radius=2)
            pygame.draw.rect(surf, PALETTE["outline"],
                             (cx - 4, cy - 6, 8, 12), 1, border_radius=2)
        elif "sword" in name or "dagger" in name or "blade" in name:
            pygame.draw.line(surf, (200, 200, 220),
                             (cx, cy + 6), (cx, cy - 6), 2)
            pygame.draw.line(surf, PALETTE["leather"],
                             (cx - 3, cy + 4), (cx + 3, cy + 4), 2)
        elif "gold" in name or "coin" in name:
            pygame.draw.circle(surf, PALETTE["gold"], (cx, cy), 4)
            pygame.draw.circle(surf, PALETTE["outline"], (cx, cy), 4, 1)
        else:
            pygame.draw.rect(surf, (180, 140, 80),
                             (cx - 4, cy - 4, 8, 8), border_radius=2)
            pygame.draw.rect(surf, PALETTE["outline"],
                             (cx - 4, cy - 4, 8, 8), 1, border_radius=2)
        return surf

    # ----------------------------------------------------------- helpers
    def _dither(self, surf, color, prob: float) -> None:
        for y in range(0, self.tile_size, 2):
            for x in range(0, self.tile_size, 2):
                if self._rng.random() < prob:
                    surf.set_at((x, y), color)
