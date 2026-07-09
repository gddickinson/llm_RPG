# LLM-RPG — Session Log

## 2026-05-17 — Major expansion: independent fully-functional game

**Goal:** Transform llm_RPG (v1) into a standalone, expansive, fully-functional locally-runnable game. Bring in the best ideas from `llm_RPG_2` and `autonomous_world` without making this a fork of either.

### Pre-existing state (snapshot)

- ~5,900 LOC across `engine/`, `world/`, `characters/`, `llm/`, `ui/`
- Two oversized files violating 500-LOC rule: `engine/game_engine.py` (1566), `ui/gui.py` (1104)
- Ollama-only LLM integration (no fallback if Ollama is offline)
- No save/load, no quests, no real items (items were bare strings), no skills
- Tests directory existed but contained only stubs
- pygame GUI worked, terminal UI worked

### Reference repos surveyed

- **`/Volumes/GeorgeDrive/claude_test/llm_RPG_2`** — v2 prototype: FastAPI web server, multi-provider LLM abstraction (`llm/interface.py`), typer CLI, tkinter GUI client.
- **`/Users/george/Documents/GitHub/autonomous_world`** — large autonomous world simulator: procedural world gen, biomes, D&D systems, quest boards, economy, sprite-based pygame rendering, 155 systems modules.

### Plan executed this session

**Phase 1 — Foundation**
- INTERFACE.md (project navigation map)
- SESSION_LOG.md (this file)
- LLM provider abstraction (`llm/providers/`) with heuristic fallback so the game runs without Ollama

**Phase 2 — Game depth**
- Real items system (`items/`) — `Item` class, registry, loot tables
- Quest system (`quests/`) — kill/fetch/talk/explore objectives, templates
- Save/load (`engine/save_load.py`) — JSON full-state persistence
- Skills (`engine/skills.py`) — D&D-style skill checks

**Phase 3 — Refactor**
- Split `engine/game_engine.py` into `combat_system.py`, `economy_system.py`, `dialog_system.py`, `action_router.py`, plus thinner `game_engine.py`
- Split `ui/gui.py` into `renderer.py`, `sprite_loader.py`, `hud.py`, `input_handler.py`, thinner `gui.py`

**Phase 4 — Visual & World polish**
- Procedural sprite renderer (no external PNGs needed; inspired by `autonomous_world/game/ui/sprite_loader.py`)
- Day/night visual overlay
- Biome-based procedural world generation

**Phase 5 — Tests + docs**
- Unit tests for items, quests, save/load, combat, world gen
- Updated README + ROADMAP

### Design decisions

- **Heuristic LLM fallback by default**: keeps the game playable for anyone without Ollama, while still benefiting users who have it.
- **JSON saves**: human-readable, easy to debug, no schema lock-in.
- **No new heavy dependencies**: kept the stack at pygame + requests + (optional) anthropic/openai. No FastAPI server (kept simpler than llm_RPG_2).
- **Procedural sprites over PNG assets**: no asset pipeline, fully self-contained game.
- **Did NOT port**: the multiprocess NPC architecture stays as-is (existing one works); web server (overkill for local game); 3D renderer (out of scope).

### How to run

```bash
python main.py --ui gui                 # Pygame GUI (default)
python main.py --ui terminal            # Terminal mode
python main.py --provider heuristic     # No-LLM mode (default)
python main.py --provider ollama --model llama3
python main.py --load saves/quicksave.json
```

### Known issues / next steps

- See ROADMAP.md.

---

## 2026-05-17 (later) — Phase 2 expansion: bring over all autonomous_world systems

Brought across the entire high- and medium-impact wishlist from
`/Users/george/Documents/GitHub/autonomous_world`:

**Phase 1 — Foundations**
- `world/calendar.py`: 12-month/30-day calendar, 4 seasons, hour-to-time-of-day, tint multipliers per season.
- `characters/factions.py`: 8 factions with reputation tracking (-100..+100), kill-driven rep shifts, hostile pair detection, faction labels.

