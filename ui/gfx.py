"""P40.1 the gfx foundation — reusable procedural-sprite primitives.

The world's procedural sprites read low-res because they're drawn FLAT (2–3
tone dither), SPARSE, and at NATIVE tile size (so curves/diagonals alias and
sub-pixel detail is impossible). The cure — validated by the P40.0 PoC and
already used for CHARACTERS (`body_renderer.draw_body_crisp`) — is to build
each sprite at `size × SS`, draw far MORE layered detail, then
`smoothscale` down: the downscale anti-aliases everything and preserves
sub-pixel detail, and the result is CACHED so per-frame cost is unchanged.

This module holds the pure/thin primitives that make a sprite a STACK of
layers: a gradient base, multi-tone mottle, dense detail (the caller's), a
directional light, a contact shadow, an outline. All headless-testable
(build a Surface, assert its shape) — no display required. Callers cache.
"""

import math
import os
import random

# Oversample factor. Env `LLM_RPG_SS` overrides; else the caller passes a
# default (the renderer picks 3 when "Smooth sprites" is on, 1 when off).
_SS_MIN, _SS_MAX = 1, 4


def ss_factor(default: int = 3) -> int:
    """The supersample factor to build at: `LLM_RPG_SS` env, else `default`,
    clamped to [1, 4]. 1 = off (native size, no oversampling)."""
    env = os.environ.get("LLM_RPG_SS")
    if env is not None:
        try:
            return max(_SS_MIN, min(_SS_MAX, int(env)))
        except ValueError:
            pass
    return max(_SS_MIN, min(_SS_MAX, int(default)))


def apply_ssaa_setting(engine) -> None:
    """P34.7/P40.2: the "Smooth sprites" setting drives BOTH the character
    beauty pass (`body_renderer.SSAA_SCALE`) and the terrain oversample
    (`tile_variants.SSAA`). `LLM_RPG_SS` overrides the terrain factor. Called
    once per frame from the renderer (cheap; the sprites themselves cache)."""
    from engine import settings
    from ui import body_renderer as _br
    from ui import tile_variants as _tv
    smooth = settings.enabled(engine.player, "smooth")
    _br.SSAA_SCALE = 2 if smooth else 1
    _tv.SSAA = ss_factor(3 if smooth else 1)


def supersample(build_fn, size: int, ss=None):
    """Render `build_fn(S)` at S = size·ss, then smoothscale to (size, size)
    so every curve/edge is anti-aliased. ss<=1 builds at native size.

    Defensive: `smoothscale` needs a 24/32-bit source and misbehaves (can
    render BLACK) on some display formats. We force a 32-bit source and fall
    back to plain `scale` if smoothscale ever raises, so a tile never comes
    out black on an odd display (George 2026-07-15)."""
    import pygame
    ss = ss_factor() if ss is None else max(1, int(ss))
    if ss <= 1:
        return build_fn(size)
    big = build_fn(size * ss)
    if big.get_bitsize() < 24:                 # 8/16-bit → smoothscale-unsafe
        try:
            big = big.convert_alpha()
        except pygame.error:
            pass
    try:
        return pygame.transform.smoothscale(big, (size, size))
    except (ValueError, pygame.error):
        return pygame.transform.scale(big, (size, size))


# ---- colour helpers ---------------------------------------------------

def lerp_rgb(a, b, t: float):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale_rgb(c, f: float):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def shade_ramp(base, n: int = 5, lo: float = 0.72, hi: float = 1.24):
    """`n` tones of `base` from lo× (shadow) to hi× (highlight) — a proper
    light→dark ramp instead of a flat fill."""
    if n <= 1:
        return [tuple(base)]
    return [scale_rgb(base, lo + (hi - lo) * (i / (n - 1))) for i in range(n)]


# ---- layer builders ---------------------------------------------------

def vgradient(size: int, top, bottom):
    """A vertical top→bottom gradient Surface (cheap row fills). Explicitly
    32-bit SRCALPHA (opaque fills) — NOT a bare `Surface` that would inherit
    the display's format, which can make `smoothscale` render BLACK on some
    displays (George 2026-07-15: "the ground tiles are still mainly black").
    The working character path (`draw_body_crisp`) uses SRCALPHA for the same
    reason."""
    import pygame
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    denom = max(1, size - 1)
    for y in range(size):
        r, g, b = lerp_rgb(top, bottom, y / denom)
        surf.fill((r, g, b, 255), (0, y, size, 1))
    return surf


def _upscaled(small_build, size: int, small: int = 20):
    """Build a soft field at low res then smoothscale up — a cheap way to get
    a smooth radial/diagonal falloff without a per-pixel pass at full size."""
    import pygame
    s = max(2, min(small, size))
    return pygame.transform.smoothscale(small_build(s), (size, size))


