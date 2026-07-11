# LLM-RPG — INTERFACE.md

Top-level navigation map for the codebase. Read this **before** opening source files.

## Architecture Overview

```
llm_RPG/
├── main.py                     # Entry point
├── config.py                   # Centralized config + system prompts
├── INTERFACE.md                # This file
├── SESSION_LOG.md              # Development progress log
├── README.md                   # User-facing docs
├── ROADMAP.md                  # Future plans
├── requirements.txt
│
├── engine/                     # Game engine — core game loop, turn logic
├── characters/                 # Characters, NPCs, factions, schedules, party
├── world/                      # World, map, calendar, biomes, interiors
├── items/                      # Item system + crafting
├── quests/                     # Quest system + quest boards
├── data/                       # JSON content — items, recipes, spells, shops, monsters, quests, NPCs
├── llm/                        # LLM interface + providers
├── ui/                         # GUI (pygame) and terminal UI
├── saves/                      # Saved games (created at runtime)
├── tests/                      # Unit tests (290+)
```

## Module Index

### engine/battle/ — Phase 17 tactical layer

- **`battle_data.py`** — loaders over `data/battles/*.json`: unit archetypes, formations, matchup RPS + terrain, fortifications, P17.6a grid-terrain cover (`terrain_cover`); all content, no hardcoded stats.
- **`battle_unit.py`** — P17.2 grid pieces: `Soldier` (light token, +P17.4c `move_accum` speed budget) + `Squad` (owns soldiers, ONE morale bar, order/formation/commander, `speed`; rout on morale threshold); round-trips to dict.
- **`battle_field.py`** — P17.2 battle grid: own terrain (P17.6a passable COVER terrains + `cover_at`), WALL/GATE as HP structures breaching to rubble lanes, soldier occupancy, squad/team registry; round-trips to dict for mid-battle saves; P17.6c capture-point objectives (`add_objective`/`team_counts_near`/`captured_team`).
- **`battle_flow.py`** — P17.3 flow fields: multi-source BFS distance field per team (O(map)); soldiers step the gradient toward the enemy and through breaches.
- **`battle_ai.py`** — P17.3 group AI (ported colosseum brain): focus-fire target select, self-contained d20 strike, role movement (archers kite), squad morale/rout; P17.4c `step_toward` greedy push-into-contact when the centroid flow is blocked; P17.6b `nearest_struct` for siege engines homing on walls; P17.13 `charge_attack`/`_shove` (charging cavalry & beasts trample loose foot, shatter on braced spears); P17.11 `_position_mods` (flank/rear/gang-up/surround bonuses via `battle_facing`).
- **`battle_orders.py`** — P17.5 the commander's verbs as behaviour: `advance_intent` maps an order (charge/hold/fall_back/move/focus_fire) to a soldier's out-of-reach intent; `is_focus` concentrates fire; objective-type scaffold. The session + `pick_target` read it.
- **`battle_session.py`** — P17.3 deterministic tick loop; `run_headless(max_ticks)` runs squads to a result (same shape as the resolver); P17.4c multi-step movement by unit `speed` (`MAX_STEPS` cap); P17.5 order-driven movement (`_order_move`: hold/retreat/goto/advance); P17.6b siege battering (rams hammer an adjacent wall to a breach before shooting) + P17.6d ranged bombardment (artillery lobs at a wall from `SIEGE_RANGE`); P17.6c capture-point victory (`_update_objectives`; `over`/`result` end on a seizure); P17.13 `_charge_melee` (charge/overrun momentum in melee).
- **`battle_facing.py`** — P17.11 pure facing/arc geometry: 8-dir `DIRS`, `face_toward`, `arc` → front/flank/rear; feeds the flank/rear to-hit & damage bonuses in `battle_ai`.
- **`battle_scenario.py`** — P17.4 staged set-pieces from `data/battles/scenarios.json`; `build_field(id)` expands one into a tickable `BattleField` (shared by the screen and the tests).
- **`battle_resolve.py`** — P17.1 headless Lanchester auto-resolver: `Army`/`Unit`/`Fort` + seeded `resolve(attacker, defender, terrain, is_siege, seed)`; defence-reduced melee, RPS+speed-softened ranged, cavalry charge, anti-cavalry spears, wall-gated siege with breaches. Deterministic; doubles as the off-screen faction-battle resolver.

### engine/ — Core game logic

