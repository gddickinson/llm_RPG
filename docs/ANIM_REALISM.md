# ANIM_REALISM.md — realism upgrades for character animation & graphics

George: "keep improving the realism of character animation and graphics, both 2D
and iso — in rounds of upgrades." A companion to `docs/ISO_GRAPHICS.md` (which
covered ISO.1-16 + COMBAT.1-2). Build in tested rounds on `v2-development`, render
a before/after to `scratchpad/anim/`, keep the suite green, commit each round.

## Audit (rendered current output, 2026-07-17)

- **2D (top-down)** — competent but **FLAT**: every limb/torso is one solid colour
  (`body_parts._limb` = a single line + a circle cap), the head is oversized
  (chibi-ish), robes/cloaks are flat rectangles, and some weapons read oddly (the
  staff's orb floats detached). No form/volume — limbs don't read as rounded.
- **Iso** — proper 3D form (raster3d Lambert-shaded baked meshes, clearly better),
  but **matte + dim**: soft single-light shading, low contrast, dark figures,
  minimal faces, blocky tapered limbs.
- **Both** — worth checking the walk for foot SLIDING (feet skating vs planting).

The iso already out-realisms the 2D; the biggest single win is giving the 2D FORM.

## Principle

Cheap, procedural, headless-testable, cached. No new assets. Every draw stays
pure/thin; files under 500 lines; both render paths (top-down + iso) improve
together where a change is shared (pose math, foot IK), or per-path where it's
drawing (2D shading vs iso shading).

## Rounds

- **R1 — 2D form shading. ✅ DONE.** `body_parts` limbs are shaded CYLINDERS (dark
  underside, lit core shifted toward a top-left key light, highlight stripe), the
  torso has lit/shadow flanks, the head is a shaded SPHERE (highlight + terminator
  crescent + rim) with a hair sheen. Limbs read round, not flat sticks.
- **R2 — Iso shading richness. ✅ DONE.** `ui/raster3d.render` gains AMBIENT
  OCCLUSION (down-facing undersides sink to shadow), a white RIM kicker on the
  silhouette edge, and more key contrast (0.22 ambient / 0.74 key vs 0.30/0.55) —
  the baked figures + buildings gain form and pop instead of reading dim + matte.
- **R3 — Foot planting. ~ MOSTLY SOLVED.** Measured: the stance foot already holds
  roughly constant while the swing foot moves (~1.5px/frame residual over a 64px
  tile) — the `char_tween.move_phase` tied to ground speed already plants feet.
  Only a minor residual slide remains; low priority. *(deferred)*
- **R4 — Weapons & gear fidelity. ✅ DONE.** (Head size KEPT.) 2D weapons read as
  shaded metal — a lit blade edge over a shadowed spine, a grip + gold pommel on a
  sword, lit rims on axe/spear/mace heads; the staff's orb is now a glowing BEAD
  (aura → bright core), not a flat floating dot. `body_parts.draw_weapon`.
- **R5 — Cloth volume (2D). ✅ DONE.** Robed classes (`ROBE_CLASSES` — wizard/
  cleric/druid/…) wear a flared, folded, shaded SKIRT (`body_parts.draw_robe`) that
  hangs over the legs and sways with the feet — they read as mages/priests, not
  stick-legs. **R5b iso robes ✅** — the iso kit gains a `robed` flag and
  `iso_skeleton._robe_mesh` adds a flared SKIRT frustum (a cone widening downward)
  for robed classes, so the iso wizard/cleric/druid wear a gown too (parity).
- **R6 — Ground shadows & grounding.** A directional, pose-shaped contact shadow
  (2D), and stronger contact shadows/occlusion where a figure meets the ground.

Order = impact-first. R1 & R2 (shading) are the biggest realism-per-line; R3 (foot
plant) is the biggest animation-realism win. R4-R6 refine.

## Verify each round

Render a before/after montage (classes × idle/walk/attack, both facings, 2D + iso)
to `scratchpad/anim/`, eyeball it, and add a headless test asserting the draw is
non-empty + (where measurable) that shading VARIES across a part (form, not flat).
