# Graphical Fidelity — Phase 40 (George, 2026-07-14)

George: "Vastly improve the graphics of the world and its objects. Much more detail is
needed, at a higher resolution." (Ultrathink.)

## Diagnosis — why it currently reads low-res / low-detail

Everything is procedural (no art assets), which is right — but the current sprites are
built with:
- **Flat shading**: 2–3 tone dither fills (`tile_variants.RECIPES`), 2–3 flat colours per
  prop/building. No gradients, few tones.
- **Sparse detail**: ~11 grass blades, ~3 ripples per tile; objects are a few primitives.
- **Aliased, native-size drawing**: `pygame.draw` + `set_at` at the display tile size, so
  curves/diagonals are blocky and sub-pixel detail is impossible.
- **No soft shadows / ambient occlusion / rim light** to give objects mass.

Net: terrain reads as a repeated noise stamp; objects read as flat icons.

## The technique (validated by the P40.0 proof-of-concept — `scratchpad/gfx_poc.png`)

**Supersample + layer + shade.** Build every sprite at `size × SS` (SS≈3), draw *far* more
layered detail, then `pygame.transform.smoothscale` down to `size`. The downscale
anti-aliases everything and preserves sub-pixel detail. Cache the result (built once) so
per-frame cost is unchanged. In the PoC, grass gained soft mottled patches + real blades +
flowers, water gained a depth gradient + ripple arcs + sparkle — a night-and-day jump from
the flat originals, at the same display size.

Each sprite becomes a STACK of layers (adapted from autonomous_world's terrain gens):
1. **Gradient base** — a subtle directional gradient, not a flat fill.
2. **Mottle / texture** — multi-octave soft patches, 5–7 tones (a proper shade ramp).
3. **Dense scattered detail** — many varied elements (blades of varying height/angle/shade,
   ripples, rocks, cracks, canopy clumps, flowers, pebbles) — 3–5× the current density.
4. **Directional light** — consistent top-left highlights + bottom-right soft shadow.
5. **Contact shadow / AO** — a soft dark base under props/buildings/characters to ground them.
6. **Rim / outline** — a subtle darker edge so objects pop from the ground.

## Build order (each a tested, committed round; cache everything, files < 500)

- [x] **P40.0 Plan + proof-of-concept** — this doc + `gfx_poc.png` (current vs high-detail).
- [ ] **P40.1 The gfx foundation** — `ui/gfx.py` (pure/thin): `supersample(build_fn, size,
  ss)` (build big → smoothscale), `vgradient`/`rgradient` (cached gradient surfaces),
  `shade_ramp(base, n)` (n-tone light→dark ramp), `soft_shadow(size)`, `outline(surf)`,
  `mottle(surf, ...)`. Wire the SpriteLoader tile/furniture/prop builders through
  `supersample`. Immediate crispness win with no per-frame cost.
- [ ] **P40.2 High-detail TERRAIN** (biggest win — the ground is most of the screen). Rebuild
  the `tile_variants` recipes/builders with the full layer stack (gradient base + dense
  mottle + 3–5× detail + light/shadow), supersampled. Per-terrain richness: grass
  blades+tufts+flowers, water depth+ripples+foam+sparkle, forest layered canopy+trunks,
  mountain strata+snow+cracks, swamp reeds+murk, sand ripples, road cobbles, farmland
  furrows+crops. Compose with the P33.2 edge/coastline blending so tiles don't seam.
- [ ] **P40.3 High-detail OBJECTS** — upgrade `prop_sprites` + the legacy `furniture` sprites
  with shading, gradients, material texture, outlines, contact shadows, micro-detail (rivets
  on braziers, carvings on sarcophagi, grain on wood). Supersampled.
- [ ] **P40.4 High-detail BUILDINGS** — richer 2.5D: brick/stone COURSING (rows + mortar),
  roof-tile texture (thatch strands / slate / shingle rows), framed windows with mullions,
  panelled doors, weathering, soft AO where walls meet ground. Over `renderer_buildings` +
  `roof_shapes` (already material-aware).
- [ ] **P40.5 Lighting & atmosphere polish** — soft directional shadows for props/buildings,
  ambient occlusion, day/night colour grading, a gentle bloom on light sources, subtler fog.
- [ ] **P40.6 Characters** — richer body shading/outlines + drawn gear detail (only if the
  P33.4b puppets still read flat next to the upgraded world).

## Notes & guardrails

- **Fold in P39.6**: the world-detail phase's "overworld scatter detail + broad polish" round
  is subsumed here (P40.2/P40.3 deliver it at higher fidelity).
- **Performance**: supersampled sprites are built ONCE and cached (by name/variant/size), so
  frame cost is unchanged; only build-time + memory rise a little. Never supersample
  per-frame. A `LLM_RPG_SS` env / setting can dial SS (1 = off) for weak machines.
- **Still no art assets** — all procedural, all headless-testable (build a surface, assert
  non-empty / richer than before). Keep every file < 500 lines (split gfx helpers from the
  recipe data from the draw passes).
- **Resolution**: the DISPLAY tile size is unchanged (the grid is the same), but each tile is
  rendered from a higher-resolution source, so the world looks markedly sharper + more
  detailed. The map-zoom setting + resizable window already let George view it larger.