- **`game_engine.py`** — `GameEngine`; the thin orchestrator: state, start/end, delegates (438 lines).
- **`engine_setup.py`** — `build_subsystems(engine)`: every gameplay system constructed in dependency order (P14.1 split from __init__).
- **`turn_pipeline.py`** — `run_turn(engine)`: the per-minute pipeline — needs, encounters, companions, conflicts, surfaces, floods, hazards, dying, law, pets — plus the nightly stack; block order is load-bearing (P14.1 split from advance_turn).
- **`demo_setup.py`** — `initialize_demo_world()`, `create_default_player(spec)`.
- **`action_router.py`** — Routes NPC actions to specialized handlers.
- **`combat_system.py`** — Player vs NPC vs NPC combat, damage, defeat, loot, faction rep on kill.
- **`economy_system.py`** — Buy/sell/trade/give between characters.
- **`dialog_system.py`** — Player↔NPC dialog flow (routes through dialog_protocol for LLM providers).
- **`dialog_protocol.py`** — Structured JSON dialog contract: whitelisted actions, engine-validated execution.
- **`npc_memory.py`** — Per-NPC memory: recency×importance×relevance retrieval, verbatim dialog log, nightly reflection → opinions.
- **`secrets.py`** — Gated NPC secrets from `data/secrets.json`; locked secrets never reach the prompt (injection-proof).
- **`persuasion.py`** — `/persuade` `/intimidate` `/deceive` social checks; LLM or dice adjudication, day-long lockouts, haggle tokens.
- **`heart_events.py`** — Affinity-threshold scenes from `data/heart_events.json`; authored outlines, LLM-rendered prose, perks.
- **`topics.py`** — `TopicJournal`; keywords heard anywhere become askable topics (Y-key journal), per-NPC authored answers.
- **`director.py`** — `WorldDirector`; one nightly call emits structured events (rumor/shortage/caravan/sighting/feud) the systems act out.
- **`player_deeds.py`** — Rolling deeds ledger + presence digest; NPCs react to kills, quests, gear, level.
- **`llm_budget.py`** — Cost discipline: NPC action cooldowns, monster exclusion, greeting cache.
- **`guild.py`** — `GuildSystem`; quest points → ranks (Member/Veteran/Champion) with radiant/teleport/party perks.
- **`tutorial.py`** — `TutorialManager`; teach-by-doing steps, hint-bar lessons, one-way boat departure.
- **`legends.py`** — Relic pickups reveal authored legends; Legends section of the Y journal; gossip citations.
- **`defeat.py`** — Failure-as-story defeat outcomes: robbed / left for dead / slain.
- **`dying.py`** — P12.4 Dying & Wounded: 0 HP → Dying 1–4 with per-turn flat recovery checks; stabilize = +1 Wounded + gentle story beat, Dying 4 = the full defeat table; people (not monsters) are KO'd into robbable bodies that wake overnight with grudges.
- **`item_use.py`** — `use_item(engine, name)`: every on-use payload (scrolls, tomes, manuals, potions, remedies, P12.3 drinks, food); `transmute_item` (P13.1: any carried item → 40% value in gold, mana-gated, [T] in the I-panel); identity-first `_remove_one`.
- **`food.py`** — P12.5 food economy: 2-turn chew delay gates attacks after eating, combo food bypasses it, the Hearty Brew overheals + curses; freshness decays nightly (stale = half heal + poison risk), hearths re-bake carried rations.
- **`combat_depth.py`** — P12.7: concentration (one sustained spell; damage forces d20+CON vs max(10,dmg)), soft cover on the shot line (-10%/-25% hit, carried on projectiles), BG3 weapon actions as weapon data (Cleave/Topple/Pommel Strike/Lacerate, SHIFT+V, once per rest).
- **`ranged.py`** — `shoot_ranged(engine, ...)`: bow/crossbow/thrown fire with ammo, aim, chew gate, true LOS (split from game_api_mixin).
- **`skill_actions.py`** — P12.8 combat verbs on the graded core: Trip (SHIFT+T), Demoralize (SHIFT+I, 10-min per-target immunity), Feint (SHIFT+B), Battle Medicine (SHIFT+H, burns a bandage, once/day/patient); degree-sensitive outcomes both ways.
- **`bones.py`** — P12.13 NetHack bones: true deaths snapshot site/gear/slayer to the Legendarium root; new campaigns roll 1/3 to raise a flying ghost of the fallen guarding their (70% haunted, curse-on-equip) gear.
- **`wounds.py`** — P15.9 body-part health: 5 parts, severity 0–3; serious hits break a bone (head→checks, arms→attack, legs→step time, torso→HP ceiling); crippled limbs fester (P12.12); knit by sleep/camp/Battle Medicine; state on player.metadata.
- **`infection.py`** — P12.12 the infection race: dirty wounds (stabilize/ashore/crit-bleed) start it; nightly infection +28 vs immunity +21×rest-quality; Battle Medicine subtracts by degree (+cleric assist); infection 100 = fever crisis into the dying state, immunity 100 = clean.
- **`bonds.py`** — P12.11 the bond ceremony: /bond shares a drink (once per NPC) minting spendable trust; /spend secret (past gates) · skill (+150 XP lesson) · join (recruit at 20 + 12×level-gap); faction behavior thresholds gate trade/recruitment/petty-bounty forgiveness.
- **`ransom.py`** — P13.2 ransom & rescue: SHIFT+G hoists a KO'd body (6 pack slots, slow steps); set down beside a cleric = rescue (gold, +rep, warm memory) or the fence = ransom (level-priced gold, −rep, witnessed bounty, grudge); mid-carry wakes give the benefit of the doubt.
- **`law.py`** — `LawSystem` (P12.9): per-settlement bounty ledger fed by break-ins/assault/robbery; adjacent guard + local bounty opens the 1-5 confrontation menu (pay / jail with skill-XP cost / bribe / one graded talk / resist); walking away shelves, never clears. Part 2: stolen flags (`mark_stolen`/`is_stolen`/`fence_sale` — honest merchants refuse, the fence pays 60% after 3 unseen break-ins), hearth laundering, witness outfit memory (guards only confront a matching outfit — armor changes are disguises).
- **`tactics.py`** — Opportunity attacks, SHIFT+move disengage, SHIFT+F shove.
- **`faction_ticker.py`** — Daily dice-resolved faction events; strength/stores drive encounters, shortages, rumors; repelled raids spawn a visible straggler.
- **`npc_conflict.py`** — `NPCConflictSystem` (P7.1): guards fight hostiles they can see, hostiles raid civilians; `[Clash]` events near the player; the player's duel is never stolen; overworld-grid NPCs only.
- **`retaliation.py`** — `RetaliationSystem` (P7.2): deep hostile faction rep → warning rumor, then level-scaled bounty hunters converge on the player; nightly check, persisted, escalation ladder per faction.
- **`squad_tactics.py`** — P7.3 positional helpers shared by companions/guards/packs: `surround_step` (fan out around targets), `flank_tile` (+2 flanking spot), `player_focus_target` (focus fire), `path_step` (BFS with greedy fallback), `greedy_step`.
- **`disease.py`** — `DiseaseSystem` (P8.2): outbreaks/contagion/immunity from `data/diseases.json`; state in character metadata; player symptom drain (never kills); the right remedy cures via item use; nightly tick.
- **`pantheon.py`** — `PantheonSystem` (P8.4): five gods from `data/pantheon.json`; deeds build favor (player_deeds hook), SHIFT+P prayer at shrines/temples, favor-funded miracles (heal/bless/fortune/cure/insight), nightly omens at deep favor.
- **`market.py`** — `MarketSystem` (P8.5): tâtonnement price indices per category (arms/provisions/goods/arcana); purchases/sales move prices, nights drift them home; multiplies buy AND sell in shop pricing; persisted.
- **`doors.py`** — `DoorManager` (P9A.1): door policies from `data/doors.json` (homes locked, shops night-locked, taverns open); key/lockpick/SHIFT+TAB-force paths; forcing is noisy and remembered; dawn resets; persisted.
- **`furniture.py`** — P9A.2: E beside interior furniture — beds rest (+30% HP/day), hearths cook, altars pray, shelves surface rumors, chests/barrels rummage; flavor for the rest; cooldowns in player.metadata.
- **`trespass.py`** — `TrespassSystem` (P9A.4): private homes + after-hours shops; witnessed trespass costs rep/relationship/memory; forced entry is a crime — guards converge on the alert, repeat offenses reach the P7.2 bounty ladder.
- **`presence.py`** — P9A.7: NPCs within an enterable footprint are INDOORS — hidden from the street, shown inside as the same entities at zone-local spots; `npc_adjacent_to_player` is THE adjacency check (talk/hints/melee/barter).
- **`carry.py`** — carry capacity (George): slot-based pack, 18 + 2 per STR modifier; `can_carry`/`full_message` enforced at pickup/forage/gather/harvest/shop/rummage/chests.
- **`targeting.py`** — `TargetingSystem` (P8.7): [ ] cycle / click-to-target locks with range + true LOS; auto-refresh each turn; reticle + hint bar; bow and attack spells fire at the lock.
- **`tile_damage.py`** — `TileDamage` (P10.2): sparse tile HP + materials (stone resists fire, wood burns); walls crack → RUBBLE (a breach is a second door); fire scorches; persisted.
- **`surfaces.py`** — `SurfaceLayer` (P10.3): sparse fire/oil/water per-tile surfaces; fire burns occupants + tiles and spreads; oil pools chain-ignite; water douses; per-turn tick; persisted; DM-paintable. P14.2a: blood pools from serious wounds (conduct, never burn) + `electrify` — lightning races through connected water/blood (shock spell triggers it), zapping occupants, fading back to water.
- **`bosses.py`** — P15.6 boss set-pieces: data `boss` block gives telegraphed AoE (mark a tile, blast it next turn) via `boss_tick`, and once-only HP-threshold phases via `boss_on_damaged` (enrage/flood/electrify/summon); Giant Warlord, Tyrant of the Depths, Wisp Queen.
- **`giants.py`** — Giants + labor (P10.5): `is_giant`/`giant_tick` (smash walls to deep rubble, hurl boulders — maims the player, real splash deaths) on the conflict scan; nightly `run_night_labor` (crews clear rubble by buildings, masons rebuild breached walls, scorched ground regrows).
- **`flood.py`** — `FloodSystem` (P10.6): cellular flood frontier over low ground, dammed by rubble/buildings/mountains; recedes restoring original terrain; occupied tiles never flooded; storm-burst chance; persisted.
- **`earthworks.py`** — P10.6: the E-key ground fallback (clear rubble, then pickaxe-dig adjacent mountains — 4 swings tunnel to grass, trains Mining); `footprint_to_perimeter`/`sync_breaches`/`close_breach` breach mapping shared by entry-sync and the night masons.
- **`rest.py`** — Enter-to-sleep at inns; dawn wake, restoration, day-summary overlay; P12.6 tiers: 15g private room grants well_rested (+10% XP), 5g bunk; routes outdoor Enter to camping.
- **`camping.py`** — P12.6: camp anywhere outdoors — burns provisions (supplied = real night, unsupplied = doze), 25% wilderness ambush at dawn; `night_beat` = the DM's guaranteed `[DM]` dream after every sleep (dm_autonomous.night_scene overrides).
- **`dm_api.py`** — `DMApi`; the Dungeon Master's typed/validated/budgeted command set + notebook + scheduled beats.
- **`dm_digest.py`** — `build_digest(engine)`; the DM's compact JSON view of the table.
- **`dm_bridge.py`** — `--dm-bridge` file bridge: digest export + inbox bundle polling + result receipts.
- **`dm_autonomous.py`** — `AutonomousDM`; one planning call per game-day, campaign notes, ≤6 charter-checked commands.
- **`dm_modules.py`** — Atomic adventure bundles: prevalidate → install → rollback-on-failure.
- **`dm_library.py`** — The Legendarium (P6.7): DM definitions persist to `data/dm_library/` with provenance and load into the registries at every boot; slain DM creations enter `legendarium.json`. `record_definition` / `load_into_registries` / `record_legend` / `legendarium_tail`; root overridable via `LLM_RPG_DM_LIBRARY`.
- **`module_packs.py`** — Module packs (P1.4 + P14.2b): authored campaign packs install at new-game start; packs ship monsters/items/spawns/quests/beats AND structures (charter-checked, budget-free, Legendarium-inherited); structures-only packs valid.
- **`memory_manager.py`** — Event history + `on_event` observer hook (feeds the topic journal).
- **`save_load.py`** — JSON full-state save/load.
- **`skills.py`** — D&D-style skill checks; P12.1 degrees of success: `check()` → `CheckResult` with `Degree` (crit ±10 margins, nat 20/1 shift one degree) — lockpicking, forcing, persuasion, shove, and forage all route through it.
- **`leveling.py`** — XP curve, auto level-up with HP/stat increases.
- **`skill_progression.py`** — 8-skill lattice from `data/skills.json`; geometric curve, `add_skill_xp()`, levels 1–50.
- **`collection_log.py`** — `CollectionLog`; unique items/kills/crafts/places vs registry totals (O-key overlay).
- **`pets.py`** — `PetSystem`; rare skilling-pet rolls from `data/pets.json`, follower trails the player; P12.14 loyalty 1–20 (SHIFT+Z treats +1, nightly neglect −1, 0 walks away), apport fetch at 12+.
- **`diaries.py`** — `DiaryManager`; regional task tiers from `data/diaries.json`, auto-claim rewards + shop discounts (J-key overlay).
- **`travel.py`** — `TravelSystem`; terrain crossings (delegates to traversal) + diary-unlocked teleports with toll/cooldown (U-key menu).
- **`traversal.py`** — `TraversalSystem` (P11.1): per-terrain rules from `data/traversal.json` — wade at shores, graded swim/climb checks (d20 + skill level + ability mod vs DC raised by pack load and exhaustion, bad fails hurt), swamp/forest slogs + weather tax per step; fatigue on the needs scale, reset by sleep.
- **`hazards.py`** — P11.2: `flow_at` (rivers run along the longer water axis; lakes are slack), per-turn deep-water struggle (`water_hazard_tick`: fail → swept downstream + escalating drown damage; at 1 HP washed ashore minus one item), `tumble` off rock faces on bad climb fails; `[!]` telegraphs + hint-bar warning. P13.3 breath clock: (1+CON mod)×4 turns of free diving before the struggle starts, hint-bar countdown. P11.3 aids: carried gear (`equip_bonuses` climb/swim via `traversal.aid_bonus`), water_walking status skips checks and struggles, swimmers_grace +5, heavy-pack "drop or sink" telegraph.
- **`spells.py`** — `SpellSystem`, spell registry, mana mechanics.
- **`settings.py`** — PUX.4a persisted player options (Event log / Hint bar / Mini-map / Sound / Map zoom) in player.metadata; `get/set/cycle_setting`, `enabled`; the `,`-key settings overlay reads these.
- **`banking.py`** — Deposit/withdraw gold at temples/shops.
- **`npc_process.py`** / **`npc_process_manager.py`** — Multiprocess NPC AI (optional).
- **`player_actions.py`** — Player-driven actions (pickup/drop/use/attack/move); weather travel penalty.
- **`game_api_mixin.py`** — `GameAPIMixin`; thin engine wrappers: party, interiors, dungeons, spells, banking, crafting, `effective_visibility()`.
- **`trade_info.py`** — PUX.2 pure helpers behind a merchant deal: `item_report`, `compare_to_equipped`, `price_factors`/`factors_line` (why a price is what it is), `is_junk`/`junk_items`, `affordable_qty`; the shop panel renders these.
- **`shop.py`** — `ShopManager`; per-merchant catalogs, faction-aware prices, persistence; P12.10: stock-elastic pricing (5%/unit deviation, daily restock heals), regional category factors from `data/settlement_economy.json` (arbitrage), H-key haggle minigame (patience 3/day, graded Persuasion, crit fails cost reputation).
- **`effects.py`** — Effective AC / stat / damage bonuses from worn equipment (broken gear contributes 0).
- **`durability.py`** — Gear wear on uncommon+ weapons/armor; break, repair at forge, `durability_label()`.
- **`projectiles.py`** — In-flight arrows/bolts + spell projectiles with per-turn ticks.

