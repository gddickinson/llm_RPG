"""Continuous tile-to-tile MOTION helpers (shared by the top-down + iso renderers).

A turn-based step teleports a character between tiles; the renderer SLIDES the
sprite across so the walk reads as motion. But an NPC steps on a slow world
cadence (~every `config.NPC_IDLE_INTERVAL` s while the player idles), so a fixed
short slide DARTS then freezes — the jerky stop/start George reported. Instead an
NPC's slide STRETCHES to fill the measured gap since its last step, so ambient
motion GLIDES tile-to-tile continuously; the player keeps a crisp fixed step so
input stays responsive. The stride cycles in proportion to ground speed so the
legs don't shuffle fast over a slow glide. Pure over the char's `_anim` dict.
"""

import math

TWEEN_DUR = 0.16           # the player's crisp step (seconds to slide one tile)
NPC_TWEEN_MAX = 0.85       # cap an NPC's gap-filling slide (a lone step after a
                           # long stand doesn't ooze slowly across a whole tile)
STRIDE_PER_TILE = 0.5      # gait cycles per tile crossed (1 tile ≈ one step)


def start_slide(anim, prev, cur, is_player):
    """Begin a slide from `prev`→`cur`: the player steps crisply, an NPC's slide
    fills the time since its last step (clamped) so a slow-cadence walk glides."""
    anim["tween_from"] = (prev[0] - cur[0], prev[1] - cur[1])
    gap = anim.get("since_move", TWEEN_DUR)
    anim["tween_dur"] = TWEEN_DUR if is_player \
        else min(max(gap, TWEEN_DUR), NPC_TWEEN_MAX)
    anim["tween_t"] = anim["tween_dur"]
    anim["since_move"] = 0.0


def advance_slide(anim, dt):
    """Advance the slide + stride a frame. `move_phase` advances with ground speed
    (one tile / tween_dur) so the legs cycle at the pace the body actually glides."""
    dur = anim.get("tween_dur", TWEEN_DUR) or TWEEN_DUR
    anim["move_phase"] = anim.get("move_phase", 0.0) + (dt / dur) * STRIDE_PER_TILE
    anim["walk_phase"] = (anim.get("walk_phase", 0.0)
                          + dt * 20.0 * (TWEEN_DUR / dur)) % math.tau
    anim["tween_t"] = max(0.0, anim.get("tween_t", 0.0) - dt)