**Phase 2 — World feel**
- `characters/needs.py`: hunger and fatigue simulation, decay and feed/rest deltas.
- `characters/schedules.py`: per-class daily schedules (wake/eat/work/drink/sleep/patrol/pray/play).
- `world/encounters.py`: `EncounterManager` spawns wolves / bandits / goblins / wandering trolls in wilderness tiles, with cooldown and FOV-aware spawn positions.
- Heuristic provider rewritten to honor schedules and urgent needs (starving/exhausted NPCs break routine).

**Phase 3 — Economy depth**
- `engine/banking.py`: deposit/withdraw gold at temple/shop locations.
- `items/crafting.py`: recipe registry, ingredient + gold cost, forge-gated weapons. 6 starter recipes.

**Phase 4 — Spaces**
- `world/interiors.py`: indoor mini-maps for tavern/forge/shop/temple with furniture and NPC spots.
- `quests/quest_board.py`: tavern bulletin board, browse + accept posted quests.

**Phase 5 — Social**
- `characters/companions.py`: 3-member party, recruit by relationship ≥30, auto-follow and attack adjacent hostiles.
- `engine/dialog_trees.py`: branching dialog node graphs for tavernkeeper / merchant / guard / bard / cleric.

**Integration**
- `world.get_location_at()` now returns the innermost (most specific) location so banking and quest_board work inside the village.
- Engine `advance_turn()` ticks needs, runs encounter spawn, updates companions.
- Combat hooks faction reputation deltas through `on_defeat`.
- World generator tags locations with `type` properties (tavern/forge/temple/shop) and a `forge` flag.

**Tests** (10 new files, 50 new tests; total now 107 — all pass)
- test_calendar.py, test_factions.py, test_needs_schedules.py
- test_encounters.py, test_banking.py, test_crafting.py
- test_interiors.py, test_quest_board.py, test_companions.py
- test_dialog_trees.py

**Docs**
- INTERFACE.md, README.md, ROADMAP.md rewritten to reflect all new systems.

All source files remain under 500 LOC.

**Death popup (added near end of session)**
- Player defeat in combat now sets `engine.player_dead` (instead of immediately calling `end_game`) when a GUI is attached.
- `GameGUI` enters a `"death"` mode and overlays a centered popup with `[R] Restart` and `[Q] Quit` options. Restart rebuilds the engine in-place.
- Terminal mode is unchanged (falls back to `end_game` on death so the loop exits).
- 4 new tests in `tests/test_death.py` cover the flag, no-shutdown-with-GUI, and terminal fallback.

### Refactors during Phase 6
- Pulled `initialize_demo_game` + `create_default_player` + `_upgrade_item_string` out into `engine/demo_setup.py` to keep `game_engine.py` under 500 LOC.
- Pulled preset NPCs (Goren / Durgan / Melody / Karim / Gorkash) out of `characters/npc_manager.py` into `characters/npc_presets.py`.

### Did NOT port (out of scope, may be added in Bundles B/C)

- Religion / divine system, vegetation/foraging, astronomy
- Warfare / sieges, multi-year history sim, 3D renderer, networked multiplayer

---

## 2026-05-17 (continued) — Bundle A: Player depth

Three-bundle expansion plan agreed (A: player depth, B: world breadth,
C: NPC richness). Bundle A delivered in this session.

**Start menu + character creator (`ui/start_menu.py`, `ui/character_creator.py`)**
- Title screen with New Game / Load Game / Quit; arrow-key navigable.
- New Game branches to Quick Start (default warrior) or Customize.
- Multi-step creator: name → race (with stat bonuses) → class (with starting gear preview) → stats (4d6 keep best 3, re-roll on R) → confirm.
- Load Game lists saves from `saves/`.
- Wired through `main.py` (`--no-menu` flag added) and `GameEngine(player_spec=...)`.

**Equipment slots (`characters/equipment.py`)**
- 6 slots: weapon / armor / shield / amulet / ring / boots.
- `equip()`, `unequip()`, `equipped_weapon`, `total_armor`, `weapon_damage` helpers.
- Combat system now prefers equipped items over inventory scan.