### characters/ — Characters, NPCs, social systems

- **`character.py`** — `Character` dataclass (player + NPC).
- **`character_types.py`** — Class/race/alignment/trait/status enums.
- **`npc_manager.py`** — NPC creation + lifecycle.
- **`npc_presets.py`** — Preset NPCs loaded from `data/npcs/*.json`; `make_npc(id)`, `all_presets()`.
- **`factions.py`** — `Faction` enum, reputation tracking, on-defeat hooks.
- **`schedules.py`** — Daily routines per NPC class.
- **`needs.py`** — Hunger, thirst, and fatigue simulation; P12.3 exhaustion ladder: `exhaustion_level` 0–6 from tired/starving/parched/sleep-debt with rung penalties (checks → speed → attacks → HP cap → collapse), two-track sleep (naps clear fatigue, only real beds clear debt), `player_needs_turn`/`run_player_night` engine hooks, `drink()`.
- **`status_effects.py`** — Poison / paralyzed / blessed / cursed / etc. with duration ticks; P12.2 valued conditions: Frightened N (−N to every check, decays 1/turn), persistent_damage (flat DC 15 to end), prone/blinded/off_guard with `check_penalty`/`attack_penalty`/`ac_penalty` queried by skills + combat.
- **`equipment.py`** — Worn weapon / armor / shield / amulet / ring / boots slots; P15.10: two-handed rules (a two-hander stows the shield; no shield while two-handed) + matched-set bonuses (`set_bonus`, +1 AC per matched armor/shield/boots piece).
- **`companions.py`** — `CompanionManager`; party recruitment, follow-and-fight; P15.5 depth: /order follow|hold|flee, authored travel banter (data/banter.json), camp watch (halves ambush), bond-gated personal quests.
- **`families.py`** — Static family ties for preset NPCs.
- **`gossip.py`** — Gossip lines pulled from family ties + recent memory events.
- **`homes.py`** — `HomeSystem` (P9A.3): explicit occupant binding at world start — preset homes kept, guards to the watchtower, blueprint npc_class residents for unowned buildings, derelict flags; `occupants_of`/`owner_of`/`is_derelict`.

