# OAKVALE — a large, living, walled town + countryside

**George's ask (2026-07-16):** redesign & enlarge Oakvale into a large multi-district
town with a **central defended region walled with multiple gates**; districts for
guilds, shops, taverns/pubs, blacksmith & armourer, wizard crafts, libraries, a
cathedral & churches, and numerous dwellings; a **full role-based population**
(shopkeepers, landlords, tavernkeepers, craftsfolk, smiths, armourers, a mayor,
bankers, adventurers, guildsmen, thieves, street urchins, vagrants); and a
**living countryside** — supporting villages, farmers working nearby fields,
terrain-sensible roads with bridges, rivers, and a water supply (wells/fountains).

This is the design + phased plan. Research synthesized from `autonomous_world`
(settlement layout) and `building-gen` (building variety); both reports captured
in the session log.

## Design principles (what we adopt from the research)

- **Districts via Voronoi wards** — golden-angle "sunflower" seeds over the town
  disc → nearest-seed wards → 3× Lloyd relaxation (even, organic wards) →
  classify by **distance ring**: inner = market/civic/temple/guild, middle =
  residential/craft, outer = farming/stable/military; terrain overrides push
  waterside trades (docks/tanners) to the river. (`autonomous_world/voronoi_layout.py`)
- **Streets by size template + hierarchy** — boulevards (N–S, E–W) + a polygonal
  ring road + radial lanes + a small core grid, with a reserved **central market
  square**; road types (main/ring/lane) distinguished by width. Segments nudge
  around water. (`street_layout.py`)
- **Defended core = wall polygon around the inner ~55%** — gates placed exactly
  where a **main street crosses the wall**, towers at corners + intervals. Outer
  districts (residential/craft/farm) sit OUTSIDE the wall as suburbs. This is the
  "central defended region with multiple gates". (`wall_generation.py`)
- **Terrain-aware roads = A\* over a cost-field** (flat cheap, hills dear, water
  ∞→routes around, or stamps a BRIDGE where a road must cross water), network by
  **MST + a few loop edges**, road tier by settlement importance. (`road_pathfinder.py`)
- **Role population = specialization-weighted profession pools** — each building
  KIND spawns its role NPC (shop→shopkeeper, tavern→tavernkeeper, forge→smith…);
  dwellings fill with townsfolk; a town roster adds the singletons (mayor,
  bankers, guildsmen) and the underclass (thieves, urchins, vagrants). Homes near
  the residential wards; workplace = the building. (`specializations.py`)
- **Building variety (later polish)** — expand roof SHAPES (mansard/gambrel/
  cross-gable/pyramid) via building-gen's `roof_types.select_roof` rules; per-KIND
  footprint/room/roof/material specs; multi-rectangle massing (L/T/U/courtyard)
  to break the "row of boxes" look. Most building/interior machinery already
  exists (BLD phase); this is incremental.

## Architecture — new `world/town/` subpackage (each file < 500 lines)

- **`world/town/wards.py`** — Voronoi districts: sunflower seeds, numpy
  nearest-seed assignment, Lloyd relaxation, ring classification → a per-tile
  ward map + `{ward_id: district_type}`. Data: `data/town/districts.json`.
- **`world/town/streets.py`** — street-network templates (boulevards + ring +
  radial + core grid + market square) → ROAD/plaza tiles; road hierarchy.
- **`world/town/town_wall.py`** — wall polygon around the inner core, rasterized
  to WALL tiles; gates at street×wall crossings; corner/interval towers. Reuses
  the P37.3 gate + P31.1 tower machinery.
- **`world/town/lots.py`** — building lots along street frontage; each lot's ward
  → a building KIND (from `districts.json`) → a `Location` (tagged for interiors
  + residents). Reuses `room_gen.subdivide` where useful.
- **`world/town/town_gen.py`** — orchestrator: `build_town(world, cx, cy, radius)`
  → streets → wards → wall → lots → Locations. Reusable (Oakvale, future towns).
- **`world/town/population.py`** — role NPCs per building + townsfolk in dwellings
  + the town roster singletons/underclass. Data: `data/town/roles.json`.
- **`world/countryside.py`** + **`world/road_astar.py`** — A\* terrain roads,
  bridges, satellite villages (MST-linked), farm rings, wells/fountains.

Existing reused infrastructure: `fortify.py` (walls/gates/towers/guards),
`building_types.json` (24 kinds), `blueprints.py`/`homes.py` (residents),
`interiors.py`+`room_plan.py`+`furnishings.py` (interiors), `production_loop.py`
(economy), `guildhalls.py`, `adventurers.py`, `river_gen.py`.

## Phased plan (each phase = a tested, committed round)

- **T1 — District wards** (`wards.py` + `districts.json`): Voronoi + Lloyd + ring
  classification. Pure, numpy, headless-tested. ← START HERE (map-size-independent)
- **T2 — Street network** (`streets.py`): size-scaled templates + market square,
  rasterized, water-aware. Pure + tested.
- **T3 — Town wall & gates** (`town_wall.py`): inner-core wall polygon, gates at
  road crossings, towers. Tested.
- **T4 — Building lots & placement** (`lots.py` + `town_gen.py`): frontage lots →
  KIND by ward → Locations; the town takes shape on a test canvas + screenshot.
- **T5 — Integration**: replace the small Oakvale with `build_town`; wire
  interiors + fortify; size the map to fit town + countryside. (The one step that
  depends on the enlarge-in-place vs dedicated-region choice — steer here.)
- **T6 — Role population** (`population.py` + `roles.json`): every building gets
  its keeper/craftsfolk; dwellings get townsfolk; mayor/bankers/guildsmen/thieves/
  urchins/vagrants; homes↔workplaces.
- **T7 — Living countryside** (`countryside.py` + `road_astar.py`): terrain-aware
  roads + bridges, supporting villages (MST-linked), farm rings worked by farmers,
  wells/fountains for water supply.
- **T8+ — Building variety polish**: roof-shape variety, per-KIND specs,
  multi-rect massing. Incremental.

## Open decision (steer at T5)

**Where the big Oakvale lives.** Two readings, same generator:
(A) **Enlarge the classic world in place** — bump the default map, replace small
Oakvale with `build_town`, make Riverside/Stonepine the supporting villages.
Matches "Oakvale should be enlarged". Higher integration risk (existing content +
tests + perf). ← default/recommended.
(B) **Dedicated large-town region** — a new start option on a bigger map, classic
world untouched. Lower risk, but a separate place rather than THE Oakvale.
T1–T4, T6–T7 are identical for both; only T5 differs.
