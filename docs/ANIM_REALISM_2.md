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
- **G3 — Action readability. ✅ DONE (2D).** The unused `char_motion.attack_lunge`
  now drives the whole body FORWARD on a strike (`body_renderer`, in the facing
  direction) + a bolder weapon-arm reach (`char_pose3d` H·0.30→0.36), so an attack
  reads from ANY facing (was near-invisible head-on). Pairs with G1's fighting
  face. Render `g3_attack.png`. (Iso action-read is a later pass.)
- **G4 — Hands & directional boots. ✅ DONE (2D).** `draw_arm` caps the wrist with a
  rounded HAND + lit knuckle; `draw_legs` draws a directional BOOT whose toe points
  the facing (a clear silhouette cue). Render `audit_2d.png`. Tests:
  `test_body_renderer.TestActionAndAnatomy`.
- **G5 — Gear detail. ✅ DONE (2D).** `body_parts.draw_pauldrons` (armored shoulder
  plates for warrior/paladin/guard/knight/fighter/barbarian) + `draw_hood` (a cowl
  for rogue/ranger/assassin/druid/warlock), wired in `body_renderer` by class;
  casters keep the R5 robe. Tests: `test_body_renderer.TestGear`.
- **G6 — Iso action readability. ✅ DONE.** The strike LUNGE reaches the iso view
  (`iso_render` shifts the figure toward its facing in world space during a strike,
  projected through `world_to_screen`) — parity with G3 (the swing already plays
  via `attack_figure`).
- **(deferred → further plan) Dynamic 2D lighting via baked normal maps** — a large
  multi-round feature; opens the "H-series" of further improvements.

G1 + G2 alone transform the read (a face that isn't two black holes; iso figures
that aren't murky). Same discipline as R1–R6: pure/thin, cached, headless-tested,
a before/after render each round, files < 500 lines, suite green + commit per round.

## Further plan — the H-series (after G1–G6)

The G-series pushed the 2D well ahead (expressive faces, lunging attacks, hands,
boots, gear); the ISO now lags. The H-series closes that gap, then finishes action
readability and takes on the ambitious lighting unification.

- **H1 — Iso gear parity. ✅ DONE.** The iso figure already had hands, booted feet,
  eyes + a nose and a hood (rogue/ranger head→hood); the gap was armored SHOULDER
  PLATES. `iso_gear.pauldron_mesh` adds a steel cap per shoulder for armored
  classes, wired through the kit (now 6-tuple, `iso_chars.kit_of` sets the flag
  from `body_parts.ARMOR_CLASSES`) → `accessories`. An iso warrior now reads plated
  (G5 parity). Render `audit_iso.png`. Tests: `test_iso_chars`. (Iso FACE
  expression — re-baking the head per mood — deferred to a later pass.)
- **H2 — Cast readability. ✅ DONE (2D).** `body_renderer._cast_glow` gathers a soft
  additive cyan bloom of arcane light at the casting hand during a `cast` action,
  so a spell reads as MAGIC, not just a staff wave. Render `h2_cast.png`. Tests:
  `test_body_renderer` (`test_cast_glow_is_bright`). (Shoot draw-and-loose + iso
  cast glow: a later pass.)
- **H3 — Equipment-driven appearance (MED, both).** Render the ACTUAL worn gear —
  helmet kind, armor tier, a cape, the specific shield/pack — from the equipment
  data, not just a class default, so upgrades show on the body. Shared 2D + iso.
- **H4 — Population variety (MED).** Wider skin tones, hairstyles + hair colour, and
  body types so a crowd reads as individuals, not clones.
- **H5 — Status on the body. ✅ DONE (2D).** `char_fx.draw_status` (wired into
  `draw_effects`) overlays a soft cue per active magical condition: BLESSED → a
  golden body-hugging halo RING, POISONED → rising green wisps, CURSED → a dark
  violet ring — all framing the visible figure, not washing it out, pulsing on the
  anim clock. Render `h5_status.png`. Tests: `test_char_fx.TestStatusOverlays`.
- **H6 — Dynamic 2D lighting via baked normal maps (AMBITIOUS).** Bake a normal map
  alongside each 2D sprite and light it by the world (day/night, torch, forge,
  wisp) so 2D characters react to lighting like the iso world does — the unifying
  capstone; likely several sub-rounds.
- **H7 — Cloth & hair richness.** Capes for cloaked classes, stronger cloak/hem
  sway, hair flow — build on `char_flow`.

Order = close-the-gap first (H1), then readability (H2), then depth (H3–H5), then
the ambitious lighting (H6) and polish (H7).