### world/ — World, map, calendar, locations

- **`world.py`** — `World`; high-level world state; `get_location_at` returns innermost.
- **`world_map.py`** — `WorldMap`, `TerrainType`; tile grid, movement, FOV; `_is_flier` flight bypass (P11.4) for water/mountain blocking.
- **`location.py`** — `Location`, `LocationFactory`.
- **`biome.py`** — `Biome` enum and biome→terrain mapping.
- **`calendar.py`** — `Date`, `Season`; 12-month calendar, day-night clock, season tints.
- **`world_generator.py`** — `WorldGenerator`; procedural world. Two settlements (Oakvale + Riverside Hamlet) connected by road on 60×40+ maps.
- **`interiors.py`** — Building interior mini-maps; multi-level stacks (P9A.5): tavern/inn bedroom lofts, shop/forge cellars, twinned stair tiles (`add_upper_floor`/`add_cellar`).
- **`blueprints.py`** — Building footprint blueprints used by the world generator.
- **`chunked_world.py`** — `WorldStreamer`; off-map region transitions (chunk streaming); NPCs are region-scoped (each region caches its own cast; companions cross with the player).
- **`encounters.py`** — `EncounterManager`; wilderness monster spawns (weather-scaled chance).
- **`monsters.py`** — Monster templates from `data/monsters.json`; terrain-filtered encounters + dungeons; `build_monster()`.
- **`weather.py`** — `WeatherSystem`; rain/fog/snow/storm tied to season, with visibility multipliers.
- **`astronomy.py`** — P8.1 pure sky math from `data/astronomy.json`: seasonal day length, solar intensity, two moons (Lunara 28d / Thal 47d) with phases, `moonlight()`, `is_conjunction()` + `announce_conjunction()` omen nights (brighter clear nights, ×1.5 encounters).
- **`farming.py`** — `FarmManager` (P8.3): farm locations claim FARMLAND fields; fallow→planted→growing→mature→harvested by season with solar-intensity ripening; Z-key player harvest (wheat + XP); autumn farmer harvest fills village stores; persisted.
- **`foraging.py`** — `ForageManager`; pickable herbs/berries from forest tiles with cooldown.
- **`gathering.py`** — `GatheringManager`; mining/woodcutting/fishing nodes from `data/gathering.json`, tier level gates, tool checks.
- **`dungeon.py`** — `Dungeon`, `generate_dungeon`, `populate_dungeon`; BSP-lite procedural dungeons accessible from cave tiles.
- **`event_filter.py`** — display-side event-log filter: categorize by prefix/content, per-player verbosity (quiet/normal/verbose, SHIFT+L), hide ambient overworld noise while indoors; `filtered_recent` feeds the HUD (memory keeps everything).
- **`discovery.py`** — P15.11 fog of war: per-turn VISIBLE set (shadowcaster) folded into a persistent EXPLORED mask (player.metadata, save-safe); `actor_hidden` (renderer), `can_witness` (event-log gate, fresh LOS); reveal by walking / map items (use_effect.reveal) / Farsight spell.
- **`fov.py`** — P8.6 recursive shadowcasting: `compute_fov`, `has_line_of_sight`, `zone_fov` (dungeon fog-of-war), `overworld_los` (ranged-shot gating; buildings/mountains block).
- **`structures.py`** — `StructureBuilder` (P9.1): themed multi-level structures from `data/structures.json` (grid-string levels, twinned stairs, dark levels, inscriptions, populate-on-first-visit natives); ships the Ruined Keep; populated-set persists.
- **`history_sim.py`** — Pre-game history: faction shifts, ruined keep, lore lines, themed relics per event.
- **`tutorial_island.py`** — The starter isle grid + instructor cast (P4.4c).

