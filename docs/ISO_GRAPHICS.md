# ISO GRAPHICS — realistic isometric world

**George (2026-07-16):** make the isometric graphics more realistic — environmental
tiles, buildings, and characters; better character animation (movieMaker as
inspiration for 3D character work); scale may need to be larger for detail.

Design synthesized from two research passes (both in the session log): an AUDIT
of the current iso renderer and a study of `/Users/george/claude_test/movieMaker`.

## The core finding

The iso path (`ui/iso_*.py`) BAKES numpy-software-rasterized 3D once per
(kind/pose/facing) into cached sprites — a sound architecture — but it renders
**crude boxes and flat diamonds and ignores every rich top-down module the game
already has**: `roof_shapes`, `facade_trim`, `roof_relief`, `building_variety`,
`tile_variants`, `char_pose`, `char_mocap`. My `raster3d.py` already ported
movieMaker's rasterizer + camera + 2× SSAA, so the work is (a) build richer
MESHES and (b) reuse the existing style/animation data.

## Current state (baseline)

- **Buildings — Poor:** one coloured box + one gable/parapet block per anchor
  tile; no windows/doors/chimneys/real roof shapes/storeys/materials/variety;
  not footprint-spanning. (`ui/iso_objects.building_sprite`)
- **Characters — Poor + STATIC:** 5 stacked boxes (legs/torso/head/hair/nose),
  4 facings, baked once, **no walk/idle/attack** — snaps between facings.
- **Tiles — Poor→OK:** flat shaded diamonds + 3 pixel flecks; `tile_variants`
  unused; flat water; stepped height, no slopes/blending.
- **Scale:** tile_size 48 → iso 48×24; bake at 2× SSAA (a soft detail ceiling).

## Phased plan (each = a tested, committed round)

- **ISO.1 — Realistic BUILDINGS** (biggest gap; research-independent). Enrich the
  baked building mesh: real roof SHAPE (gable ridge / hip pyramid / flat parapet)
  sized to the footprint, storey-driven HEIGHT (a tower towers), recessed WINDOW
  boxes per storey, a DOOR, CHIMNEY boxes, materials + per-building VARIETY
  (covering/wall via `building_variety`, cache-keyed so clones differ). ← START
- **ISO.2 — Richer TILES.** Texture the iso diamonds from `tile_variants`
  (grass blades / water ripples / furrows / rock), animated water, softer
  inter-terrain shading, ramp-shaded slopes on lifted tiles.
- **ISO.3 — Character BODIES: proportions + stance + shading** (movieMaker
  #2/#4/#5, big realism-per-line). Anthropometric stature-fraction proportions
  for the figure; a seeded contrapposto / relaxed-arm STANCE (anti-symmetry
  kills the mannequin look); two-light shading + per-part colour; 3–4× SSAA.
- **ISO.4 — Character ANIMATION** (movieMaker #1/#3). A small BONE hierarchy +
  FK matrix stack so the boxes are a posable puppet; bake POSED frames per
  clip-phase (walk cycle + attack) sampled from the existing `char_mocap` clips;
  drive phase from `metadata["_anim"]` (which iso already reads for facing).
  Mind the cache multiply (N frames × 4 facings).
- **ISO.5 — Scale & fidelity polish.** Larger bake resolution where detail lands;
  optional bigger tile_size; re-frame the bake camera for taller meshes.

## Reuse map (top-down → iso)

roof_shapes (shapes/shades/coursing) · facade_trim · roof_relief (weathering) ·
building_variety (variant_style/window_shape) · openings (window shapes) ·
tile_variants (build_tile/RECIPES) · char_pose/char_pose3d · char_mocap
(`data/anim/*.json`) · char_secondary (springs). movieMaker pure-numpy to port:
FK matrix stack (`skinning.world_of`+`_trs`), contrapposto/relax/jitter,
anthro proportion ratios, quaternion-continuity fix.
