"""P37.3 — gate & portcullis geometry (pure, headless-testable).

A SHUT town/castle gate should READ as a barred gateway — a stone arch with an
iron PORTCULLIS grille — not a blank wall (George: "make doors to castles look
like locked doors / gates / portcullises when closed, not walls"). `portcullis`
returns the rects/segments a thin `renderer_buildings` pass draws over a closed
gate tile; `_LOCKED_BAR` tints it red when the gate is barred by an alarm.

All coordinates are absolute screen pixels derived from the block's front face
(the rectangle (px, py+ts-h)..(px+ts, py+ts)), so the draw side stays trivial.
"""

# palette
STONE = (122, 118, 110)          # the gate's stone jambs + lintel
STONE_DARK = (78, 74, 68)        # the mortar lines / lintel edge
OPENING = (26, 24, 28)           # the dark recess behind the grille
IRON = (72, 74, 84)              # the portcullis bars
IRON_HI = (104, 108, 120)        # a lit edge on the bars
LOCKED_IRON = (120, 60, 54)      # a barred (alarm-locked) gate glows iron-red


def portcullis(px, py, ts, h):
    """Geometry for a shut gate whose block front face is the rectangle
    (px, py+ts-h)..(px+ts, py+ts). Returns a dict:
      frame:   {left,right,lintel} stone rects (x, y, w, h)
      opening: the recessed dark rect (x, y, w, h)
      bars_v:  vertical bar segments [((x, y0), (x, y1)), ...]
      bars_h:  horizontal cross-bar segments
    Deterministic; every value an int."""
    fy0 = py + ts - h                       # top of the front face
    fy1 = py + ts                           # ground line
    fh = max(3, fy1 - fy0)
    jamb = max(1, ts // 8)                  # slim stone jamb each side
    arch = max(1, fh // 8)                  # thin stone lintel — the archway
    ox = px + jamb                          #   opening dominates the face
    ow = max(1, ts - 2 * jamb)
    oy = fy0 + arch
    oh = max(1, fy1 - oy)
    opening = (ox, oy, ow, oh)

    n_v = max(2, ow // max(2, ts // 6))     # vertical iron bars
    bars_v = []
    for i in range(1, n_v):
        bx = ox + round(ow * i / n_v)
        bars_v.append(((bx, oy), (bx, fy1)))

    n_h = max(1, oh // max(2, ts // 4))     # horizontal cross-bars
    bars_h = []
    for j in range(1, n_h + 1):
        by = oy + round(oh * j / (n_h + 1))
        bars_h.append(((ox, by), (ox + ow, by)))

    frame = {"left": (px, fy0, jamb, fh),
             "right": (px + ts - jamb, fy0, jamb, fh),
             "lintel": (px, fy0, ts, arch)}
    return {"frame": frame, "opening": opening,
            "bars_v": bars_v, "bars_h": bars_h}