### items/ — Item system + crafting

- **`item.py`** — `Item` dataclass; types, rarity, effects.
- **`data_loader.py`** — `load_data_dir()`; merges `data/<subdir>/*.json` content files (Phase 1 data layer).
- **`data_validate.py`** — `validate_all()` / `python -m items.data_validate`; cross-reference checks for all content.
- **`item_registry.py`** — thin loader over `data/items/*.json` (69 items); `create_item()`, `item_by_name()`.
- **`loot_tables.py`** — Drop tables by enemy class.
- **`crafting.py`** — `craft()` + recipes loaded from `data/recipes.json` (forge-gated, ingredients).

### quests/ — Quest system

- **`quest.py`** — `Quest`, `QuestObjective`, `QuestStatus`, `ObjectiveType`.
- **`quest_manager.py`** — Tracks quests, event hooks for progress.
- **`quest_templates.py`** — Quests loaded from `data/quests.json`; `create_quest(id)`.
- **`quest_board.py`** — `QuestBoardManager`; tavern bulletin board.
- **`radiant.py`** — `RadiantQuestGenerator`; morning task quests from shortages/sightings, level-scaled, board-posted.

### llm/ — LLM integration

- **`llm_interface.py`** — `LLMInterface`; facade over providers.
- **`providers/`** — Pluggable backends.
  - **`base.py`** — `LLMProvider` ABC.
  - **`heuristic.py`** — Rule-based default; honors NPC schedules + needs.
  - **`ollama.py`** — Local Ollama HTTP.
  - **`anthropic.py`** — Anthropic Claude.
  - **`openai_provider.py`** — OpenAI.

