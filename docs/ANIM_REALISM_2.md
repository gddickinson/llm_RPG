# ANIM_REALISM_2.md — the next character-graphics arc (2D + iso)

George: "How can the animations and graphics of the characters, both 2D and iso, be
further improved?" This is the follow-on to `ANIM_REALISM.md` (R1–R6 done: 2D form
shading, iso shading, weapons, cloth, grounding shadows). Audit renders:
`scratchpad/anim/audit_2d.png` + `audit_iso.png` (5 classes × idle/walk/attack).

## Honest read of where it stands

**2D (top-down)** — competent, class-legible, dynamic side-walk, grounded (R6). But:
- The **face reads as two big black voids** — the neutral `char_face` "dot" eyes are
  large, dark, pupil-less; the single most unnatural element. The expression system
  exists (8 `EXPRESSIONS`) but idle stays neutral, so nuance never shows.
- **Front-facing ATTACK ≈ idle** — a strike only reads in the side profile; head-on
  it barely moves. Cast/shoot the same.
- **Idle is a stiff near-T-pose** front-on (weight-shift/breathing are subtle).
- **Limbs end in stubs; feet are identical brown ellipses** — no hands, no boots.
- **Torso is a flat fill** — no armor plates, robe trim, hood, collar, cuffs.

**Iso** — proper 3D form + natural mocap poses (clearly good), but:
- **Dark / murky** — `raster3d` base = `0.22 ambient + 0.74 key + 0.12 fill`; dark
  class colours (leather/plate) sink into a dark ground. Biggest iso weakness.
- **Face is a dark smudge** — no readable eyes/features on the baked head.
- **Attack ≈ idle** in iso too — the strike doesn't read.
- Limbs are smooth tubes (no hands/boots); the bake could be crisper (SSAA).

## Prioritized improvement catalog

Ordered by perceived-quality-per-effort.

### A. Faces & expression (HIGH — both). The #1 realism lever.
- 2D `body_parts.draw_face`: give eyes a sclera + pupil + a 1px catchlight, shrink
  the dark mass, add a nose-shadow tick and a clearer mouth; keep the 3-param spec.
- Drive CONTEXT expressions: grit/grimace in combat, pain at low HP, a smile when
  greeting/social, wide-eyed near a monster (wire `express()` from combat/needs/AI).
- Iso: bake a lighter face patch + eye marks + hair so the head reads even small;
  feed the same expression params into the baked head.

### B. Iso exposure & relight (HIGH — iso). The #1 iso lever.
- Raise `raster3d` ambient (~0.22→0.32) + fill, add a small overall gain and a
  slightly warm key, lift the AO floor — so colours read and the figure separates
  from the dark ground. Optionally a stronger rim kicker.
- Consider a subtle dark OUTLINE on the baked sprite for separation.

### C. Action readability (HIGH — both).
- Make ATTACK read from ANY facing: bigger weapon-arm arc + torso twist + a lunge +
  follow-through + a 1-frame impact "pop". Distinct CAST (channel→thrust) and SHOOT
  (draw→loose) reads. In iso, ensure the mocap swing (or an overlay arc) is visible.

### D. Hands, feet & silhouette (MED — both).
- Simple articulated HANDS (a mitt + thumb hint) and directional BOOTS (toe points
  the facing) instead of stubs/ellipses; a touch of waist taper + shoulder shaping,
  so the silhouette reads unmistakably human.

### E. Gear & cloth detail (MED — both).
- Armor plates/pauldrons (warrior), robe trim + sash + sleeves (casters), a HOOD
  (rogue/ranger), collars/cuffs/belts. Ideally driven by ACTUAL equipped gear
  (helmet kind, cape, shield, pack) rather than the class default.
- Stronger secondary cloth (cloak/hem sway) — `char_flow` exists; push it.

### F. Motion quality (MED — both).
- More baked frames / interpolation for fluid loops; more idle + combat + social
  mocap variety; hair/cloak follow-through more visible.

### G. Ambitious / unifying (LOWER — bigger payoff).
- **Normal-mapped 2D sprites**: bake a normal map from the 3D mesh and light the 2D
  sprite dynamically (day/night, torch/forge) — 2D would react to lighting like the
  world does, and unify the two pipelines.
- **Consistent cel-shaded outline** art direction across both views.
- **Full equipment layering** (visible worn pieces) shared by 2D + iso.

## Proposed rounds ("G-series")

- **G1 — Faces. ✅ DONE.** 2D `draw_face` eyes are now a sclera + iris + a 1px
  catchlight (not a black void) + a subtle nose; `EMOTE_EXPR` drives a fighting
  face on attack/wrestle/throw/taunt and a wince at ≤25% HP. Render `g1_faces.png`.
  Tests: `test_body_renderer.TestFace`.
- **G2 — Iso exposure. ✅ DONE.** `raster3d.render` lifts the ambient floor
  (0.22→0.34), fill (0.12→0.18) and AO floor (0.72→0.82) + a faintly warm rim, so
  the shadow side reads (~0.16→~0.30) and colours pop — the murky figures now
  separate from the dark ground (armor silvers, robes vivid). Render `audit_iso.png`.
- **G3 — Action readability.** Attack/cast/shoot read from any facing, both views.
- **G4 — Hands, feet, silhouette.** Articulated hands + directional boots + shaping.
- **G5 — Gear & cloth.** Armor plates / hoods / capes / robe trim; equipment layering.
- **G6 — (ambitious) Dynamic 2D lighting via baked normal maps.**

G1 + G2 alone transform the read (a face that isn't two black holes; iso figures
that aren't murky). Same discipline as R1–R6: pure/thin, cached, headless-tested,
a before/after render each round, files < 500 lines, suite green + commit per round.
