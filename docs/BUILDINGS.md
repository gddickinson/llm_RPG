# Buildings — Elaboration Plan (George, 2026-07-15)

George: buildings "are still very basic and need elaboration" — wants MUCH better,
more realistic buildings with better **frontage**, **layouts**, **furnishing** and
**decoration**. Research-first (like the P40 graphics work), then build in tested rounds.

Research: three parallel audits — exterior/frontage, interior/layout/furnishing, and a
mining pass over the on-disk `building-gen` (the source of `roof_shapes.py`'s material
system) + `autonomous_world`. Findings below; reference-technique notes fold in as they land.

## Current state — why buildings read basic

### Exterior (the street frontage)
- Drawn as flat 2.5D blocks (`ui/renderer_buildings.py` `_draw_block`/`_draw_footprint`);
  P40.4 added masonry/timber **coursing** + roof **tile rows** (`roof_shapes.wall_courses`/
  `roof_courses`). That's the whole facade vocabulary.
- **Doors** are a flat colour rect in a *separate* pass (`ui/door_glyphs.py`), kind-agnostic,
  not part of the facade — no frame, panelling, planking, arch, lintel, step, or double doors.
- **Shopfronts / signage: entirely absent.** No awnings, hanging signs, display windows,
  forge-glow, anvil/oven motifs. So `smithy`, `bakery`, `shop`, `lodge`, `farmhouse` all render
  as a plain gable house — no way to tell a business from a home.
- **Architectural trim: absent** — no cornices, window lintels/sills, corner quoins, gutters/
  downpipes, eaves fascia/soffit.
- **Windows** are a rigid uniform grid (one per column, every column, fixed size) — no shutters,
  bays, real mullion grids, ground/upper variation, or registration around the door.
- **Roofs** are flat and thin — no dormers, ridge caps, eaves overhang (+ soffit shadow onto the
  wall), bargeboards; thatch reads identically to slate (just a hue + 1px lines).
- No porches/steps, no weathering/moss/age (every cottage is pixel-identical), minimal depth/
  relief (two faces + a flat drop shadow), and **none of it composes with the P40 `gfx.py`
  supersample/shading foundation** that terrain + characters use — so every facade edge aliases.

### Interior (layout, furnishing, decoration)
- Pipeline (`world/interiors.py` `build_interiors_for_world`): name-keyword → 1 of 19 authored
  ASCII **blueprints** (or a hand-built factory, else no interior) → `fit_to_footprint` rescale →
  a **BSP** subdivision *only if* the shell is ≥ 11×8 (rare) → P39.3 themed decorative `furnish`.
- **Rooms are NOT functionally differentiated.** `_furnish_rooms` assigns generic kits
  (`["Table","Chair","Hearth"]`, `["Bed","Chest"]`, …) by **room size rank**, not by building
  purpose — a tavern's 2nd room and a temple's 2nd room both get a bed + chest.
- Furniture is a **non-blocking decorative overlay** (tiles stay walkable) — there's no real
  arrangement (a table you walk around, chairs flanking it); "arrangement" is just where a sprite
  is painted, shuffled randomly within wall/corner/centre buckets across the whole interior.
- **Theme is keyed off the interior NAME, not the building KIND**, and there is **no `shop`
  theme** — so shops, stables, farmhouses, lodges, halls, towers all fall through to `"home"`
  and get a **bed + hearth + hearthrug** (wrong for a shop). ~23 kinds collapse to home/cave.
- **Wall decoration minimal/mislocated**: tapestries only in temple/castle, **no paintings**,
  and **interior walls never get windows** (`openings.draw_window` is exterior-only). Props are
  drawn tile-*centred* with no wall-facing, so a "tapestry" sits mid-floor, not hung on the wall.
- **Lighting gap**: `hearth`/`forge`/`fireplace`/`oven` are **not** in `prop_sprites.LIT_PROPS`,
  so a fire-lit home or smithy casts **no light pool** — only the player's carried radius.
- **Occupant ignored**: blueprints carry `npc_class` but `furnish` never reads it — a smith's
  home furnishes identically to a scholar's. The lone NPC sits at the room's geometric centre,
  not at a functional station (bartender at the bar, smith at the anvil).
- `world/building_types.py` already has `function_of_kind`/`classify_interior` — but **only the
  economy uses it**; interior generation never consults building function.

## Constraints (must hold throughout)
- **100% procedural, no art assets**; content-as-data in `data/*.json`; **every file < 500 lines**.
- Tight budgets: `interiors.py` **431/500**, `structures.py` 427, `renderer_buildings.py` **417**
  — new logic goes in **new modules**, not these. Roomy: `roof_shapes.py` (236), `openings.py`
  (130), `furnishings.py` (121), `building_types.py` (94).