**Spells + mana (`engine/spells.py`)**
- 7 spells: magic_missile, fireball, frost_ray, heal, bless, shock, poison_dart.
- Each has mana_cost, damage/heal, range, optional status_effect+duration.
- `SpellSystem.cast()` checks mana, range, target validity; integrates with status_effects.
- Wizards/sorcerers/clerics/etc. start with class-appropriate spells.
- Slow mana regen each turn via `rest_recover_mana`.

**Status effects (`characters/status_effects.py`)**
- poisoned (1 dmg/turn), paralyzed (skip turn), blessed (+1 atk), cursed (-1 atk), frightened, stunned.
- `apply_effect`, `has_effect`, `tick_effects`, `can_act`, `attack_damage_modifier`.
- Engine.advance_turn ticks all characters' effects.
- Action router skips paralyzed NPCs' turns; combat damage modified by attacker's status.

**Tests (33 new tests across 4 files)**
- `tests/test_equipment.py`, `tests/test_spells.py`, `tests/test_status_effects.py`, `tests/test_character_creator.py`.
- 144 total tests pass.

### Coming next (Bundle C)

- **Bundle C (NPC richness)**: schedule-driven movement that actually walks NPCs to their target locations, NPC families, gossip in dialog, multi-year history sim.

---

## 2026-05-17 (continued) — Bundle B: World breadth

