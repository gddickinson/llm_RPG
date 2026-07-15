# Isometric 3D-look World — Phase 41 (George, 2026-07-14)

George chose the **full isometric 3D-look world** (from the "make it more 3D like
movieMaker" ask): tilt the whole world to an isometric / three-quarter view with real
height, and render buildings / props / characters as true 3D-shaded geometry baked (once,
at the fixed iso angle) to sprites via a ported numpy software rasterizer. The classic
"looks 3D" RPG look, real-time, still pygame.

## Proven feasible

- **3D object baking** — `scratchpad/3d_poc.png`: movieMaker's `raster3d.py` (pure-numpy
  perspective z-buffer Lambert rasterizer) ported here rendered a house+roof, temple
  pillars, a sarcophagus, a pillar, and figures as real 3D geometry. Because the camera
  angle is FIXED, each mesh is rasterized ONCE → cached sprite → blitted like any 2D
  sprite. Genuine 3D objects, zero per-frame 3D cost.
- **Iso projection** is standard 2:1 dimetric tile math (below), cheap and real-time.

## Core math (P41.1)

2:1 isometric (dimetric). A world tile `(wx, wy)` at elevation/height `z` →
```
sx = (wx - wy) * (TW // 2) + origin_x
sy = (wx + wy) * (TH // 2) - z * ZSCALE + origin_y      # TW:TH = 2:1, e.g. 64×32
```
Depth-sort key (painter's back-to-front): `(wx + wy, z, layer)`. `screen→tile` inverse for
mouse/targeting. All pure, headless-testable in `ui/iso.py`.

## Rendering model

- **Terrain**: each tile a shaded iso DIAMOND (the textured/shaded ground); elevation lifts
  the diamond and draws a cliff SIDE face (left/right) so hills read as 3D. Water/lava get
  the same diamond with theme shading.
- **Objects**: buildings (box + pitched roof), props (per-prop mesh), and characters are
  3D meshes rasterized once at the iso angle (`ui/raster3d.py`) → cached iso sprites,
  anchored at the tile floor, drawn in depth order. Reuse the P39 prop/theme/light data +
  the P33.4 character rig (baked to iso frames or kept as billboards).
- **Depth sort**: one back-to-front pass over (terrain tiles + objects + characters) by the
  sort key — the heart of correct iso occlusion (a hero behind a wall is hidden).

## Guardrails — build it WITHOUT breaking the game

- **Toggleable render mode.** A `render_mode` setting / `LLM_RPG_RENDER=iso|topdown` (default
  topdown until iso is solid). The current top-down renderer STAYS as the fallback; the iso
  renderer grows beside it. The game stays fully playable + green throughout.
- **Reuse, don't rewrite, the engine.** Iso is a VIEW change only — world state, movement,
  combat, AI, data are untouched. Only `ui/renderer.py`'s draw is swapped when iso is on.
- Pure math + cached bakes; every file < 500 lines; headless tests for the projection +
  depth sort + bake; a screenshot every round.

## Build order (each a tested, committed round)

- [ ] **P41.1 Iso projection foundation** — `ui/iso.py`: `world_to_screen`, `screen_to_tile`,
  diamond/cliff geometry, `depth_key`. Headless tests.
- [ ] **P41.2 The numpy software rasterizer** — `ui/raster3d.py` (ported from movieMaker):
  `render(meshes, cam…) → (rgb, mask)`; `bake(mesh, angle, size)` → cached iso sprite.
  Tests: a box bakes to a shaded 3D-looking sprite.
- [ ] **P41.3 Iso TERRAIN render path** — a new `render_iso` in the renderer (behind the
  toggle): draw the visible tiles as depth-sorted shaded diamonds with elevation cliffs,
  over the P36 elevation + P39.2 themes. First real iso screenshot.
- [ ] **P41.4 Iso OBJECTS** — bake buildings (box+roof) + props to iso sprites (via raster3d
  + the P39 prop/theme data), place + depth-sort them in the scene.
- [ ] **P41.5 Iso CHARACTERS & movement** — the player/NPCs placed at iso tile positions,
  facing + walk anim, correctly depth-sorted (behind/in front of walls). Targeting/mouse via
  `screen_to_tile`.
- [ ] **P41.6 Iso INTERIORS** — dungeons/buildings rendered iso (themed/furnished/lit as P39,
  now in 3D), with a cut-away or roof-fade so you can see inside.
- [ ] **P41.7 Fidelity + polish** — fold Phase 40 in (supersampled high-detail iso terrain +
  objects), camera pan/zoom, UI/HUD fit, lighting/shadows, edge cases; flip the default to
  iso once it's at parity.

## Relationship to Phase 40 (graphics fidelity)

Phase 40's supersample + layered-detail work is NOT wasted — it becomes the texture/shading
for the iso diamonds and the baked object meshes (P41.7). Phase 40 and Phase 41 merge: the
iso world IS the higher-fidelity, more-3D world George asked for.