- Pure + **headless-testable** + seed-reproducible (the room_gen/furnish pattern). Reuse, don't
  replace: `room_gen.subdivide`, `building_types.function_of_kind`, the `furnishings._buckets`
  wall/corner/centre classifier, `prop_sprites` + `LIT_PROPS`, `interior_theme`/`interior_light`,
  and the `gfx.py` supersample/`contact_shadow` path.

## The plan — phased, by impact-over-cost

### BLD.1 — Data quick-wins (cheapest, every building improves)
Close the theme/furnishing coverage gaps in `data/furnishings.json` + `data/interior_themes.json`
(add `shop`/`market`, `farmhouse`/`cottage`, `stable`, `lodge`, `watchtower`, `hall`, `tower`,
`well`/`shrine`), and make `theme_of` fall back through the building **KIND** (via
`building_types`) not just the name — so a store stops getting a bed + hearthrug. Add
`hearth`/`forge`/`fireplace`/`oven` to `LIT_PROPS` so fire-lit rooms glow. Pure data + a
one-line lighting fix.

### BLD.2 — Functional room plans (biggest interior structural win)
New `world/room_plan.py` + `data/room_plans.json`. After `subdivide`, **label** leaf rooms by
`function_of_kind(kind)` and assign roles by area-rank **and** door-adjacency (public room touches
the entrance, private rooms deeper): tavern → common-room / bar / kitchen / store / guest-room;
home → hearth-room / bedroom / kitchen; smithy → forge / workshop; temple → nave / altar / vestry;
shop → counter / storeroom. Data maps role → furniture kit; replaces the size-indexed kit in
`_furnish_rooms`. Retune the BSP gate so medium buildings also subdivide.

### BLD.3 — Arrangement grammar (rooms that read real)
New `world/furnish_grammar.py`. Per-role placement rules using `_buckets`: bed → wall corner;
hearth → wall midpoint (under a chimney); counter/shelves → a contiguous wall run; table → centre
with chairs on adjacent free tiles; altar → far wall centre facing the door. Group placement
per room instead of shuffling the whole interior. Decide which key pieces become
movement-blocking so circulation reads.

### BLD.4 — Facade doors (biggest exterior win)
New `ui/facade.py` (pure geometry, cached, headless-testable). Real entrance doors integrated
into the facade — framed / panelled / planked / arched **per kind**, with a lintel and a step/
threshold; double doors for hall/temple. Keep the lock-state colouring. Replaces the flat rect.

### BLD.5 — Shopfronts & signage (kind identity)
In `ui/facade.py`: awnings, a projecting/hanging signboard, and a display/bay window for
tavern / inn / shop / bakery / smithy; forge-glow + anvil motif for smithy/forge, an oven for a
bakery. Drives off `kind`. This is what makes a temple, a smithy, an inn and a home read
distinctly from the street.

### BLD.6 — Occupant personality, wall decoration, floor coverings, clutter
Thread `npc_class`/profession into `furnish` via `data/occupant_furnishings.json` (smith →
tools/weapon-rack, scholar → books/lectern, cook → pots, cleric → candelabra); seat the NPC at
its functional station. A wall pass places paintings / tapestries / **interior windows** /
sconces on real wall tiles with facing (reuse `openings.draw_window`; give `_WALL_PROPS` wall-face
anchoring). Add hearthrugs (at hearths), runners (temple/hall), and light role/occupant clutter.

### BLD.7 — Window trim, shutters & architectural trim
Lintels/sills + optional shutters around windows, a real 2×2 glazing grid, ground/upper size
variation, and windows registered around the door (not the uniform every-column row). Corner
**quoins** on stone/brick, a **cornice** band under the eaves, **gutters + a downpipe**. Cheap
line/rect geometry in `ui/facade.py` / `roof_shapes.py`.

### BLD.8 — Roof relief, depth & weathering (composed with gfx.py)
Eaves overhang with a soffit shadow onto the wall, a thicker ridge cap, **dormers** for tall
kinds, and material-specific texture depth (ragged thatch, overlapping slate/tile relief) in
`roof_shapes.roof_courses`. Build each facade once via `gfx.supersample`, **cache** it (key
`(kind,w,d,h,ts)`), add a roof-to-wall **contact shadow** and recessed door/window reveals, and
light **deterministic weathering** (moss at eaves/base, stains) so identical cottages stop
looking cloned — tying buildings into the P40 look the rest of the scene already has.

## Sequencing
BLD.1 first (pure-data, immediate win everywhere). Then the interior structural core BLD.2 → BLD.3.
Then the exterior identity BLD.4 → BLD.5. Then BLD.6 (personality/decoration), BLD.7 (trim),
BLD.8 (roof relief + weathering + gfx compose). Each is one tested, committed round, every file
kept under 500 lines (new modules: `world/room_plan.py`, `world/furnish_grammar.py`, `ui/facade.py`;
new data: `data/room_plans.json`, `data/occupant_furnishings.json`, extended theme/furnishing JSON).

