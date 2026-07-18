# Magic & Worldcraft — Design & Plan

> George (2026-07-18): a much deeper magic system (more spells, schools, tiers,
> per-caster learning/casting/requirements); spells that physically change the
> world (tiles, destroy/build structures, terraform, environment); magic-item
> crafting + imbuing + a far larger magic-item range; guilds that create/trade
> magic and aid crafting; **consistent rules** for how tiles/buildings/objects
> change by NON-magical means too; workers who gather → trade → **build**;
> a player building/terraforming tool with plan-and-implement pop-ups; and
> designs that **persist** across sessions and are **saveable across games**.

This is a multi-phase arc. This doc is the living plan; each phase ships as one
or more tested rounds (data-first, per the project's "content is data" rule),
green suite + push after each.

## The keystone idea: one Worldcraft layer, many clients

George asked for both **magical** and **non-magical** world change, governed by
consistent **rules**. That is the tell: don't scatter more ad-hoc tile edits.
Build ONE validated, persistent **world-mutation layer** — the rules for "what
can become what, at what cost, by whom" — and make every actor a *client* of it:

```
           ┌──────────────────────────────────────────────┐
           │   worldcraft: the mutation ruleset + ledger   │
           │  set_terrain / build / damage / clear (valid, │
           │  costed, PERSISTED as sparse edits over gen)  │
           └──────────────────────────────────────────────┘
             ▲          ▲            ▲            ▲        ▲
       spells (M2)  workers (M4)  player UI (M5) DM/dm_api  legacy
                                                 (existing) (earthworks/
                                                            giants/flood/
                                                            resource_nodes
                                                            fold IN)
```

Today the codebase already mutates tiles in several places (resource_nodes
depletion, earthworks digging, giants smashing, flood, tile_damage → rubble).
M0 unifies these under one ruleset + a **persisted edit ledger**, so a change
made by a spell, a mason, or the player obeys the same rules and survives saves
identically. Everything else becomes tractable once this exists.

## Design principles

1. **Content is data.** Spells, schools, spell-lists, reagents, enchant recipes,
   magic items, mutation rules, buildable structures, blueprint palettes → JSON.
   New content = JSON + validator pass. Mechanics are code; catalogues are data.
2. **The engine disposes.** Costs, gates, validity, and persistence live in code,
   never in prompts. Fully playable on `--provider heuristic`; no per-tick LLM.
3. **One mutation chokepoint.** All tile/structure changes route through
   `worldcraft`, which validates against the rules, charges the cost, writes the
   edit ledger, and emits the load-bearing event beat. No more ad-hoc edits.
4. **Symmetry of means.** A tile becoming farmland is the same *operation*
   whether a druid casts it or a farmer tills it — different *cost/gate/actor*,
   same validated mutation + persistence. That is the "consistency" George wants.
5. **Reversible where sensible; persistent always.** Edits ride the save; some
   are reversible (regrow, repair), some permanent (terraform). The ledger is the
   single source of truth restored on load.
6. **Files < 500 lines**; split modules before exceeding. Round-trip test every
   new persisted subsystem.

## Phases (M0 keystone first, then breadth)

- **M0 · Worldcraft foundation.** A validated, costed, PERSISTED tile+structure
  mutation API over a rules table (`data/worldcraft/mutations.json`): what
  terrain/structure can become what, the resource/skill/mana cost, the actor
  gate. A sparse **edit ledger** on the world that rides the save and re-applies
  over the generated map on load. Fold the existing ad-hoc mutations
  (earthworks/giants/flood/resource_nodes/tile_damage) onto it. *The keystone.*
- **M1 · Magic depth.** Spell **schools** + **tiers/levels**; per-**caster-type**
  spell lists, casting **requirements** (components/slots/favor/mana), and
  distinct **learning routes** (wizard tome→spellbook, cleric prayer/favor,
  sorcerer innate, druid grove, buy from a mage guild, discover from legend).
  Vastly expanded spell catalogue in data. Spellbook/known-spells persistence.
- **M2 · World-altering spells.** Spells that call M0: stone-shape / move-earth
  (terraform), wall-of-stone / fabricate (build), disintegrate / shatter
  (destroy a wall/part of a building), plant-growth (grass→forest), control-water
  (flood/part), create-object. Telegraphed like bosses where destructive.
- **M3 · Magic-item crafting + imbuing.** An **enchant/imbue** mechanic (base
  item + reagents/runes/essences + recipe + skill/spell → a magic item with
  equip-bonuses / charged use-effects); a much larger magic-item **range** in
  data (wands, staves, rings, amulets, charged foci, talismans, enchanted
  gear); reagent economy.
- **M4 · Guilds + worker build economy.** A **Mage/Enchanters' Guild** that
  teaches enchanting, sells reagents, buys/sells magic items, and whose members
  craft them in the production loop. Workers (miner/forester/mason/farmer) gather
  via the M0-consistent rules and **build** — settlements physically grow/repair
  through worldcraft.
- **M5 · Player build/terraform tool.** A specialized pop-up **planner**: a grid
  canvas where the player paints terrain + places structures from a palette,
  gated by skill/mana/resources, with preview → commit through worldcraft. Edits
  persist in-save.
- **M6 · Blueprint library (cross-game).** Save a design (a placed pattern of
  tiles + structures) to a persistent library that survives across saves AND
  games (the `dm_library` model), loadable into the planner to stamp.

## Existing substrate (from research — filled in as agents report)

_Magic (surveyed):_ `data/spells.json` (24 spells) → `Spell` dataclass →
`SPELL_REGISTRY` in `engine/spells.py`. Schema: `name, mana_cost, damage, heal,
range, status_effect, duration, area, concentration, classes[]` — **no school /
tier / requirements today** (unknown JSON keys are silently ignored, so adding
them is non-breaking). Casting is deterministic + **player-centric** (`cast()`
always acts on `engine.player`; away-heroes via `acting_as`), mana-gated,
`spells_known` on `metadata`. **Zero LLM in the cast path** — NPC "cast" is a
cosmetic ranged reskin (`combat_system._resolve`), so nothing is lost on
heuristic. Quick-cast: `engine/quick_spells.py` (slots on metadata, keys 1–5).
- **Learning today:** auto-grant ALL class-tagged spells on first access
  (`starting_spells_for`); tomes (`use_effect.teach_spell`); scrolls
  (`use_effect.spell`, one-shot). No level-up/trainer learning yet.
- **World-altering today:** only `fireball`/`shock` — HARDCODED by `spell.id` in
  `cast()`. But the primitives exist + are save-persisted: `engine/tile_damage.py`
  (`damage_radius`, `add/clear_rubble`, `set_terrain` flips, materials/HP),
  `engine/surfaces.py` (ignite/pour/electrify/flood, DOS2 spread), `flood`,
  `earthworks` (player already digs mountains → grass), `world/structures.py` +
  `module_packs._install_structures` (stamp a whole structure). `bosses.py` shows
  the telegraph→detonate pattern for destructive AoE.
- **M1/M2 integration:** add `school`+`tier`+`requires` to the dataclass +
  `_build_spells`; a `can_learn(char, spell)` chokepoint (called from
  `starting_spells_for` + `item_use` tome path + `leveling.check_level_up`); split
  `classes` (eligibility) from a new class→spell-list grant table; replace the
  hardcoded fireball/shock branches with a **data-driven `world_effect` block**
  in `cast()` dispatching to the tile_damage/surfaces/set_terrain/build primitives
  (this is where M2 spells call M0). Note the current overworld-only zone guard.
- **Persistence:** all caster state is `metadata` (rides the save wholesale, no
  `save_load.py` change); `tile_damage`/`surfaces` already round-trip. `SAVE_VERSION=3`.
- Tests to mirror: `test_spells`, `test_quick_spells`, `test_spell_panel`,
  `test_surfaces`, `test_castle_cast`.
_Crafting/items (surveyed):_ ONE flat `Item` dataclass (`items/item.py`) — every
category is the same struct; "magic" is emergent from 4 static channels:
`equip_bonuses` (passive while worn, summed by `effects._gather_bonuses`),
`use_effect` (on-use payload dispatched by `engine/item_use.py`), `damage_kind`
(element), and `metadata` flags. **No enchant/imbue mechanic exists anywhere.**
Items in `data/items/*.json` (merged by id, ~69 today); recipes in
`data/recipes.json` (11, zero magic). `Item.to_dict/from_dict` round-trips every
field → all item magic persists for free.
- **Recipe schema** (`items/crafting.py`): `output_id, output_qty, ingredients,
  gold_cost, required_property` (a Location property like `"forge"`), `skill` (XP
  target, **NOT a level gate**). `can_craft` = ingredients + gold + station. **No
  skill-level requirement today.**
- **M3 integration:** (a) magic-item CRAFTING = pure JSON (new recipes whose
  `output_id` is a magic item + a new station property like `"enchanting_table"`
  + `skill:"enchanting"`); for TIERED crafting add an optional `min_skill` field
  to `Recipe` checked in `can_craft`. (b) ENCHANT/IMBUE = the ONE new subsystem —
  a small `items/enchanting.py` + `data/enchantments.json` that MUTATES the item
  instance in place (merge into `equip_bonuses`, adjust `damage_kind`, stamp
  `metadata["enchantments"]`), because the "produce fresh, consume base" recipe
  model structurally can't do in-place upgrades; persistence is automatic. Give
  enchanted instances a distinct identity so `inventory_ops.can_stack` won't merge
  them (it already compares equip_bonuses/use_effect/metadata). (c) bigger range =
  JSON in items + `loot_tables.TIER_LOOT` + `data/shop_catalogs.json` (wizard cat).
- **Guild trade of magic** = hook the existing NPC production loop: add
  `enchanter` profession → `enchanting` skill → `enchanting_table` workstation in
  `data/production.json` + magic recipes → `production_loop._work` makes them,
  `_arbitrage` caravans them, `shop._stock_from_surplus` shelves them. The
  `ambition_effects.masterwork` hook is the template for "special NPC stocks a
  special item."
- **Economy:** `shop.py` (catalogs `data/shop_catalogs.json`, faction/market/stock
  pricing), `market.py` (4 indices incl. `arcana`), `production_loop`+`production`
  (settlement stores, recipe = a production step). Validator (`items/data_validate`)
  checks recipe/shop ids but NOT `damage_kind`/`use_effect`/`equip_bonuses` keys —
  add that as the magic surface grows (would've caught the dead `temp_stat`
  payload in `item_use.py`). Fix `temp_stat` while there.
_World alteration (surveyed — the M0 crux):_ `TerrainType` is a hardcoded Enum
(13 members: GRASS/FOREST/MOUNTAIN/WATER/ROAD/BUILDING/CAVE/SWAMP/FARMLAND/RUBBLE/
SCORCHED/BRIDGE), **not** data-driven — extending it touches satellite tables
(renderer glyphs, `tile_damage.TILE_MATERIAL/BASE_HP`, `surfaces.COMBUSTIBLE`,
`flood.FLOODABLE`, `dm_api._EDITABLE_TERRAIN`).
- **The chokepoint exists but is under-used:** `WorldMap.set_terrain(x,y,type)`
  is the intended single writer and fires a `register_tile_callback` bus (P10.0) —
  **which has ZERO consumers today (idle).** Only 4 systems route through it
  (`tile_damage`, `flood`, `giants`); ~15 BYPASS it with direct `terrain[y][x]`
  writes (`resource_nodes`, `farming`, `town_gates`, `colosseum`, `deepdelve`,
  `dm_api`, earthworks-interior + all worldgen).
- **Persistence:** the full terrain grid is snapshotted (`save_load.py:103/254`) —
  so ANY terrain edit persists regardless of path. Sparse overlays (`tile_damage`,
  `surfaces`, `flood`, `resource_nodes`, `farms`, `town_gates`, `structures`,
  `dm_state`) round-trip via their own `to_dict/from_dict`.
- **Structures:** `data/structures.json` letter-grid schema (`W`→BUILDING, `.`→
  floor, `D`→door, `>`/`<`→stairs, `T/B/C/…`→furniture, `G/L/S`→puzzle) is the
  STRUCTURE LINGUA FRANCA — used by authored content, the DM (`define_structure`),
  the cross-game Legendarium (`dm_library/structures.json`), AND `module_packs`.
  `StructureBuilder.build/_build_level` parses grid→Interior (one-directional — no
  Interior→grid serializer yet).
- **Destroy/build today:** `tile_damage` (walls→RUBBLE, forest→grass, mountain→
  grass, bridge→water; `damage_radius` is the AoE spell entry), `giants`
  (smash+nightly rebuild), `earthworks._dig` (player digs mountains→grass — the
  only non-magical player terraform), `homestead` (claim/staged-repair a derelict
  home). The **DM layer** (`dm_api`: `edit_terrain` brush w/ `_protected_region`
  safety, `add_building`, `define_structure`; budget 12/day, charter-checked) is
  the de-facto world-edit API but DM-only + budgeted + bypasses `set_terrain`.
  **No Location/structure DELETE exists anywhere; no player build verb.**
- **⚠ Persistence GAP (blocks M5):** `engine.interiors` is REBUILT from scratch at
  world init and is ABSENT from the save — only *which* interior the player stands
  in is saved. So breaches + homestead furniture don't durably persist. **A real
  player building tool must add interiors to the save.**
- **M0 architecture:** a thin `engine/worldcraft.py` facade over `set_terrain`
  taking `(x, y, new_type, source, reason)` — validates against a
  `data/worldcraft/mutations.json` ruleset (what→what, cost, actor gate), charges
  cost, writes the beat, and drives the now-live callback bus (interiors/minimap/
  FOV invalidation). Reuse `tile_damage.MATERIALS/BASE_HP` as the shared effort
  model (a spell's fire multiplier vs a worker's swings). Migrate the ad-hoc
  writers onto it incrementally. Reuse `dm_api._protected_region` as the safety
  check. Add a `remove_location` for demolition. Keep the terrain-grid snapshot
  persistence (free); add interior persistence for M5.
_Guilds/workers/economy (surveyed):_ "Guild" = two unrelated things today:
`GuildSystem` (player QP→rank ladder, on `player.metadata`) and `GuildHallSystem`
(guilds as PLACES — 2 halls, recruit/train). **Nothing ties guilds to production
or trade.** The economy has two clocks: per-turn cosmetic (`activities.py` — a
gatherer at its workplace mints +1 raw/16 performs into the nearest settlement
store) and nightly abstract (`production_loop.run_day` — gatherers +3/day into
the store, crafters consume `inputs_of`→goods; `_arbitrage` caravans; `_consume`
eats food → shortages → radiant quests). Stores → `shop._stock_from_surplus` →
shelves.
- Profession = building kind (`building_types.profession_of_kind`) else
  class→skill (`bonds.CLASS_TEACHES`)→profession (`production.json`). `production.py`
  is PURE DATA — new professions/recipes index automatically. Skills: the 12-skill
  lattice (`data/skills.json`); gathering tiers gate on level.
- **Workers DON'T touch real nodes today** — mining/woodcutting are abstract mints;
  only farming mutates real tiles (grass→FARMLAND). Player Z-gathering is the only
  real resource_node interaction (feeds the player, not stores). mine/sawmill/dock
  building kinds are catalogued but UNPLACED by worldgen.
- **M4 architecture (mostly DATA):** (a) magic guilds/enchanting — add
  `enchanter`→`enchanting` to `production.json` professions + `rune_table`
  workstation, a 13th `enchanting` skill, an `enchanter`→`enchanting` `CLASS_TEACHES`
  row, a `sanctum` building kind, an arcane raw (`arcane_dust`/`mana_crystal`) +
  magic recipes → the nightly loop makes+trades them for free; a `MageGuildSystem`
  mirroring `ProductionSystem` keyed on `hall_id` (members from
  `guildhalls.roster`), guildmaster catalog via `shop._category_for_npc`. (b)
  workers BUILD — add a build phase to `production_loop.run_day` (or a
  `ConstructionSystem`): consume store timber/stone (homestead's `WOOD_IDS`/stone
  vocab) → change tiles (`farm_manager.ensure_plots`, `fortify.fortify`) or stamp a
  new building (`town/lots.py`+`town/stamp.py`) via the M0 worldcraft layer. New
  `mason` profession = data rows.
- **Persistence:** the to_dict/from_dict + `engine_setup` construct + `save_load`
  two-table registration is the whole contract. New Locations/tiles persist for
  free (world+map save); only in-progress projects need new state (homestead rides
  `player.metadata`/`location.properties` — the zero-code model).
_UI/persistence (surveyed):_ GUI is a `gui.mode` string state-machine. Two
pop-up kinds: (a) read-only numbered overlays (`_OVERLAY_MODES` + `menu_mode_key`)
and (b) **stateful interactive panel objects** — the template for the planner:
a class with `__init__(engine)` (holds cursor/state), `handle_key(event)->bool`,
`draw(target, rect)`; wired via 4 touchpoints (gui slot, `show_X` opener setting
`mode`, a draw gate in `_render`, an input gate in `handle_event`). Cite
`shop_panel`/`crafting_panel`.
- **M5 grid/cursor precedent:** `ui/battle_screen.py` is the structural template
  — float camera, `world_to_screen`/`screen_to_world`, per-tile rect draw, an
  ARMED-click place-and-commit (`move_arm`), a selection ring. It's a standalone
  blocking screen, so PORT its camera/click/preview into a kind-(b) panel that
  draws a ghost grid over the live map. `InputHandler._pixel_to_tile` converts a
  mouse pixel → world/zone tile (reuse for cursor). `targeting.py` is the on-map
  reticle model.
- **Save/load:** `engine/save_load.py` (`SAVE_VERSION=3`) — register new state via
  a subsystem `to_dict/from_dict` (construct in `engine_setup.py`, add one key to
  `_serialize_engine` + the restore tuple list) OR park it on `player.metadata`
  (zero save-code, the homestead model). **Terrain edits persist AUTOMATICALLY** —
  `world.map.terrain` is saved wholesale, so any `WorldMap.set_terrain` terraform
  is save-safe with no code. `tile_damage`/`StructureBuilder` are the `to_dict`
  templates (dicts keyed `(x,y)` → `[[x,y,val]]`).
- **M6 cross-game exportable library:** mirror `engine/dm_library.py` EXACTLY — it
  writes `data/dm_library/*.json` (env-overridable via `LLM_RPG_DM_LIBRARY`,
  gitignored), `record_*` with dedup+cap+atomic write, and `load_into_registries()`
  at startup (`engine_setup.py:130`) so creations from one game appear in every
  future game. `STRUCTURES` is already such an inheritable registry. A
  `blueprint_library.py` writing `blueprints.json` there is portable JSON — export
  = copy the file. `bones.py` reuses the same root as a second example.
- **M5/M6 architecture:** (A) `ui/build_planner.py` kind-(b) panel (grid cursor +
  `plan` dict, ghost preview over live map, commit → M0 worldcraft); (B) committed
  terraform auto-persists, committed structures via a small `player_builds`
  subsystem or `StructureBuilder`; the in-progress plan on metadata/subsystem;
  (C) `blueprint_library` mirroring `dm_library`.

## M0 detailed spec (the first build rounds)

The research validates the keystone: `WorldMap.set_terrain` is the chokepoint (+
an idle callback bus), terrain persists free (grid snapshot), and `tile_damage`'s
material/HP model is the shared "effort" backbone. M0 ships in small rounds:

**M0.1 · `engine/worldcraft.py` + `data/worldcraft/mutations.json` (core).** A
pure-ish mutation facade over `set_terrain`:
- `mutations.json` — a rules table keyed by id, each `{from, to, labor?, magic?}`
  where `labor` = `{skill, tool?, resources?, effort}` and `magic` =
  `{tag}` (e.g. earth/nature/water/fire). A `means` absent ⇒ that means can't do
  this change. Seed ~12 rules: clear-forest, till-soil, level-mountain,
  grow-forest, raise/clear-wall, clear-rubble, pave-road, flood/drain, scorch,
  regrow.
- `rule_for(from,to)`, `allowed_targets(from, means)`, `can_mutate(engine,x,y,to,
  means,actor) -> (ok, reason)` (rule exists for means + from matches + in-bounds
  + not `protected()` [reuse `dm_api._protected_region` logic] + actor meets the
  labor gate: tool held, skill level, resources in inventory), and
  `mutate(engine,x,y,to,means,actor,charge=True) -> (ok, msg)` (validate → consume
  labor resources → `set_terrain` → `[Realm]`/`[Build]` beat → callbacks fire).
  Magic mana stays the spell system's job; worldcraft just applies + charges labor.
- Validator `check_worldcraft` (terrain names valid, skills/tools/items resolve),
  wired into `items/data_validate`. Tests: `tests/test_worldcraft.py`.
- Persistence: FREE (terrain grid snapshot). No `save_load` change.

**M0.2 · Adopt + activate.** Route `earthworks._dig` and `resource_nodes` depletion
through `worldcraft.mutate` (proving one chokepoint); register a tile callback that
invalidates FOV / interior-footprint state on change (activating the idle bus).
`remove_location(engine, loc)` for demolition (clear footprint + drop interior).

M1–M6 then build on this: M2 spells set `world_effect:{worldcraft:{to,...}}`; M4
workers/masons call `worldcraft.mutate(...,means="labor")`; M5's planner commits a
plan as a batch of `mutate` calls; all obey ONE ruleset.

## Open design questions (resolve during M0/M1)

- Caster resource model: keep the single **mana** pool, or add **prepared
  slots** (wizard/cleric) vs **innate** (sorcerer) vs **favor** (cleric)? Lean:
  mana stays the universal currency; caster *type* changes learning + gating +
  which lists are available, not the spend model (keeps combat + `quick_spells`
  intact). Revisit if it feels flat.
- Terraform scope: bounded to owned/claimed land + wilderness, never inside a
  settlement's protected core without ownership (avoid griefing the town gen).
- Blueprint portability: a design references structure/tile IDs; loading in a
  game that lacks a referenced module degrades gracefully (skip/placeholder).

## Status

- [~] M0 Worldcraft foundation — **M0.1 DONE** (`engine/worldcraft.py` +
  `data/worldcraft/mutations.json` + validator + `tests/test_worldcraft.py`);
  M0.2 (adopt existing mutators + activate the callback bus + `remove_location`)
  pending.
- [~] M1 Magic depth — **DONE**: `Spell` gains `school`/`tier`/`requires`/
  `world_effect`; tier-1-only starting spells; `can_learn` gate;
  `learn_new_spells` on level-up + tome `teach_spell`; catalogue 23→43 across
  schools/tiers/casters; spellbook shows tier+school. (Remaining flavour: cleric
  prayer-learning & sorcerer-innate distinctions are future polish.)
- [~] M2 World-altering spells — **DONE**: `engine/spell_world.py` dispatches a
  spell's `world_effect` (`worldcraft`/`tile_damage`/`surface`); 8 new spells
  (Stone Shape, Wall of Stone, Plant Growth, Conjure Water, Blight, Disintegrate,
  Earthquake, Firestorm); pure world spells target the faced tile, overworld only,
  protected ground resists. `tests/test_spell_world.py`. **M2b** (George): NPCs +
  away-heroes cast world spells too — `spell_world.ambient_shape` +
  `engine/ambient_magic.py` (a nearby druid grows a woodland, a warlock blights, a
  mage raises a wall); the overworld guard is now caster-relative. (Future polish:
  fold the legacy hardcoded fireball/shock into `world_effect`; reticle targeting.)
- [~] M3 Magic-item crafting + imbuing — **DONE**: `items/enchanting.py` +
  `data/enchantments.json` (in-place imbue: 8 enchantments over
  equip_bonuses/damage_kind/metadata, gated on forge + `enchanting` skill +
  reagents); `min_skill` on recipes for tiered magic crafting; reagent items
  + craftable magic items (amulet_of_warding, mage_ring) + magic recipes; K-panel
  enchant rows. `tests/test_enchanting.py`. (Future: a dedicated enchanting-table
  station + wands/charged foci in M4's guild content.)
- [~] M4 Guilds + worker build economy — **DONE**: `engine/construction.py`
  (`ConstructionSystem.run_day` — settlements with a builder clear rubble/scorched
  scars via `worldcraft`, so sacked towns rebuild); an `enchanter` profession +
  `sanctum` building kind + reagents/magic-items buyable at the wizard shop bring
  magic into the economy. `tests/test_construction.py`. (Future: masons stamp NEW
  buildings; a dedicated Mage-guild store keyed on hall_id.)
- [ ] M5 Player build/terraform tool
- [ ] M6 Blueprint library

_Research launched 2026-07-18; plan drafted; substrate sections pending agent
findings, then M0 begins._