### ui/ — User interfaces

- **`gui.py`** — `GameGUI`; pygame main window + death popup mode.
- **`start_menu.py`** — Title screen with New Game / Load / Quit; routes into the character creator.
- **`character_creator.py`** — Multi-step character creation flow + `CharacterSpec`, race/class data.
- **`renderer.py`** — `MapRenderer`; map tiles + sprites + lighting; `_render_zone()` draws dungeons/interiors.
- **`sprite_loader.py`** — Procedural sprite generation + P15.1 PNG tileset pipeline: data/tiles/<name>/ via config.TILESET_NAME or LLM_RPG_TILESET, per-image graceful fallback to procedural; contract in data/tiles/README.md.
- **`crafting_panel.py`** — `CraftingPanel`; K-key recipe browser with have/need counts, crafts via `engine.craft()`.
- **`controls.py`** — PUX.3 the controls reference as audited data (single source of truth for the F1/? help): `CONTROLS`, `help_columns()` (two balanced columns that fit one screen), `documented_keys()`.
- **`hints.py`** — `context_hints(engine)`; contextual key hints (talk/barter/forage/enter/…) rendered as the HUD hint bar; a standing `[?] all controls` reminder when a slot is free.
- **`spell_panel.py`** — X-key Spellbook; cast any known spell (Enter/1–9), mana + effect readout.
- **`hud.py`** — Status, HP/XP bars, mini-map, event log, quest tracker; `draw_help_overlay` (two-column controls, PUX.3); hint bar + mini-map gated on settings (PUX.4a); PUX.4b `draw_party_panel` (companions — order + HP — in the reclaimed bottom-right).
- **`settings_panel.py`** — PUX.4a the `,`-key settings overlay (cycle Event log / Hint bar / Mini-map / Sound / Map zoom; applies zoom + mute live).
- **`dialog_input.py`** — dialog-typing key handler (split from input_handler to hold the line).
- **`input_handler.py`** — Keyboard input routing (movement, dialog, quest hotkeys, death popup).
- **`terminal_ui.py`** — Text-based UI.
- **`inventory_panel.py`** — I-key equipment + bag overlay (equip/use/drop).
- **`shop_panel.py`** — B-key two-column buy/sell overlay; PUX.2 Trading II: an inspect/compare + price-breakdown pane, Shift+Enter bulk ×5, and `J` sell-all-junk (via `engine/trade_info.py`).
- **`body_renderer.py`** — Layered character body sprites (race/class/equipment).
- **`combat_effects.py`** — Damage popups, hit flashes, death particles.
- **`lighting.py`** — Night darkness + torch/window light punches (weather-scaled).
- **`weather_overlay.py`** — Rain/snow/fog particle overlays.
- **`sound.py`** — Procedural SFX (numpy-synthesized) via event observer + weather ambience loops.
- **`battle_camera.py`** — P17.4 pure zoom/pan/LOD math for the battle screen (tile_size 8/16/32/48, float camera, world↔screen, blob_mode < 16px) + P17.4b unit-type glyph geometry (`category_shape`/`marker_points`); unit-tested headless.
- **`battle_screen.py`** — P17.4 the zoomable Battle Testbed view: a standalone pygame loop (no engine) that watches a `BattleSession` tick a scenario — terrain, soldiers-or-blobs by LOD, HUD, play/pause/step/reset; reachable from the start menu; P17.5 command overlay (TAB/click select an allied squad, C/H/F/G/M issue orders).
- **`gui_interface.py`** — Minimal GUI-facing engine interface helpers.

