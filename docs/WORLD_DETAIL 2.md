# World Detail & Decoration — Phase 39 (George, 2026-07-14)

George: "Different regions/modules should have different THEMES — tombs dark, deserted,
dank with appropriate graphics. Buildings need embellishments: pillars, tapestries,
braziers, torches, mausoleum decorations. Every building should have appropriate
furnishings + decorations, applied throughout the game. Add many more decorative items,
furniture, diases, different stairs, different windows. Make the world come alive with
far more detail." (Referenced building-gen, autonomous_world, movieMaker.)

## Research synthesis (what to lift)

- **autonomous_world** (best fit — pure pygame): a prop-type → procedural-sprite-BUILDER
  dispatch (zero art); a `kind → [(prop, x_frac, y_frac)]` furniture-layout table
  (`furnish.py`); a DECORATION PASS by room type (carpet / entrance pillars / corridor
  torches / storage clutter); radial-GLOW interior light sources (fireplace/forge/altar/
  fountain); context-driven AMBIENT PARTICLES (dust motes = old/deserted/dank; fireflies;
  embers). Prop set: TABLE BED CHEST THRONE BOOKSHELF BARREL ANVIL FORGE_FIRE FOUNTAIN
  CARPET MOSAIC PILLAR ALTAR FIREPLACE ARCHWAY IRON_GATE WELL GRAVESTONE.
- **building-gen**: the `fixtures.py` room_type→fixture + WALL-PREFERENCE placement engine;
  per-theme material COLOR tables; window variants (sash / casement / lancet / rose /
  arrow-loop / oriel / bay); door variants (panel / plank-studded / arched / stable);
  stair variants (straight / L / U / SPIRAL-for-towers); `building_type_rules.yaml` flavor
  for temple/tomb/smithy/tavern/castle to author fantasy props from. (Braziers, tapestries,
  sarcophagi, altars, statues, fountains, diases are NOT in building-gen — author them.)

## How it maps onto THIS codebase

- `ui/sprite_loader.py:furniture(name)` already draws procedural furniture (bed/chest/
  hearth/anvil/altar/shelf/barrel/table). → EXTEND with the new props (split into a pure
  `ui/prop_sprites.py` to hold the 500-line line).
- `ui/renderer.py:_render_zone` draws interior floor/walls (`_TERRAIN_TO_SPRITE` + a flat
  zone fill) + furniture. → add a per-THEME floor/wall palette + a lighting/ambiance pass.
- Placement: structures grid symbols (`world/structures.py` W/./D/<>/K/G/L + T/B/C/R/A/S),
  `world/interiors.py:_furnish_rooms`, `world/building_types.py:classify_interior`. → add a
  data-driven kind→furniture table + a decoration pass (wall-preference, like fixtures.py).
- Lighting: `ui/lighting.py` + `ui/light_palette.py` already punch torch/window light. →
  add interior light sources (brazier/torch/altar glow) + a dank-dim for tombs.
- Every building has a `kind` (`world/building_types.py`). → give each kind a THEME.

All content-as-DATA (JSON), pure-math-then-thin-draw, every file < 500 lines.

## New/extended props to author (procedural sprites)

pillar, half_pillar, brazier (lit glow), wall_torch/sconce (lit glow), tapestry/banner,
rug/carpet, sarcophagus, tomb_slab, gravestone, bone_pile, cobweb, urn/amphora, statue/idol,
fountain, dais/throne, candelabra, chandelier, well, cauldron, weapon_rack, crate/sack,
lectern/bookstand, hanging_herbs, wine_rack, mosaic_floor, pew/bench, coffin. Plus stair
variants (stone/spiral/wooden) and window variants (arched/lancet/rose/arrow-loop/round).

## Interior THEMES (palette + ambiance per kind)

| theme | floor / wall | props | ambiance |
|---|---|---|---|
| **tomb / crypt** | black stone / mossy stone | sarcophagi, braziers, urns, bones, cobwebs, gravestones | dank dim + dust motes, cold blue glow |
| **temple** | marble / pale stone | altar, pillars, braziers, pews, tapestry | warm gold glow, shafts of light |
| **smithy** | soot floor / iron | forge_fire, anvil, quench, bellows, weapon rack, barrels | forge orange glow, embers |
| **home / cottage** | wood / plaster | bed, table, hearth, chest, rug, shelves | warm hearth glow, cozy |
| **tavern** | wood / timber | trestle tables, bar, barrels, hearth, hanging herbs | warm, lively |
| **library / study** | parchment / wood | bookshelves, lectern, table, candelabra | quiet lamplight |
| **castle hall** | flagstone / stone | throne/dais, pillars, tapestries, braziers, long table | grand, torch-lit |
| **cave / dungeon** | rock / rock | rubble, bones, cobwebs, the occasional brazier | dark, dripping |

## Build order (each a tested, committed round)

- **P39.1 Prop sprite library.** `ui/prop_sprites.py` (pure geometry + thin draw) + a data
  catalog; extend `sprites.furniture()` to dispatch new prop names. Headless tests each
  prop surface builds; a contact-sheet screenshot.
- **P39.2 Interior themes (palette + dank/warm ambiance).** `data/interior_themes.json`
  (floor/wall/tint per theme) + `_render_zone` applies the theme's palette + a dim/dust for
  deserted/dank, a warm wash for lived-in. Themes chosen by the zone's building kind /
  structure. Screenshot: a dank tomb vs a warm home.
- **P39.3 Themed furnishing (kind→furniture + decoration pass).** `data/furnishings.json`
  (kind → prop list) + a wall-preference placement pass (adapted from fixtures.py) wired
  into `interiors`/`building_types` so every generated building is furnished in-theme.
- **P39.4 Interior light sources & mood.** Radial glow for braziers/torches/hearths/altars
  (via `lighting.py`); dust motes / cold shafts. Warm-vs-dank made to read.
- **P39.5 Stair, window & door variants.** Spiral/stone/wood stairs; arched/lancet/rose/
  arrow-loop windows; plank/arched/portcullis doors — rendered per theme in the 2.5D pass +
  interiors.
- **P39.6 Apply everywhere + adventure polish.** The Drowned Vault gets the tomb/crypt theme
  (sarcophagi, braziers, bones); every settlement building themed; overworld scatter detail
  (gravestones by ruins, etc.); broad screenshots; a "world feels alive" pass.

## Guardrails

- Content-as-data; validator green after each data edit. Pure geometry then thin pygame
  draw (like `roof_shapes`/`gate_shapes`). Every file < 500 lines — split sprite/palette/
  placement into separate modules. Fog/visibility respected; performance (cache prop
  surfaces by (name, theme, size), like the existing furniture cache).
