"""P34.18 creature BODY PLANS (pure) — not every monster is a biped.

`body_plan(char)` classifies a character into a body plan (quadruped / slime / wisp
/ humanoid) from its species; the pose builders return SCREEN points for
`creature_render` to draw. Quadrupeds use the same depth projection as the humanoid
puppet (nose→tail is the fore-aft DEPTH axis) so a beast turns to face any heading
and its legs stride. Humanoids (goblins, trolls, orcs, skeletons, bandits) stay on
the jointed puppet — this only re-bodies the genuinely non-human creatures.
"""

import math

_QUAD = ("wolf", "fox", "boar", "bear", "cat", "hound", "dog", "deer", "stag",
         "rabbit", "hare", "lion", "wildcat", "direwolf", "warg", "hog", "ram",
         "goat", "wolfhound", "panther", "lynx", "mare", "pony", "mule", "horse",
         "dragon", "drake", "wyrm", "lizard", "croc", "basilisk",
         "sheep", "mouflon", "mustang", "aurochs", "razorback", "bull", "ox",
         "cattle", "cow", "donkey", "husky", "shark")   # big beasts too
_SLIME = ("slime", "ooze", "jelly", "blob", "pudding", "gel")
_WISP = ("wisp", "spirit", "will-o", "ghost", "wraith", "flame", "ember", "spark")
_AVIAN = ("bird", "bat", "raven", "crow", "hawk", "eagle", "owl", "harpy",
          "pheasant", "vulture", "wyvern", "imp")
_ARACHNID = ("spider", "scorpion", "arachnid")
# only re-body genuine beasts — NPCs, the player and humanoid monsters stay puppets
_BEAST_CLASSES = ("monster", "animal", "beast")


def body_plan(char):
    """quadruped / slime / wisp / humanoid — from an explicit metadata hint, else
    the creature's name keywords, but ONLY for beast-class creatures (a villager
    named 'Will' must never become a wisp)."""
    md = getattr(char, "metadata", None) or {}
    if md.get("body_plan"):
        return md["body_plan"]
    klass = getattr(getattr(char, "character_class", None), "value", "")
    if klass not in _BEAST_CLASSES:
        return "humanoid"
    # #9 a creature pointing at an animal GLB model draws that baked model, so
    # give it a non-humanoid plan (→ creature_render dispatch, model or fallback)
    if md.get("model"):
        return "quadruped"
    name = ((getattr(char, "name", "") or "") + " " +
            str(getattr(char, "id", ""))).lower()
    for kws, plan in ((_AVIAN, "avian"), (_ARACHNID, "arachnid"),
                      (_QUAD, "quadruped"), (_SLIME, "slime"), (_WISP, "wisp")):
        if any(k in name for k in kws):
            return plan
    return "humanoid"


# diagonal gait: front-left + back-right swing together, front-right + back-left
_LEGS = {"fl": (-0.16, 0.26, 0.0), "fr": (0.16, 0.26, math.pi),
         "bl": (-0.16, -0.26, math.pi), "br": (0.16, -0.26, 0.0)}


def quadruped_points(cx, foot_y, size, walk, facing_deg, moving=True, cfg=None,
                     attack=0.0, hurt=0.0):
    """Screen points for a four-legged beast at facing `facing_deg`. Body coords
    are (u across the width, w nose↔tail DEPTH, y height); the fore-aft stride
    projects to a leg-lift head-on and a full stride in profile. `attack` lunges
    the beast forward (a pounce/bite), `hurt` recoils it back (P34.24)."""
    cfg = cfg or {}
    th = math.radians(facing_deg)
    c, s = math.cos(th), math.sin(th)
    # a forward LUNGE on the strike, a backward RECOIL when hit — along the nose axis
    fore = (math.sin(min(1.0, attack) * math.pi) * 0.22
            - math.sin(min(1.0, hurt) * math.pi) * 0.16)

    def proj(u, w, y):
        return (cx + (u * c + (w + fore) * s) * size, foot_y - y * size)

    sw = math.sin(walk)
    stride = 0.16 if moving else 0.0
    bob = -abs(sw) * 0.02 if moving else math.sin(walk * 0.3) * 0.006
    bh = cfg.get("height", 0.42) + bob                 # body height off the ground
    snout = cfg.get("snout", 0.80)
    p = {"size": size, "cos": c}
    p["shoulder"] = proj(0.0, 0.32, bh + 0.05)
    p["hip"] = proj(0.0, -0.34, bh + 0.03)
    p["head"] = proj(0.0, 0.55, bh + 0.15)
    p["snout"] = proj(0.0, snout, bh + 0.06)
    p["ear1"] = proj(-0.05, 0.50, bh + 0.30)
    p["ear2"] = proj(0.05, 0.50, bh + 0.30)
    p["tail_root"] = proj(0.0, -0.55, bh + 0.10)
    p["tail_tip"] = proj(0.0, -0.80, bh + 0.16 + sw * 0.05)   # sways / wags
    legs = {}
    for name, (u, w0, ph) in _LEGS.items():
        step = math.sin(walk + ph) * stride
        lift = max(0.0, math.sin(walk + ph)) * 0.07
        hip = proj(u, w0, bh)
        foot = proj(u, w0 + step, lift)
        depth = -u * s + w0 * c                         # + = nearer the camera
        legs[name] = (hip, foot, depth)
    p["legs"] = legs
    return p
