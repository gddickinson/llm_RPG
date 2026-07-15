"""P34.17 injury & state animation modifiers (pure).

The body should SHOW its condition: a leg wound makes the walk LIMP, an arm wound
lets that arm hang limp, and an unconscious / dying / KO'd character lies DOWNED
instead of standing. `injury_state` reads the wound/dying state off `metadata`
(what `wounds.py` / `dying.py` write) and `apply_*` bend the finished screen pose.
Headless-testable; `body_renderer` calls in.
"""

import math


def _sev(char, part):
    md = getattr(char, "metadata", None) or {}
    return int((md.get("wounds", {}) or {}).get(part, 0))


def injury_state(char):
    """{down, limp 0-1, arm 'l'/'r'/None} from the character's condition."""
    md = getattr(char, "metadata", None) or {}
    down = bool(md.get("dying", 0)) or bool(md.get("unconscious")) or \
        bool(md.get("ko"))
    legs = _sev(char, "legs")
    la, ra = _sev(char, "left_arm"), _sev(char, "right_arm")
    arm = "r" if (ra and ra >= la) else "l" if la else None
    return {"down": down, "limp": min(1.0, legs / 3.0), "arm": arm}


def apply_limp(pose, walk, H, amount):
    """A hitch in the stride — the body DIPS onto the good leg each step and the
    stiff leg drags (P34.17). Mutates the screen pose."""
    if amount <= 0:
        return pose
    hitch = amount * H * 0.06 * max(0.0, math.sin(walk))
    for k in ("chest", "neck", "head", "l_sh", "r_sh", "l_hip", "r_hip",
              "l_elbow", "r_elbow", "l_hand", "r_hand"):
        if k in pose:
            x, y = pose[k]
            pose[k] = (x, y + hitch)
    if "l_foot" in pose and "l_knee" in pose:      # the stiff leg barely lifts
        fx, fy = pose["l_foot"]
        kx, _ky = pose["l_knee"]
        pose["l_foot"] = ((fx + kx) / 2.0, fy)
    return pose


def apply_arm(pose, side, H):
    """The injured arm hangs LIMP (no swing) close to the body."""
    if not side:
        return pose
    sh, el, ha = side + "_sh", side + "_elbow", side + "_hand"
    if sh in pose:
        sx, sy = pose[sh]
        pose[ha] = (sx, sy + H * 0.22)
        pose[el] = (sx, sy + H * 0.11)
    return pose