## Key Classes — where to find them

| Class                  | File                                |
|------------------------|-------------------------------------|
| `GameEngine`           | `engine/game_engine.py`             |
| `Character`            | `characters/character.py`           |
| `NPCManager`           | `characters/npc_manager.py`         |
| `CompanionManager`     | `characters/companions.py`          |
| `Faction`              | `characters/factions.py`            |
| `World`                | `world/world.py`                    |
| `WorldGenerator`       | `world/world_generator.py`          |
| `Interior`             | `world/interiors.py`                |
| `EncounterManager`     | `world/encounters.py`               |
| `Date`, `Season`       | `world/calendar.py`                 |
| `Item`                 | `items/item.py`                     |
| `Recipe`, `craft()`    | `items/crafting.py`                 |
| `Quest`                | `quests/quest.py`                   |
| `QuestBoard`           | `quests/quest_board.py`             |
| `Bank`                 | `engine/banking.py`                 |
| `CombatSystem`         | `engine/combat_system.py`           |
| `LLMProvider`          | `llm/providers/base.py`             |
| `HeuristicProvider`    | `llm/providers/heuristic.py`        |
| `MapRenderer`          | `ui/renderer.py`                    |
| `SpriteLoader`         | `ui/sprite_loader.py`               |

## Engine subsystems wired to the game loop