def rgradient(size: int, inner, outer, center=None):
    """A radial inner→outer gradient (opaque). Built small then upscaled."""
    import pygame

    def _b(s):
        surf = pygame.Surface((s, s), pygame.SRCALPHA)   # 32-bit (smoothscale-safe)
        cx, cy = center or (s / 2, s / 2)
        maxd = math.hypot(max(cx, s - cx), max(cy, s - cy)) or 1
        for y in range(s):
            for x in range(s):
                t = math.hypot(x - cx, y - cy) / maxd
                surf.set_at((x, y), (*lerp_rgb(inner, outer, t), 255))
        return surf
    return _upscaled(_b, size)


def mottle(surf, tones, seed: int, density: float = 0.55, blob=None):
    """Scatter soft translucent blobs of `tones` over `surf` — the multi-tone
    texture layer. `density` ≈ the fraction of area the blobs cover."""
    import pygame
    S = surf.get_width()
    r = random.Random(seed)
    blob = blob or max(1, S // 8)
    per = math.pi * (blob * 0.6) ** 2
    n = max(1, int(S * S * density / max(1.0, per)))
    layer = pygame.Surface((S, S), pygame.SRCALPHA)
    for _ in range(n):
        x, y = r.randint(0, S - 1), r.randint(0, S - 1)
        rad = r.randint(max(1, blob // 2), blob)
        col = tones[r.randint(0, len(tones) - 1)]
        pygame.draw.circle(layer, (*col, r.randint(38, 105)), (x, y), rad)
    surf.blit(layer, (0, 0))
    return surf


def directional_light(size: int, strength: int = 34):
    """A soft top-left HIGHLIGHT + bottom-right SHADOW overlay (SRCALPHA), so
    a flat tile gains a consistent light direction. Built small, upscaled."""
    import pygame

    def _b(s):
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        denom = 2 * max(1, s - 1)
        for y in range(s):
            for x in range(s):
                t = (x + y) / denom                 # 0 at TL … 1 at BR
                if t < 0.5:
                    surf.set_at((x, y), (255, 255, 255, int(strength * (0.5 - t) * 2)))
                else:
                    surf.set_at((x, y), (0, 0, 0, int(strength * (t - 0.5) * 2)))
        return surf
    return _upscaled(_b, size)


def soft_shadow(size: int, alpha: int = 120):
    """A soft radial dark blob (SRCALPHA) to GROUND a prop/building/character
    (Phase 2). Built small then upscaled for a smooth falloff."""
    import pygame

    def _b(s):
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = s / 2
        maxd = (s / 2) or 1
        for y in range(s):
            for x in range(s):
                t = min(1.0, math.hypot(x - cx, y - cy) / maxd)
                surf.set_at((x, y), (0, 0, 0, int(alpha * (1 - t) ** 2)))
        return surf
    return _upscaled(_b, size)


def contact_shadow(size: int, w_frac: float = 0.7, h_frac: float = 0.2,
                   y_frac: float = 0.8, alpha: int = 115):
    """A soft elliptical shadow near the bottom-centre of a size×size tile — to
    GROUND a prop/scatter piece that would otherwise float. SRCALPHA; built
    from concentric fading ellipses then upscaled for a soft edge."""
    import pygame

    def _b(s):
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        ew, eh = max(2, int(s * w_frac)), max(1, int(s * h_frac))
        ecx, ecy = s / 2, s * y_frac
        rings = 5
        for i in range(rings, 0, -1):
            f = i / rings                       # 1 = outer/faint … small = dark
            a = min(255, int(alpha * (1 - f) ** 1.1) + 8)
            rw, rh = ew * f, eh * f
            pygame.draw.ellipse(surf, (0, 0, 0, a),
                                (ecx - rw / 2, ecy - rh / 2, rw, rh))
        return surf
    return _upscaled(_b, size, small=24)


def outline(surf, color=(0, 0, 0), alpha: int = 90):
    """Return a copy of `surf` with a soft darker rim around its opaque mass
    (Phase 2/3) — so an object pops from the ground. Needs SRCALPHA input."""
    import pygame
    S = surf.get_width()
    try:
        mask = pygame.mask.from_surface(surf)
    except Exception:
        return surf
    edge = pygame.Surface((S, S), pygame.SRCALPHA)
    outline_pts = mask.outline()
    if len(outline_pts) >= 2:
        pygame.draw.lines(edge, (*color, alpha), True, outline_pts, max(1, S // 24))
    out = edge
    out.blit(surf, (0, 0))
    return out