**Larger map**
- DEFAULT_MAP_WIDTH/HEIGHT bumped to 60×40 (was 30×20).
- World generator places a second settlement (Riverside Hamlet) in the SW quadrant on maps ≥50×30, with three buildings (Inn, Wheelwright's Shop, Hamlet Chapel) and a connecting road to Oakvale.
- Three new preset NPCs: Esra (innkeeper), Brother Anselm (priest), Tova (wheelwright).

**Weather (`world/weather.py`)**
- 6 weather types: clear, cloudy, rain, fog, snow, storm.
- Per-season distribution biases the roll (snow in winter, storms in summer, etc.).
- Visibility multiplier (0.5–1.0) for renderer / encounter range.
- Rolls every 4 game-hours; serializable.

**Foraging (`world/foraging.py`)**
- `ForageManager.forage()` picks an item from terrain-keyed drop tables.
- 2-day cooldown per tile.
- Notifies the quest manager on item acquisition (FETCH objectives).

**Procedural dungeons (`world/dungeon.py`)**
- BSP-lite room placement + carved corridors.
- `engine.enter_dungeon()` checks player is on CAVE tile, generates and caches the dungeon, populates it with monsters and loot.
- `engine.exit_dungeon()` returns the player to the overworld.

**Engine integration**
- `WeatherSystem` ticks each turn.
- `enter_dungeon` / `exit_dungeon` / `forage` / `current_weather` added to `GameAPIMixin`.

**Tests (18 new tests across 4 files)**
- `tests/test_weather.py`, `tests/test_foraging.py`, `tests/test_dungeon.py`, `tests/test_world_breadth.py`.
- 162 total tests pass.

---

## 2026-05-17 (continued) — Bundle C: NPC richness

**Schedule-driven movement (action_router)**
- `_resolve_location_target()` resolves keywords ("tavern", "forge", "home", "village", "shop", "temple", ...) to actual location coordinates.
- Falls back to direct name match. If the NPC has a `home_location` matching the keyword's location type, prefer that one; otherwise pick the nearest.
- NPC already at its target now correctly stays put instead of bouncing in random directions.

**Families (`characters/families.py`)**
- Static registry: spouse / siblings / parents / surname per preset NPC.
- Goren (Oakvale Tavern) is married to Esra (Riverside Inn). Melody is Goren's sister. Durgan and Tova are dwarven siblings.
- `family_of(npc_id)` and `relation_to(a, b)` helpers.

**Gossip (`characters/gossip.py`)**
- Static gossip pool of 8 lines (rumors about troll, mountains, river, etc.).
- `gossip_for(npc, engine)` composes lines from: family ties, recent event-log lines mentioning other NPCs, and one filler static line.
- Dialog system appends a gossip line in `_append_quest_prompts`.

**History sim (`world/history_sim.py`)**
- 5-event pre-game simulation drawn from 8 templates: bandit raids, plagues, troll attacks, festivals, druid blessings.
- Each event has faction reputation impact applied to the player.
- Plants a Ruined Keep (2x2 building) in the NE wilderness.
- Two lore lines surface in the player's starting event log.
- Wired into `engine/demo_setup.py`.

**Tests (12 new tests across 3 files)**
- `tests/test_families_gossip.py`, `tests/test_history_sim.py`, `tests/test_npc_movement.py`.
- 179 total tests pass.

### Bundle plan complete

A, B, C all delivered:
- **A**: start menu + character creator, equipment, spells, status effects.
- **B**: bigger world, second settlement, dungeons, weather, foraging.
- **C**: schedule-driven movement, families, gossip, history sim.


---

## 2026-07-09 — v2 development begins (branch `v2-development`)

Full audit + game-design research (OSRS, Stardew, Qud, LLM-NPC games) produced
`DEVELOPMENT_PLAN.md` (phases P0 Repair → P5 Polish). New illustrated README
with headless-rendered screenshots (`docs/img/`). Improvement now proceeds in
small tested rounds, one plan item per round.

**Round 1 — P0.1 save/load data loss (fixed).**
`Character.to_dict()` omitted `metadata` (XP, faction rep, bank, mana, spells,
status effects), `equipment`, and `symbol`; `_rebuild_character` never restored
them — every F9 load silently stripped the player's equipped gear and progress.
Save format v3 now round-trips character metadata + equipment and engine-level
weather / forage cooldowns / companions, with pre-v3 saves still loading.
`metadata` promoted to a real `Character` dataclass field.
New: `tests/test_save_full_state.py` (6 regression tests). Suite: 253 tests, all pass.

**Round 2 — P0.1b remaining engine state (done).**
Dungeons gained `to_dict`/`from_dict` (terrain, rooms, spawned flag — so
cleared dungeons don't re-populate); `ShopManager` catalogs persist (sold
stock stays sold); saving inside a dungeon or building now restores the player
there, with return positions. Quest boards were confirmed derived state (filter
on persisted quest status) — no serialization needed. +3 round-trip tests.

**Round 3 — P0.2 unreachable shop (fixed).**
The shop hotkey was S, but S is consumed by move-down earlier in
`_handle_play_input`, so the entire shop UI (211-line panel + buy/sell
economy) was dead code. Shop now opens on **B** (barter); help overlay and
README updated. New `tests/test_input_bindings.py` drives the input handler
with synthetic key events: S must move (never open shop), B must open the shop
with an adjacent merchant, plus a full end-to-end ShopPanel buy (gold spent,
item added). Suite: 260 tests, all pass.

**Round 4 — P0.3 crafting UI (done).**
New `ui/crafting_panel.py` (K key): lists every recipe with live have/need
ingredient counts and gold cost; uncraftable recipes greyed out with the
blocking reason (missing ingredients / gold / "need a forge"); craftable-first
sort; Enter crafts via `engine.craft()`. Wired into gui mode machine + input
handler; help overlay + README updated. New `tests/test_crafting_panel.py`
(7 tests incl. end-to-end craft: herb consumed, gold paid, potion appears).
Suite: 267 tests, all pass.

**Round 5 — P0.4 companion recruit/dismiss UI (done).**
`P` key now recruits an adjacent NPC (or dismisses a party member); party
names + HP appear in the HUD status panel. The deeper blocker: relationship
only ever changed via NPC-initiated actions or combat, so the >=30 recruit
threshold was unreachable — talking now builds +2 trust per exchange
(non-hostiles only) and quest turn-in gives +15 with the giver. Companions
also unlock the existing flanking bonus, previously impossible to trigger.
New `tests/test_party_ui.py` (6 tests). Suite: 273 tests, all pass.

**Round 6 — P0.5 weather wired into gameplay (done).**
Weather was pure decoration (its visibility modifier had zero callers outside
its own test). Now: `engine.effective_visibility()` scales the NPC
awareness/LLM-processing radius; encounter spawn chance scales x(2 - vis_mod)
so fog/storm ambushes are ~1.5x likelier; storm/snow cost +1 minute per
off-road step (roads stay full speed — first gameplay reason to use roads);
night-time torch radius shrinks with visibility. New
`tests/test_weather_gameplay.py` (4 tests). Suite: 277 tests, all pass.

**Round 7 — P0.6 player hunger, light version (done).**
Player hunger now ticks with game time (NPC-only before). Hungry (>=60):
-1 attack damage; starving (>=90): -2 and 1 HP drain per 30 game-min, floored
at 1 HP — hunger weakens, never kills. Eating food feeds (heal x8 satiety),
works at full HP when hungry, and heals as before. HUD shows a Condition line
when not comfortable; a stomach-growl event fires when crossing the hungry
threshold. This makes food a real consumable — the consumption side of the
Phase 2 economy. New `tests/test_player_needs.py` (6 tests).
Suite: 283 tests, all pass.

**Round 8 — P0.7 contextual hint bar (done).**
New `ui/hints.py`: `context_hints(engine)` inspects the player's surroundings
and returns up to 3 prioritized hints — [T] talk / [F] attack / [B] barter /
[P] invite / [G] pick up / [Z] forage / [N][M] bank / [K] craft at forge /
[TAB] enter-leave-descend. Rendered as a translucent bar along the map's
bottom edge (hud.draw_hint_bar). Every previously-invisible system now
advertises itself in context. Verified live via headless screenshot
(docs/img refreshed). New `tests/test_hints.py` (7 tests).
Suite: 290 tests, all pass.

**Round 9 — P0.8 housekeeping (done). PHASE 0 COMPLETE.**
Deleted confirmed orphans: `engine/dialog_trees.py` + tests (nothing imported
it; P3 rebuilds dialog around the structured LLM protocol) and
`ui/threaded_llm_interface.py` (no importers). Removed `_archive/` from disk
(was gitignored). INTERFACE.md: fixed stale test count, documented 16
previously-missing modules (shop, game_api_mixin, projectiles, panels,
lighting, blueprints, chunked_world, ...). ROADMAP.md rewritten as a pointer
to DEVELOPMENT_PLAN.md with a phase-status table and resolved-debt list.
Suite: 286 tests, all pass.

Phase 0 (Repair) is complete: save/load integrity, shop, crafting,
companions, weather, hunger, and discoverability are all real, tested,
player-reachable systems. Next: Phase 1 — data-driven content layer.

**Round 10 — P1.1a data layer foundation: items ported to JSON (done).**
New `items/data_loader.py`: `load_data_dir()` merges `data/<subdir>/*.json`,
rejects duplicate ids, raises readable DataErrors. All 69 items generated
from the live registry into `data/items/{weapons,armor,consumables,jewelry,
misc,ammo_scrolls,books}.json` (entries carry only non-default fields);
`item_registry.py` is now a thin loader with an unchanged public API.
New `tests/test_data_content.py` (10 tests): registry integrity, migrated-value
spot checks, duplicate-id rejection, and cross-reference validation — every
item id used by recipes, loot tables, shop catalogs, forage tables, dungeon
loot, and quest rewards must exist. Engine boot smoke-verified (starter gear
identical). Suite: 296 tests, all pass. Remaining registries → P1.1b.

**Round 11 — P1.1b recipes, spells, shop catalogs to JSON (done).**
`data/recipes.json` (6), `data/spells.json` (7), `data/shop_catalogs.json`
(10 categories) — all generated from the live registries for fidelity;
`items/crafting.py`, `engine/spells.py`, `engine/shop.py` are now thin
loaders with unchanged APIs. Validation grew two new cross-reference rules:
scroll items must cast spells that exist, and spell status effects must be
in VALID_EFFECTS. Suite: 301 tests, all pass. Monsters/NPC presets/quest
templates → P1.1c.

**Round 12 — P1.1c monsters to JSON (done).**
New `data/monsters.json` + `world/monsters.py`: one template registry now
feeds both spawn systems — wilderness encounters read `encounter_weight`,
dungeon rooms read the `dungeon` flag (the troll is wilderness-only, as
before). Optional per-monster `stats` blocks override hostile defaults.
`encounters.py` lost its 40-line hardcoded template dict; `dungeon.py` uses
the shared pool. Adding a monster is now one JSON entry. +6 tests (enum
validity of class/race included). Suite: 307 tests, all pass.

**Round 13 — P1.1d NPC presets + quest templates to JSON (done). All content data-driven.**
`data/quests.json` (6 quests) and `data/npcs/{oakvale,riverside,stonepine,
hostiles}.json` (11 NPCs, split by settlement to stay under 500 lines);
`npc_presets.py` shrank 332→70 lines, `quest_templates.py` keeps its
factory-dict API. The new giver-must-exist validation caught a real
pre-existing bug: herb_gathering's giver was `cleric_01`, an id that never
existed — the quest could be accepted from the tavern board but never turned
in. Reassigned to Brother Anselm (hamlet_priest_01). +6 tests.
Suite: 313 tests, all pass.

Every content registry (items, recipes, spells, shop catalogs, monsters,
quests, NPCs) now loads from data/*.json with cross-reference validation.

**Round 14 — P1.3 unified content validator (done). PHASE 1 COMPLETE.**
New `items/data_validate.py`: `validate_all()` returns a problem list;
`python -m items.data_validate` exits 1 on failure (pre-commit friendly).
Rules span recipes, shop catalogs, forage/loot tables, monster enums,
spell effects, scroll->spell links, quest givers + objective targets
(FETCH item ids, KILL/TALK actors, DELIVER item:npc pairs), NPC enums,
relationships, and inventory-string resolvability. The validator is itself
tested against injected broken content. Suite: 315 tests, all pass.

Phase 1 complete (P1.4 module packs deferred as stretch): all content in
JSON, all cross-references machine-checked. Next: Phase 2 — the skills
progression lattice.

**Round 15 — P2.1 skills system (done). Phase 2 begins.**
New `engine/skill_progression.py` + `data/skills.json`: 8 parallel skill
tracks (mining, woodcutting, fishing, cooking, smithing, alchemy, foraging,
agility), levels 1-50 on a geometric curve (50 * 1.10^L per level — the
OSRS-shaped "last 7 levels cost as much as the first 43", verified by test).
XP lives in player.metadata["skills"], so save persistence came free.
Live XP earners wired: foraging (Z), alchemy (brew consumables), smithing
(forge recipes) — with level-up events in the log. Character sheet (C) now
shows all skill levels + progress + total level. 12 new tests.
Suite: 327 tests, all pass. Gathering nodes for mining/woodcutting/fishing/
cooking arrive with P2.2.

**Round 16 — P2.2 gathering nodes (done).**
Z is now a smart gather verb via `world/gathering.py` + `data/gathering.json`:
mining on mountain/cave edges (pickaxe; copper 1 / iron 10 / coal 20 /
mithril 35), woodcutting in forest (any axe; logs 1 / oak 12 / yew 30),
fishing at shorelines (rod; trout 1 / salmon 15) — weighted toward common
tiers, per-tile regen cooldowns that persist in saves. Priority routing:
tooled node > herb foraging > tool lesson (water without a rod now teaches
fishing instead of "nothing here"). 16 new material items incl. tools, ores,
bars, logs, raw/cooked fish; general store sells pickaxe/rod/axe; new
cooking + smelting recipes train cooking/smithing via Recipe.skill; hint
bar announces "[Z] mine here" or the missing tool. All 8 skills now have
live XP earners. 9 new tests; validator covers gathering data.
Suite: 331 tests, all pass.

**Round 17 — P2.3 production chains + gear durability (done).**
The ore->bar->weapon chain is complete: swords cost 2 iron bars (was 3 coins),
bronze sword added at the copper tier, iron shields take a bar. New
`engine/durability.py`: uncommon+ weapons wear 1/landed hit (200 max), armor
+ shields 1/hit absorbed (150); at 0 the item is [BROKEN] and contributes no
damage/armor/enchant bonuses until repaired at a forge (~15% of value scaled
by damage taken). Inventory shows wear labels; the K panel lists repair
entries at the forge; durability rides item.metadata so persistence is free.
Commons never degrade (worry-free starter gear). 8 new tests; 3 legacy
recipe tests updated to the bar economy. Suite: 339 tests, all pass.

**Round 18 — P2.4 economy balancing (done).**
Two structural exploits closed: (1) shop restock existed but had zero
callers — `refresh_all_if_due()` now runs daily from advance_turn (checked
every 30 turns); (2) merchants had unlimited gold, allowing infinite
sell-loops — each catalog now carries a finite purse (100g + wares/4),
shown in the shop UI. Selling drains the purse and is refused when the
merchant is broke; your purchases refill it (gold circulates); restock
resets stock and purse; purse persists in saves. New
`tests/test_economy_balance.py` (6 tests). Suite: 345 tests, all pass.

**Round 19 — P2.5 collection log (done).**
New `engine/collection_log.py` + O-key overlay: four categories (items,
foes bested, recipes crafted, places found), each shown as got/possible
against the live data registries. An inventory+location scan runs every
turn from advance_turn, so pickups, purchases, gathering, loot, and quest
rewards all register regardless of code path; kills only count when the
player lands the killing blow; first-time discoveries surface as
"[Collection] Discovered: Oakvale Tavern" / "First Wolf defeated!" events.
Stored in player.metadata -> persists through saves. 8 new tests.
Suite: 353 tests, all pass.

**Round 20 — P2.6 skilling pets (done).**
New `engine/pets.py` + `data/pets.json`: 8 named cosmetic pets (Rocky the
pebble golem, Acorn the squirrel, Bubbles the otter pup, Cinder the kitchen
imp, Ingot the iron sprite, Fizz the bottled wisp, Bramble the hedgehog,
Zephyr the dust sprite). Every gather/craft/forage action rolls
1/(400 - level*6), floored at 1/60 — higher skill, better odds. The newest
pet visibly trails one tile behind the player (small bobbing critter drawn
by the renderer, hooked on pre-move position for a correct one-step lag).
No duplicates; jackpot announced with fanfare; pets counted in the
collection log (n/8); ownership persists via metadata. 8 new tests.
Suite: 361 tests, all pass.

**Round 21 — P2.7 regional achievement diaries (done).**
New `engine/diaries.py` + `data/diaries.json`: Oakvale / Riverside /
Stonepine diaries, each easy/medium/hard with 3-4 themed tasks. Design win:
tasks are pure predicates over state the game already tracks (collection
log kills/items/crafts/places, skill levels, quest status) — zero new event
plumbing. Completed tiers auto-claim from the turn loop with fanfare:
gold, reward items, and a stacking 5%-per-tier purchase discount at that
region's merchants (matched by home_location keywords; verified not to
leak across regions). J opens the diary overlay with live checkboxes.
Claims persist via metadata; validator checks all diary targets.
9 new tests. Suite: 370 tests, all pass.

**Round 22 — P2.8 shortcuts + earned teleports (done). PHASE 2 COMPLETE.**
New `engine/travel.py`. Agility shortcuts: level 15 clambers over mountain
tiles, level 25 swims across water — every blocking terrain edge on the map
becomes a potential shortcut, costing +3 minutes and granting Agility XP;
walking into a wall below the level teaches the requirement. Teleports
(U key): Oakvale always available; Riverside/Stonepine unlock by claiming
their diary easy tier (the promised diary reward); non-home destinations
cost a 15g toll; all share a 4-game-hour cooldown persisted in metadata.
9 new tests. Suite: 379 tests, all pass.

Phase 2 (progression lattice) complete: 8 skills with earners, gathering
tiers, production chains, durability sink, balanced economy, collection
log, pets, diaries, shortcuts + teleports. The game now has a genuine
progression treadmill. Next: Phase 3 — the LLM as a gameplay pillar.