Each turn (after a player move / dialog / action):
1. `world.advance_time(1)` — calendar minute passes
2. `quest_manager.on_turn_advanced()` — SURVIVE objectives tick
3. NPC needs tick — hunger / fatigue grow
4. `encounter_manager.maybe_spawn()` — chance of wilderness monster
5. `companion_manager.update()` — party members follow / fight
6. Every N turns: NPC actions (LLM or heuristic-based, including schedules)

## Adding new content — quick recipes

- **New item**: add an entry to the matching `data/items/*.json` file (only non-default fields needed).
- **New campaign pack**: drop a module JSON (monsters/items/spawns/quests/beats, see `engine/dm_modules.py` docstring) into `data/module_packs/`; use `"anchor": "wilderness"` instead of positions; run the validator.
- **New recipe**: add an entry to `data/recipes.json`.
- **New quest**: add an entry to `data/quests.json`; post to a board via `default_boards()` if appropriate.
- **New named NPC**: add an entry to the matching `data/npcs/*.json` file.
- **New NPC class**: extend `CharacterClass` in `characters/character_types.py`; add schedule in `characters/schedules.py`; add to `CLASS_TO_FACTION` in `characters/factions.py`.
- **New action**: add handler in `engine/action_router.py`.
- **New terrain**: extend `TerrainType` + add sprite in `ui/sprite_loader.py`.
- **New monster**: add an entry to `data/monsters.json` (`encounter_weight` for wilderness, `"dungeon": true` for dungeons).
- **New LLM provider**: subclass `LLMProvider` in `llm/providers/`, register in `llm/providers/__init__.py`.

## File size policy

All source files stay **under 500 lines** (per global coding preferences). Split modules before exceeding.