## Reference techniques (from `building-gen` + `autonomous_world`)

The mining pass found that **`autonomous_world` (aw) shares llm_RPG's exact tile/interior
paradigm — its code ports almost verbatim**, while `building-gen` (bg, a 3D engineering
generator) contributes algorithms + data models (it already gave us `roof_shapes.py`). Both
confirm the #1 gap: **rooms are anonymous**. The concrete ports, mapped to the phases above:

- **Room templates & building room-sets** → **BLD.2**. aw `game/systems/interiors.py`
  `ROOM_TEMPLATES[type] = {furniture:[(tile,min,max)], min_size, max_size}` with **quality
  tiers** (`bedroom_poor`/`_fine`/`_luxurious`) + `BUILDING_ROOM_SETS[kind] = [room_type…]`
  (tavern = entry_hall + tavern_hall + kitchen + storage + 3×guest_room + innkeeper's
  double_bedroom + stairwell). → `data/room_templates.json` + `data/building_room_sets.json`;
  `subdivide` tags each leaf with a `room_type` matched to its size.
- **Feature-composition furnishing** → **BLD.3**. aw `game/world/blueprint_gen.py`
  `ROOM_FURNISHINGS[type] = {features:[(name,prob)]}` + `_furnish_room`: named *compositions*
  not scattered tiles — `bar_counter` (L-shaped corner), `long_tables`/`scattered_tables`,
  `pew_rows`, `altar_end` (far wall centre), `pillar_row`, `carpet_runner` (2-wide centre),
  `bookshelf_walls`, `fireplace_wall`, `throne_dais`, `weapon_racks`, `display_tables`. **Biggest
  realism-per-line win.** → `features[]` in `data/furnishings.json` + a dispatch fn per feature.
- **Placement hardening** → **BLD.3**. aw `interior_gen.py` Stage 4: WALL / CENTER / INNER_WALL
  (fireplace prefers interior walls) / FLOOR_DECOR / STRUCTURAL categories with graceful
  fallback, count ranges `(min,max)`, and — critically — a **door-apron exclusion** (never place
  furniture on or beside a doorway; fixes blocked-interior bugs). Extends `furnishings._buckets`.
- **Decoration pass** → **BLD.6**. aw `interior_gen.py` Stage 5: carpet-before-fireplace,
  entrance pillars, **corridor torches every ~5 wall tiles** (immediately feed the P39.4
  `interior_light` pools), storage clutter that never blocks doors.
- **Detailed interior/facade render recipes** → **BLD.5/BLD.8**. aw `ui/renderer_buildings.py`
  (near-verbatim pygame): mortar-lined stone walls, floor grout + quadrant jitter, framed
  plank door with a handle, a **window light-pool blitted onto the floor**, detailed beds/tables;
  and roof/facade textures — thatch straw, clay overlap+highlight, slate blue-sheen, **canvas
  awning stripes** for shops. Ports into `prop_sprites`/`roof_shapes`/`iso_furniture`.
- **Facade StyleParams & bays** → **BLD.5/BLD.7**. bg `style/models.py`: `window_bay_spacing`,
  `symmetrical_facade`, `num_dormers`, `has_porch`, `exterior_wall_pattern` — extend
  `data/building_styles.json` so windows land on a **regular rhythm** on true exterior walls
  only. **Frontage orientation** (aw `lot_subdivision.py` `road_direction`) → put the door/
  shopfront on the wall that faces the street, not always-south.
- **Grid templates & room-graph** → **BLD.2 (later) / castles**. bg `layout/grid_layout.py` +
  `program/templates/*.yaml` (data-driven `col_widths`/`rows`/room cells) → `data/building_grids/
  *.json` for signature buildings; aw `CONNECTIVITY_RULES` + bg adjacency rules → a room-graph
  module for castles/manors only (aw `interior_gen.py` is 1792 lines — port as 2-3 focused
  modules under 500 each).

**Refined build order** (interior-first, per the low-risk incremental path both agents converged
on): BLD.1 (data theme/lighting quick-wins) → BLD.2 (room templates + per-room typing, the
unlock) → BLD.3 (feature compositions + placement hardening) → BLD.4/BLD.5 (facade doors +
shopfronts/awnings/signage) → BLD.6 (decoration pass + occupant clutter + interior render polish)
→ BLD.7 (trim/shutters/bays) → BLD.8 (roof relief + weathering + gfx compose). Steps BLD.1–BLD.3
deliver the bulk of the interior realism; aw's code makes them fast to port.
