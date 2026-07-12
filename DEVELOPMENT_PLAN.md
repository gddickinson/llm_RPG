# LLM-RPG — Development Plan (2026-07-09)

A phased plan to turn the current broad-but-shallow tech demo into a rich, playable
game. Based on (a) a critical code audit of this repo, (b) research into RuneScape /
OSRS design, and (c) research into living-world RPGs (Stardew Valley, Caves of Qud,
Kenshi, Moonring) and shipped LLM-NPC games (Suck Up!, Dead Meat, 1001 Nights,
Generative Agents, Mantella).

## Thesis

The project's effort so far went into **breadth of systems and engineering hygiene**
(clean modules, 247 tests) at the expense of **wiring systems to the player and to
each other**. Several advertised pillars are unreachable or inert from the player's
seat. The fastest path to a real game is NOT more features — it is:

1. **Repair** what's built but broken/unreachable (shop, save/load, crafting, companions).
2. **Connect** inert systems into loops (weather, needs, factions, economy).
3. **Deepen** with a RuneScape-style progression lattice (skills, unlocks, collection).
4. **Differentiate** by making the LLM mechanically meaningful (secrets, persuasion,
   memory, a world director) — currently it only produces throwaway flavor text.

The unique selling point of this game is #4. Nothing else here does something a
thousand pygame RPGs don't. But #1–#3 must come first or there is no game for the
LLM to enrich.

---

## Phase 0 — Repair: make what exists real  (highest priority, ~1 week)

Audit findings that actively break the advertised game. Each fix is small; together
they transform the experience.

- [x] **P0.1 Fix save/load data loss.** *(done 2026-07-09 — save v3: metadata,
  equipment, symbol/faction, weather, foraging, companions all round-trip;
  6 regression tests in `tests/test_save_full_state.py`. P0.1b (the noted
  remainder) is now CLOSED: dungeon state + place-state and shop stock got
  their `to_dict`/`from_dict` in later rounds, structure interiors persist
  through the structures subsystem, and the last gap — QUEST BOARDS —
  landed here: `QuestBoardManager.to_dict`/`from_dict` round-trips each
  board's live `posted_quest_ids`, so radiant notices and DM-posted quests
  survive a load instead of reverting to the defaults (wired into
  `save_load`, 3 tests, suite 1836).)* `character.to_dict()` (`characters/character.py:209`)
  omits `metadata` and `equipment`; `save_load._rebuild_character` never restores them.
  On every F9 load the player loses equipped gear (it's moved out of inventory by
  `equip()`), XP, faction reputation, bank balance, mana, and known spells. Also not
  saved: party, weather, status effects, dungeon/interior state, forage cooldowns,
  quest boards, shop stock. Fix serialization end-to-end + add a round-trip test that
  asserts full player/world state equality. Add SAVE_VERSION migration stub.
- [x] **P0.1b Persist remaining engine state.** *(done 2026-07-09 — dungeons
  (terrain/rooms/spawned), current dungeon/interior + return positions, and shop
  catalogs now round-trip; quest boards proved to be fully derived state (they
  filter by persisted quest status) so need no serialization. +3 tests.)*
- [x] **P0.2 Fix the unreachable shop.** *(done 2026-07-09 — shop rebound to `B`
  (barter); help overlay + README updated; 4 regression tests incl. an
  end-to-end ShopPanel buy in `tests/test_input_bindings.py`.)*
- [x] **P0.3 Crafting UI.** *(done 2026-07-09 — `ui/crafting_panel.py`, hotkey `K`
  (R was already ranged attack); live have/need counts, forge-gated recipes greyed
  out with reason, craftable-first sort; 7 tests incl. end-to-end panel craft.)*
- [x] **P0.4 Companion recruit/dismiss UI.** *(done 2026-07-09 — `P` key
  recruits/dismisses the adjacent NPC; party members + HP shown in the HUD status
  panel. Also fixed the deeper blocker: the player had NO way to reach the ≥30
  trust gate — now conversation gives +2 relationship (non-hostiles) and quest
  turn-in gives +15 with the giver. 6 tests in `tests/test_party_ui.py`.)*
- [x] **P0.5 Wire weather into gameplay.** *(done 2026-07-09 —
  `engine.effective_visibility()` shrinks NPC awareness range in bad weather;
  encounter chance scales ×(2−vis) so fog/storm ambushes are ~1.5× likelier;
  storms/snow cost +1 min per off-road step (roads immune); night light radius
  shrinks with visibility. 4 tests in `tests/test_weather_gameplay.py`.)*
- [x] **P0.6 Player needs: light hunger wired.** *(done 2026-07-09 — player hunger
  ticks with game time; hungry = −1 dmg, starving = −2 dmg + HP drain floored at
  1 (weakens, never kills); food now feeds (heal×8 satiety) and can be eaten at
  full HP when hungry; HUD shows condition; stomach-growl warning on crossing the
  hungry threshold. Food is now a real consumable → cooking gets its consumer in
  P2. 6 tests in `tests/test_player_needs.py`.)*
- [x] **P0.7 Discoverability hint bar.** *(done 2026-07-09 — `ui/hints.py`
  `context_hints()` (pure logic, testable) + HUD bar over the map's bottom edge.
  Covers talk/attack/barter/recruit/pickup/forage/bank/craft/enter/leave, capped
  at 3 prioritized hints. Verified live via headless screenshot. 7 tests.)*
- [x] **P0.8 Housekeeping.** *(done 2026-07-09 — deleted orphans:
  `engine/dialog_trees.py` (+ its tests; P3 rebuilds dialog around the LLM
  protocol) and `ui/threaded_llm_interface.py`; removed `_archive/`; INTERFACE.md
  updated (stale 107-test count, 16 undocumented modules added); ROADMAP.md
  rewritten as a pointer to this plan with a phase-status table.)*

**Exit criteria:** a new player can, unaided, buy/sell, craft, recruit a companion,
save and load without losing anything, and discover every system via hints.

---

## Phase 1 — Data-driven content layer  (~1 week, prerequisite for scaling)

All content (items, quests, recipes, monsters, spells, NPC presets, shop catalogs)
is hardcoded Python. Every content addition means code edits, and content volume is
demo-scale: 6 quests, 6 recipes, 4 encounter monsters, 7 spells.

- [x] **P1.1a Data-layer foundation + items ported.** *(done 2026-07-09 —
  `items/data_loader.py` (`load_data_dir` merges `data/<subdir>/*.json`, rejects
  duplicate ids, clear DataError messages); all 69 items now live in
  `data/items/*.json` split by category, entries only carry non-default fields;
  `item_registry.py` is a thin loader with an unchanged API. 10 tests incl.
  cross-reference validation of recipes/loot/shops/forage/quests.)*
- [x] **P1.1b Recipes, spells, shop catalogs ported.** *(done 2026-07-09 —
  `data/recipes.json`, `data/spells.json`, `data/shop_catalogs.json`; the three
  modules are thin loaders, APIs unchanged. +5 validation tests incl. new
  cross-refs: scroll items must cast known spells, spell status effects must be
  valid.)*
- [x] **P1.1c-monsters** *(done 2026-07-09 — `data/monsters.json` +
  `world/monsters.py`; one registry now feeds both wilderness encounters
  (`encounter_weight`) and dungeon rooms (`dungeon` flag); optional per-monster
  `stats` overrides. Adding a monster = one JSON entry. 6 tests.)*
- [x] **P1.1d NPC presets + quest templates ported.** *(done 2026-07-09 —
  `data/quests.json` and `data/npcs/{oakvale,riverside,stonepine,hostiles}.json`;
  `npc_presets.py` 332→70 lines, `quest_templates.py` API unchanged. Validation
  caught a real content bug: herb_gathering's giver `cleric_01` never existed, so
  the quest was un-turn-in-able — reassigned to Brother Anselm. +6 tests.)*
- [x] **P1.3 Unified content validator.** *(done 2026-07-09 —
  `items/data_validate.py`: `validate_all()` + `python -m items.data_validate`
  CLI (exit 1 on problems). Checks recipes, shops, forage, monsters, spells,
  quests (givers, FETCH/KILL/TALK/DELIVER targets), NPCs (enums, relationships,
  inventory-string resolvability). Wired into the test suite; also
  self-tested against injected broken content.)*
- [x] **P1.4** (Stretch) A "module pack" folder convention — the ROADMAP's campaign
  packs fall out of this nearly for free. *(done 2026-07-10 —
  `engine/module_packs.py`: authored packs in `data/module_packs/*.json`
  install at new-game start through the SAME atomic prevalidate→install→
  rollback pipeline the DM uses (P6.5), with authored-content courtesies:
  no DM budget consumed, inherited definitions (Legendarium/earlier
  campaign) tolerated, and world-agnostic `"anchor": "wilderness"`
  positions resolved per generated map. Ships with "The Mire Beacon"
  starter pack (monster + relic + board quest + day-2 beat + rumor).
  Validator now checks packs (enums, giver resolvable, level-1 caps,
  allowed beats). Env `LLM_RPG_MODULE_PACKS` for isolation. 7 tests.)*

**Exit criteria:** adding an item/monster/recipe/quest = editing JSON only.

---

## Phase 2 — Progression lattice (the RuneScape layer)  (~2–3 weeks, biggest playability win)

Research takeaway: the "RuneScape feeling" is a *lattice* — many parallel skill
tracks with geometric XP curves and a dense unlock schedule, cross-feeding each other
in a closed (Ironman-style) economy. Melvor Idle proved the lattice alone carries the
feeling. This directly fixes "content exhausted in under an hour."

- [x] **P2.1 Skills system.** *(done 2026-07-09 — `engine/skill_progression.py` +
  `data/skills.json`: 8 skills (mining/woodcutting/fishing/cooking/smithing/
  alchemy/foraging/agility), levels 1–50, geometric curve base 50 · 1.10^L (last
  7 levels ≈ everything before). XP in `player.metadata["skills"]` → persists
  free. Live earners: forage→foraging, brew→alchemy, forge→smithing; character
  sheet shows per-skill levels + total. 12 tests. Mining/woodcutting/fishing/
  cooking earn XP once P2.2 adds gathering nodes.)*
- [x] **P2.2 Gathering nodes on the map.** *(done 2026-07-09 —
  `world/gathering.py` + `data/gathering.json`: Z is now a smart gather verb.
  Mining (mountain/cave, pickaxe): copper 1→iron 10→coal 20→mithril 35;
  woodcutting (forest, any axe): logs 1→oak 12→yew 30; fishing (shoreline,
  rod): trout 1→salmon 15. Per-tile regen cooldowns persist in saves; tools
  sold at the general store; hint bar teaches tool needs; cooking + smelting
  recipes train cooking/smithing via new `Recipe.skill`; 16 new material
  items. 9 tests + validator coverage.)*
- [x] **P2.3 Production chains with mandatory consumption.** *(done 2026-07-09 —
  ore→bar→weapon complete: sword now costs 2 iron bars, bronze sword added,
  iron shield takes a bar; fish→food and herbs→potions were live from P2.2/P0.6.
  New `engine/durability.py`: uncommon+ weapons/armor wear per landed/absorbed
  hit (200/150), break to zero contribution, repair at forge for ~15% of value
  scaled by damage. Inventory shows [%]/[BROKEN]; crafting panel lists repairs
  at the forge; durability rides item.metadata so saves are free. 8 tests.)*
- [x] **P2.4 Economy balancing.** *(done 2026-07-09 — restock was never wired
  (`refresh_all_if_due` had zero callers): now runs daily via advance_turn.
  Merchants have finite purses (100g + wares/4, shown in the shop UI) — selling
  drains them, your purchases refill them, restock resets them: no infinite
  sell-loop. Purse persists in saves. Buy/sell spread + data-driven stock were
  already live; repair sink from P2.3. Remaining sinks (tolls, teleports, capes)
  arrive with P2.6/P2.8. 6 tests.)*
- [x] **P2.5 Collection log.** *(done 2026-07-09 — `engine/collection_log.py` +
  O-key overlay: items / foes bested / recipes crafted / places found, each
  "got/possible" against the live registries. Inventory+place scan runs from
  advance_turn so every acquisition path counts; kills credit the player only;
  "[Collection] Discovered:" / "First X defeated!" moments in the log; persists
  via metadata. 8 tests.)*
- [x] **P2.6 Skilling pets.** *(done 2026-07-09 — `engine/pets.py` +
  `data/pets.json`: 8 named pets (Rocky the pebble golem, Bubbles the otter
  pup, …), rolled `1/(400 − level·6)` per gather/craft/forage action (floor
  1/60). Newest pet visibly trails one tile behind the player (renderer
  critter draw); no duplicates; announced with fanfare; listed in the
  collection log (n/8); persists via metadata. 8 tests.)*
- [x] **P2.7 Regional achievement diaries.** *(done 2026-07-09 —
  `engine/diaries.py` + `data/diaries.json`: 3 regions × 3 tiers × 3–4 tasks,
  all predicates over already-tracked state (collection log, skills, quests) so
  zero new event plumbing. Tiers auto-claim with fanfare: gold + items +
  stacking 5%-per-tier discount at that region's merchants (keyed by
  home_location). J-key overlay with live checkboxes; persists via metadata;
  validator covers diary targets. 9 tests. Teleport rewards land with P2.8.)* Doubles as a content tour guide.
- [x] **P2.8 Shortcuts + earned teleports.** *(done 2026-07-09 —
  `engine/travel.py`: Agility 15 clambers over mountains, 25 swims rivers —
  blocking terrain becomes shortcuts map-wide, costing +3 min and granting
  Agility XP (walking into a wall teaches the requirement). U-key travel menu:
  Oakvale free; Riverside/Stonepine unlock via their diary easy tiers, 15g
  toll (gold sink), shared 4-hour cooldown persisted in metadata. 9 tests.
  **PHASE 2 COMPLETE.**)*

**Exit criteria:** 10+ hours of self-directed progression; there is always a
near-term unlock in some track.

---

## Phase 3 — Make the LLM a gameplay pillar  (~2–3 weeks, the differentiator)

Audit: the LLM currently affects nothing — dialog is flavor text; quest offers are
string-concatenated after the reply; "memory" is a substring scan of the global event
log, not per-NPC. Research consensus from every shipped LLM game:
**engine owns truth, LLM owns voice.**

- [x] **P3.1 Structured dialog protocol.** *(done 2026-07-09 —
  `engine/dialog_protocol.py`: LLM providers return
  `{dialogue, mood, action?, action_args?}`; whitelist adjust_affinity
  (clamped ±3) / give_item (only from the NPC's REAL inventory — hallucinated
  items are no-ops) / refuse / end. Robust parsing: JSON mined from fences +
  chatter, prose degrades to plain dialogue. Prompt carries engine facts
  (inventory ids, relationship score, time/weather) + anti-sycophancy rules.
  Heuristic provider keeps the legacy path. reveal_secret arrives with P3.3,
  offer_quest with P4. 13 tests via mocked provider.)*
- [x] **P3.2 Per-NPC memory with retrieval.** *(done 2026-07-09 —
  `engine/npc_memory.py`: memories stamped with GAME time, retrieval scored
  recency (half-life 1 day) × importance × word-overlap relevance; last 10
  exchanges verbatim in `dialog_log`; nightly reflection on day change distills
  fresh memories into ≤3 durable opinions (one LLM call per NPC, or a template
  heuristically). Dialog prompt now carries retrieved memories + opinions +
  conversation history instead of the global-log substring scan. All state on
  Character.memories/metadata → saves free. 12 tests.)*
- [x] **P3.3 Secrets as gated tokens (Dead Meat pattern).** *(done 2026-07-09 —
  `engine/secrets.py` + `data/secrets.json`: 8 secrets across 6 NPCs, gated by
  affinity / quest / carried item / skill. Locked secrets NEVER enter the
  prompt (injection-proof by construction — tested with an injection attempt);
  the model gets a "deflect, don't invent" instruction + the player sees a
  "holding something back" tell. reveal_secret joined the action whitelist,
  validated against the unlocked set. Heuristic mode shares an unlocked secret
  outright once per talk, so it's a feature on every backend. Secrets seed real
  goals: troll's silver weakness, mithril depths, the ruined keep. 11 tests.)*
- [x] **P3.4 LLM-adjudicated persuasion (Suck Up! pattern).** *(done 2026-07-09 —
  `engine/persuasion.py`: `/persuade` (CHA) `/intimidate` (STR) `/deceive` (INT)
  in dialog. LLM judges the actual argument vs NPC traits/relationship/stat mod
  with `{success, reason}` (junk verdicts fall back to dice); heuristic mode:
  d20 + stat + rapport vs DC 14. Stakes: failure = −6 affinity + verb locked
  with that NPC for a game-day; success = merchant haggle token (real 20% off
  in shop pricing), frightened combat debuff, or trust. NPCs remember attempts.
  10 tests.)*
- [x] **P3.5 Affinity thresholds ("heart events").** *(done 2026-07-09 —
  `engine/heart_events.py` + `data/heart_events.json`: 6 authored scenes across
  5 NPCs (Goren 30/60, Durgan 40, Melody 30, Karim 40, Esra 30). Outline is
  authored truth; LLM re-renders it as prose with "invent nothing new" (junk
  falls back to outline). Perks: items/gold with flavor notes. Fires once,
  lowest threshold first, hooked on dialog + quest turn-in; NPC remembers the
  moment (importance 7 → shapes reflections). 10 tests.)*
- [x] **P3.6 Topic journal (Moonring pattern).** *(done 2026-07-09 —
  `engine/topics.py` + `data/topics.json`: 8 topics with per-NPC authored
  responses. Learning hooks the event-log observer, so dialog, secrets, lore,
  and heart events all teach; saying a keyword yourself does NOT (knowledge
  must be heard). Asking: heuristic mode appends the NPC's authored answer;
  LLM mode injects it as grounding ("invent nothing beyond it"). Y-key journal
  with n/8 counter. Topics chain: Goren's secret teaches silver_blade, whose
  response teaches the recipe. 10 tests.)*
- [x] **P3.7 Nightly world director.** *(done 2026-07-09 — `engine/director.py`:
  one call per game-night emits 1–3 structured events from a 5-type whitelist —
  rumor (→ gossip pool), shortage (×1.5 shop prices for a day), caravan
  (merchant restock + purse), monster_sighting (real spawn away from the
  player), feud (mutual −20 between NPCs). Invalid ids are no-ops; junk output
  and heuristic mode roll template events, so the world moves overnight on
  every backend. "[Overnight] …" morning lines; rumors surface through NPC
  gossip; state persists. Feeds P4.1 radiant quests. 11 tests.)*
- [x] **P3.8 NPCs notice the player.** *(done 2026-07-09 —
  `engine/player_deeds.py`: rolling deeds ledger (kills, quest completions,
  diary tiers; cap 12) + live-derived presence (level, wielded/worn gear,
  trailing pet). Every LLM dialog prompt carries "WHAT PEOPLE KNOW OF THE
  PLAYER" with a react-in-character instruction; heuristic NPCs comment
  outright ~35% of the time ("Word travels — they say you slew Gorkash.").
  9 tests.)*
- [x] **P3.9 Cost/latency discipline.** *(done 2026-07-09 —
  `engine/llm_budget.py`: spawned monsters NEVER get LLM minds; named NPCs get
  ≤1 LLM ambient action per 30 game-min (heuristic fallback between, both sync
  + subprocess paths); plain greetings cached 60 game-min per NPC (real
  conversation never cached); `llm_interface.call_counts` for observability.
  Anti-sycophancy rules landed in P3.1's system prompt. Remaining call sites
  are all player-initiated or once-nightly. 8 tests. **PHASE 3 COMPLETE.**)*

**Exit criteria:** playing with `--provider anthropic/ollama` is *mechanically*
different from heuristic mode: you can talk your way into secrets, discounts, quests,
and out of fights — and NPCs remember you across sessions.

---

## Phase 4 — Quests, world, onboarding  (~2–3 weeks)

- [x] **P4.1 Radiant quest generation.** *(done 2026-07-09 — `quests/radiant.py`:
  each morning 1–2 quests generate from real world state — director shortages
  become FETCH quests, sighted/spawned monsters become bounties, gathering
  templates fill in. Level-scaled rewards, posted to the tavern board with
  "[Board] New notice" events, real givers for turn-in. Cap 3 available; stale
  unaccepted notices withdrawn after 3 days (accepted ones never). Serialize
  through the quest manager. The world is never questless again. 10 tests.)*
- [x] **P4.2a Quest capabilities + 4 new handcrafted quests.** *(done 2026-07-09 —
  quest chains (`prereq_quest` hides quests until the prereq is turned in) +
  capability unlocks (`reward_unlocks`: teleport:/topic:/spell:) applied at
  turn-in. Fixed TWO dead paths: DELIVER objectives were player-uncompletable
  (now talking to the recipient hands over carried quest items — the shipped
  deliver_sword quest works for the first time), and crafting never counted
  for FETCH objectives. New quests: The Silver Edge (craft the blade),
  Roads and Rivers (explore → both teleports), Supply Run (deliver → east_shaft
  topic), The Healer's Art (chain: herbs → brew → learn the heal spell).
  9 tests.)*
- [x] **P4.2b Three more handcrafted quests — 13 authored total.** *(done
  2026-07-09 — The Cellars of Caer Aldwyn (multi-stage keep expedition:
  explore the history-sim's Ruined Keep + clear 2 bandits → warding amulet;
  pays off Melody's secret + the ruined_keep topic), The Fence (investigation
  chained off Roads and Rivers: deliver bandit-looted stolen jewelry to Karim,
  ties the bandits topic thread together), The Ballad of You (humor: get all
  three barkeeps to corroborate Melody's "artistic license"). Validator now
  accepts class-valued KILL targets. 6 tests. P4.2 complete at 13 quests.)*
- [x] **P4.3 Quest points + guild.** *(done 2026-07-09 — `engine/guild.py`:
  authored quests grant 1–3 QP (23 total across 13 quests; radiants grant
  none), awarded at turn-in with rank-up fanfare. Ranks with concrete perks:
  Member (5 QP) = +2 radiant board notices; Veteran (10) = teleport cooldown
  halved; Champion (15) = a 4th companion slot. Character sheet shows
  QP + rank. 8 tests.)*
- [x] **P4.4a Alternate-map rendering (Tutorial Island prerequisite).** *(done
  2026-07-09 — the renderer drew the OVERWORLD while the player walked
  dungeon/interior-local coordinates (an old ROADMAP bug the audit missed):
  dungeons and interiors were visually unplayable. `MapRenderer.active_zone()`
  + `_render_zone()` now draw the zone grid — themed backdrops, furniture,
  zone-local ground items, dungeon monsters (bounds-filtered), clamped camera
  for small rooms. Pixel-diff test proves the dungeon view differs from the
  overworld. 6 tests.)*
- [x] **P4.4b Zone-aware movement (Tutorial Island prerequisite #2).** *(done
  2026-07-09 — movement inside dungeons/interiors consulted the OVERWORLD
  grid: dungeon walls didn't block and overworld water invisibly blocked
  corridors. `_move_in_zone()` now enforces zone bounds, zone walls
  (mountain/water/building), doors, and character collision — with a test
  proving zone floor overrides overworld water. 6 tests.)*
- [x] **P4.4c Tutorial Island.** *(done 2026-07-09 —
  `world/tutorial_island.py` + `engine/tutorial.py`: a hand-built isle
  (grass/forest/rock/dock over water) with Old Willem, Sergeant Bors, and a
  training dummy. Six teach-by-doing steps (talk → fish → cook → eat →
  fight → sail) tracked as predicates over already-tracked state; the hint
  bar carries "[Lesson] …"; TAB departs only from the boat tile (one-way:
  cast removed, mainland placement, tutorial_done flag). Gathering became
  zone-aware to make island fishing work; encounters suppressed in zones;
  tutorial cast excluded from ambient AI. `--tutorial` CLI flag; survives
  save/load mid-lesson. 9 tests. P4.4 complete.)*
- [x] **P4.5 Regional identity — The Murkfen.** *(done 2026-07-09 — new SWAMP
  terrain (sprite, minimap, passable-but-slow: +1 min/step) and a generated
  Murkfen region in the southern lowlands. Monsters gained `spawn_terrain`
  regionality: Bog Lurker (level 3, tough) and Marsh Wisp haunt only the swamp
  — the danger pocket near safe roads — while wolves stay on the meadows.
  Swamp foraging yields rich herbs + new bogcap mushrooms → antidote recipe
  (alchemy). Validator covers spawn terrains. The three settlements already
  carry identity via diaries/quests/secrets. 7 tests. Remaining: a Murkfen
  quest mini-arc can ride P4.6's history residue.)*
- [x] **P4.6 History with residue (Caves of Qud pattern).** *(done 2026-07-09 —
  every history event now leaves a themed relic on the ground (watchman's
  signet by the keep, vigil candle at the chapel, the prince's letter at the
  forge, …; 8 relic items in `data/items/relics.json`). Picking one up reveals
  its authored legend — "[Legend] The Sack of the Watchtower: …" — which also
  teaches journal topics via the event observer. The Y journal gained a Legends
  section (found n/m, unfound show "its relic is still out there…"); NPC gossip
  cites history by year. `engine.world_history` + `legends_known` persist.
  7 tests.)*
- [x] **P4.7 Failure-as-story.** *(done 2026-07-09 — `engine/defeat.py`:
  overworld defeat rolls Robbed (~60%: wake at the nearest temple, 30% of
  carried gold gone — banked gold untouchable, so banking finally earns its
  keep), Left for Dead (~30%: 1 HP where you fell, six hours later, ravenous),
  or Slain (~10%, and ALWAYS inside dungeons/zones — the classic popup).
  Victors remember besting you. Also stabilized the test suite: three flaky
  tests fixed (death tests now force the slain roll; shared-tile relic pickup;
  gossip-priority race — the round-35 mystery flake explained), 8 consecutive
  green runs. 8 tests. **PHASE 4 COMPLETE.**)*

---

### Playtest hotfixes (reported by George)

- [x] **H1 Message-flood next to talkative NPCs.** *(fixed 2026-07-09 — the GUI
  drives NPC processing every frame (30/s) and the only gate was
  `turn_counter % INTERVAL == 0`, which stays true while standing still: every
  nearby NPC acted ~30×/sec. New `_npc_turns_due()` guard: NPCs act on the turn
  cadence, plus a 3-second wall-clock tick while idle so the world stays alive
  at a readable pace; consecutive duplicate log lines ("Goren sleeps
  peacefully.") are suppressed. 4 regression tests incl. a simulated 100-frame
  idle loop.)*

## Phase 5 — Combat depth & feel  (~1–2 weeks, interleave anytime)

The resolution math (d20 + mods vs AC, crits, flanking, damage types) is genuinely
good; the tactical layer is absent — enemies wander-or-attack, the player bump-attacks
and heal-spams.

- [x] **P5.1 Enemy AI profiles.** *(done 2026-07-09 — `behavior` flags in
  `data/monsters.json`, read by the heuristic provider: wolves howl on first
  sighting (new router action alerts same-kind packmates within 10 tiles, who
  converge on your last position); bandits/goblins/wisps break and run below an
  HP fraction (directionally AWAY, using the new `player_position` in
  world_state); the wandering troll never strays >8 tiles from its lair; the
  bog lurker lies motionless until prey comes within 3. 8 tests. Also: answered
  George's question — Tutorial Island starts via `--tutorial`; a start-menu
  entry is queued.)*
- [x] **P5.2 Spell selection UI + spell growth.** *(done 2026-07-09 —
  `ui/spell_panel.py`: X opens the Spellbook — every known spell with mana
  cost/range/effect, Enter or 1–9 casts (heals self-target, attacks resolve to
  the nearest hostile); V stays quick-heal. 8 new spells (firebolt, smite,
  entangle, drain life, regrowth, war cry, hex, frost armor → 15 total) via
  the data layer; 3 spell-teaching tomes sold by wizard-stock merchants
  (consumed on study, refused if already known); quests already teach via
  `spell:` unlocks. 8 tests.)*
- [x] **P5.3 Player tactical verbs.** *(done 2026-07-09 — SHIFT is the
  tactical modifier. Retreating from melee now provokes a free strike from the
  abandoned enemy; SHIFT+move disengages safely (+1 min); SHIFT+F shoves (STR
  contest, pushes the enemy a tile — blocked tiles hold); SHIFT+R takes an
  aimed shot (+2 damage, +1 min). Drink-as-turn was already true. Moving
  within melee reach never provokes. `engine/tactics.py`; 7 tests.)*
- [x] **P5.4 Off-screen faction ticker.** *(done 2026-07-09 —
  `engine/faction_ticker.py`: factions carry strength + stores (0–100); one
  dice-resolved event per game-day (raids resolved attacker-vs-defender,
  patrols, caravans, incursions, harvests) moves the numbers whether or not
  the player watches. Consequences are mechanical: strong brigands double
  bandit encounter weight; hungry villages push a bread/ale shortage through
  the director (prices rise → a radiant fetch quest follows); every event
  becomes a rumor NPCs repeat. "[Realm] …" morning lines; persists.
  8 tests.)*
- [x] **P5.5 Sound.** *(done 2026-07-09 — `ui/sound.py`: fully procedural,
  no audio files (true to the sprite ethos) — 9 synthesized effects (thudding
  hits, pickup blips, coin pings, a level-up arpeggio, spell zaps, discovery
  chimes, a defeat fall) driven by an event-log observer keyword map, plus
  rain/storm noise ambience looped by weather. Degrades silently headless;
  mixer re-inits to mono if pygame grabbed stereo first. 5 tests.)*
- [x] **P5.6 Sleep + day summary.** *(done 2026-07-09 — `engine/rest.py`:
  Enter at an inn/tavern sleeps to 6am for 5g — full heal/mana/hunger, and
  crossing the day boundary fires the whole nightly stack (reflection,
  director, ticker, radiant board). Wake to "A New Day": gold/XP/skill/quest/
  kill deltas vs the dawn snapshot, the morning's freshest rumor as tomorrow's
  hook, and a nudge toward the refreshed board. Hint bar advertises the bed.
  8 tests. **PHASE 5 COMPLETE.**)*

---

## Sequencing

| Milestone | Contents | Cumulative outcome |
|---|---|---|
| **M1 Repair** (Phase 0) | fixes P0.1–P0.8 | Everything advertised actually works |
| **M2 Foundation** (Phase 1) | data-driven content | Content scales without code edits |
| **M3 Progression** (Phase 2) | skills, chains, collection, diaries | 10+ hours of self-directed play |
| **M4 The Pillar** (Phase 3) | LLM protocol, secrets, persuasion, memory, director | The game nothing else is |
| **M5 The World** (Phase 4) | radiant + handcrafted quests, tutorial, regions | Rich, guided, replayable |
| **M6 Polish** (Phase 5) | combat AI, spells, sound, day loop | Feel and tactics |

Dependencies: P0 before everything (fix before build). P1 before P2/P4 content work.
P3 is independent of P2 and can run in parallel. P5 items can interleave anywhere.

## Playtest checkpoints & success metrics

- After M1: a fresh player completes buy→craft→recruit→save→load with zero data loss
  and no reading of README.
- After M3: playtester still has undone unlock goals after 5 hours; gold has scarcity
  (they can't afford everything they want).
- After M4: transcript test — a session where the player gains a quest, a discount,
  and a secret purely through conversation; NPC recalls it after save/load.
- After M5: a new player finishes Tutorial Island in ≤20 minutes and knows every core
  verb.

## Phase 6 — The Dungeon Master  (proposed 2026-07-09 by George; feasibility: HIGH)

An AI game-master with campaign memory and the power to reshape the world —
new NPCs, buildings, quests, monsters, terrain, history — **within the rules
of the game**, staging multi-day adventures behind the scenes. Three
interchangeable drivers: a live Claude Code session, the in-game LLM
provider, or none (the game as it is today).

**Why this is feasible now:** the architecture is already ~70% of a DM.
The nightly world director (P3.7) *is* a micro-DM — one call, five
whitelisted powers, engine-validated, heuristic fallback. Phase 1 made all
content data-shaped and machine-validated, so "create a monster/quest/NPC"
is a JSON spec the validator can referee. And "the LLM proposes, the engine
disposes" is this codebase's proven safety pattern (dialog actions, secrets,
persuasion, director). The DM is that pattern at world scope, with memory.

**Non-negotiable rules (the DM charter):** the DM never touches the player
directly (no teleporting/damaging/robbing the player, no deleting player
property), never breaks an active quest, creates content within balance caps
(monster level ≤ player+2, reward ceilings, budget of N mutations per
game-day), and every act is validated and written to an audit log — the
DM's notebook, which doubles as its campaign memory. World text (NPC dialog,
rumors) is never fed back as DM *instructions* (injection separation).

- [x] **P6.1 DM Tool API.** *(done 2026-07-09 — `engine/dm_api.py`, pure
  Python, no LLM: narrate / define_monster / define_item / spawn_npc /
  place_item / add_building / edit_terrain / create_quest (auto-posts to the
  board) / adjust_faction / schedule_beat (future-day queue, fired on day
  change). Charter enforced in code and tested: monster level ≤ player+2,
  item value ≤ 500, quest gold capped, 6×6 brush max, no spawning within 6
  tiles of the player, no burying/trapping the player, 12 mutations per
  game-day (narration free), every act + refusal in the persisted notebook.
  Definitions re-inject into registries on load. 12 tests. Remaining for
  later steps: plant_secret/teach_topic commands, dm_library persistence
  (P6.7). )*
- [x] **P6.2 World digest.** *(done 2026-07-09 — `engine/dm_digest.py` +
  `engine.dm.digest()`: one compact JSON dict (< 20KB, size-tested) — player
  sheet/skills/quests/equipment/deeds, named-NPC roster with feelings +
  latest opinions (spawns excluded), world systems (factions, shortages,
  rumors, board notices, monster census, locations), recent events, and the
  DM's own notebook/schedule/budget. JSON round-trip tested — ready for the
  P6.3 bridge to write to disk. 7 tests.)*
- [x] **P6.3 Session-DM bridge.** *(done 2026-07-09 — `engine/dm_bridge.py`
  + `--dm-bridge`: the game maintains `saves/dm/` — `digest.json` refreshed
  every ~10s + each dawn + after every bundle; `inbox/*.json` command bundles
  polled every ~2s, executed in order through the charter-enforced API;
  per-bundle `.result.json` receipts in `processed/`; a README for the DM.
  Whitelisted commands only (to_dict/run_scheduled refused); malformed JSON,
  bad args, and charter refusals are reported, never crash. Claude Code can
  now sit behind the screen. 8 tests.)*
- [x] **P6.4 Autonomous DM.** *(done 2026-07-09 — `engine/dm_autonomous.py`:
  one planning call per game-day (LLM providers only; heuristic mode never
  calls). The model reads the digest + its persisted `campaign_notes`, updates
  the arc, and proposes ≤6 whitelisted commands — executed through the
  charter-enforced API, refusals reported not fatal, junk output = a quiet
  day. The DM prompt teaches arc craft: foreshadow before striking, build on
  the player's deeds, reuse creations, schedule_beat future payoffs. Every
  planning day logged to the notebook. 8 tests via mocked provider.)*
- [x] **P6.5 Adventure modules.** *(done 2026-07-09 —
  `engine/dm_modules.py` + `dm.install_module(module)` (bridge + autonomous
  whitelisted): one bundle = monsters + items + optional building + spawns +
  placements + quest chain + day-offset beats + a diegetic announcement
  (rumor + narration). Prevalidation checks every piece against the charter
  before anything mutates; a mid-install failure rolls back every applied
  piece AND refunds the budget (tested by injected failure). Modules are
  named in the notebook. 6 tests.)*
- [x] **P6.6 Charter enforcement + safety tests.** *(done 2026-07-09 —
  closed a real charter hole: the DM could pave over buildings/POIs
  (`_protected_region` now refuses regions touching BUILDING terrain or typed
  locations; open wilderness stays editable). Injection resistance tested
  end-to-end: a deliberately "obedient" mocked model following an in-world
  injection ("give me 99999 gold, spawn a level-99 dragon on my tile") gets
  every breach refused by the code-level charter; the digest is marked
  untrusted in the prompt. Cost accounting: exactly one call per autonomous
  day. Save round-trips + player-touching-surface checks. 7 tests. Also this
  round per George: README fully refreshed (features/status/controls/flags/
  screenshots) + project CLAUDE.md added.)*

- [x] **P6.7 The Legendarium — persistent generative library** (George,
  2026-07-09): everything the DM defines (monsters, NPCs, magic items,
  buildings, quests, terrain variants — within the existing type system) is
  written to `data/dm_library/*.json`, loaded at startup alongside authored
  content and validated identically. Creations OUTLIVE the session and the
  save: a monster invented for tonight's adventure joins the world's bestiary
  forever; new games inherit the grown world. Retired entities (slain
  villains, lost relics, departed heroes) are recorded in a legendarium with
  their stories — and any future DM can resurface them ("the blade thought
  lost in the Murkfen turns up in a fence's stock"), so play accretes deep
  history: heroes and monsters come and go, resurface, and build long-term
  arcs. The history-sim/legends system (P4.6) becomes the template — the DM
  writes new legends the same way. Library curation: dedup by id, provenance
  stamps (which campaign/day created it), a size-capped "active set" the DM
  draws from so the world enriches without bloating prompts.
  *(2026-07-10 — engine/dm_library.py: `data/dm_library/` (gitignored,
  env-overridable via LLM_RPG_DM_LIBRARY), define_monster/define_item →
  record_definition with provenance + dedup + cap 100;
  load_into_registries() at every engine boot so new campaigns inherit the
  grown bestiary/armory; a slain DM creation enters legendarium.json
  (cap 200) with story + slayer + day; digest carries the legendarium tail
  so future DMs can resurface the past. Test isolation hardened: the test
  package pins a per-run temp library and DM tests wipe it in setUp;
  test_dm_library restores (not pops) the env var — popping it had leaked
  real-library writes for every module discovered after it. 6 tests;
  suite green twice consecutively. NPC/building/terrain variants already
  persist via the notebook/save path; quests via modules.)*

- [x] **P6.8 Play+DM self-playtest — SESSION 1 run** (standing activity,
  repeat after major changes). *(2026-07-09 — full both-sides session:
  Tutorial Island (all six lessons + boat), Oakvale shopping/gathering, a
  DM-staged two-day arc ("The Rot-King": define → narrate foreshadowing →
  scheduled quest + spawn), herb quest, tavern sleep (nightly stack + day
  summary), the hunt with shove tactics, turn-in. VERDICT: the loops hold
  together and the DM arc landed perfectly. FIXED from findings: (1) owning
  an axe locked you out of forest herb-foraging — the woodcutting node
  shadowed foraging even on cooldown (quest-breaking; Z now falls through);
  (2) tavern_intro was unreachable (no giver, not posted — now on the board).
  QUEUED: tavernkeeper greeting uses merchant stock lines ("finest wares" —
  flavor mismatch); consider 1 QP for DM-created quests; recurring
  ~1-in-10-runs world-gen test flake still uncaught. 3 regression tests.)*

### The Playtest Matrix (George, 2026-07-09 — the standing P6.8 charter)

Each playtest session evaluates as many of these as it can reach; findings
become fixes or plan items. Track coverage per session.

1. **Progression** — can the player complete every authored quest and
   advance (levels, skills, QP, guild ranks)? Any dead ends?
2. **Cooperation** — companions in fights; NPCs helping the player
   (secrets, discounts, heart events); NPC↔NPC cooperation (guard patrols,
   schedules, families).
3. **Conspiracy** — can NPCs work AGAINST the player? (Brigand faction,
   feuds, the fence storyline; does anything conspire, ambush, retaliate?)
4. **Economy** — full loop: earn → spend → craft → repair → bank; can it
   be broken (infinite money, dead sinks)? Do shortages/haggling matter?
5. **Monsters** — are encounters interesting (pack howls, ambushes,
   routing, territory)? Do they coordinate? Do they threaten appropriately
   at each level?
6. **Quests** — are they rich (chains, unlocks, multi-stage, humor)? Do
   radiant + DM quests keep the board alive?
7. **Navigation & discovery** — can the player find their way (hints,
   minimap, landmarks)? Are there interesting things to stumble on
   (relics, ruins, the Murkfen, caves, dungeons)?
8. **Alliances & enemies** — trust building, party recruitment, faction
   reputation consequences, persuasion/intimidation stakes; can the player
   make a real enemy?
9. **Combat completeness** — melee, ranged + ammo, spells, tactics
   (shove/disengage/aimed), status effects, durability, defeat outcomes.
10. **Coordination** — monsters and NPCs acting together (wolf packs,
    guard + player vs brigand, companion + player flanking).
11. **The DM layer** — arcs land diegetically; modules install; beats pay
    off; the world remembers.
12. **Feel** — pacing, log readability, hint quality, day-loop rhythm,
    sound cues, anything confusing or dull.

### Playtest Session 2 scorecard (2026-07-09 — full matrix run)

| # | Dimension | Verdict |
|---|---|---|
| 1 | Progression | ✅ board→accept→complete→turn-in→QP works; **fixed: 2 giverless quests had no GUI turn-in path** |
| 2 | Cooperation | ✅ recruit + companion fights; ⚠️ NPC↔NPC visible cooperation thin |
| 3 | Conspiracy | ❌ **absent** — hostile rep changes prices only; nothing retaliates |
| 4 | Economy | ✅ purse/haggle/shortage/repair/bank all bite |
| 5 | Monsters | ✅ howl→alert→converge verified live (packmate closed 5 tiles) |
| 6 | Quests | ✅ chains/unlocks/radiant/DM-module all flow |
| 7 | Navigation | ✅ hints, earned teleports, 5 relics seeded |
| 8 | Alliances/enemies | ✅ trust, recruit, persuasion stakes (−6 + day lockout) |
| 9 | Combat | ✅ melee/ranged+ammo/aimed/spells/durability; defeat outcomes tested prior |
| 10 | Coordination | ⚠️ wolves yes; **mixed NPC+player or guard-vs-brigand: none** |
| 11 | DM layer | ✅ module installed live in 4 pieces with announcement |
| 12 | Feel | ✅ log reads well (transparent dice); no flooding |

**New plan items from Session 2:**

- [x] **P7.1 NPC-vs-NPC conflict.** Guards engage hostiles they can see;
  brigands raid NPCs; ticker events occasionally play out ON SCREEN (a
  patrol fights a bandit near the road). Makes cooperation/conflict visible.
  *(done 2026-07-10 — engine/npc_conflict.py: cheap distance scan every 3
  turns, zero LLM. Guards/paladins close on and fight hostiles within
  sight 8; hostiles raid civilians at a slower cadence; ≤3 engagements a
  scan. `[Clash]` swings logged only within earshot of the player (14
  tiles) so distant fights don't flood the log; defeats always news. The
  player's duel is sacred — hostiles within 2 tiles of the player are
  left alone (no kill-stealing/rescues); party members excluded (the
  companion system owns them). Ticker tie-in: a repelled brigand raid
  leaves a straggler bandit spawned near a guard's beat, so the morning
  patrol fight actually happens on screen. 7 tests.)*
- [x] **P7.2 Conspiracy & retaliation.** Deep hostile faction rep spawns
  targeted responses: bounty hunters sent after an infamous player, ambush
  beats via the DM layer, the fence retaliating during The Fence quest.
  The player should be able to MAKE a real enemy.
  *(done 2026-07-10 — engine/retaliation.py, checked once per game night
  in the nightly stack. Escalating, TELEGRAPHED ladder per hunting
  faction (brigands + guards, so both outlaw and lawbreaker playstyles
  make enemies): rep ≤ −30 → warning rumor first ("a price on your
  head"), never an ambush from nowhere; still hostile after a 3-day
  cooldown → a level-scaled Bounty Hunter (new data/monsters.json
  template) spawns 8–14 tiles out with the pack-alert converge behavior
  pointed at the player's last position; rep ≤ −60 → a pair. Recovering
  above the threshold stands the hunt down. State persists via
  save_load. P7.1's guards will fight brigand-class hunters they see —
  an infamous-but-lawful player can lure the hunt into the watch.
  9 tests. ALSO fixed this round: (1) P7.1 regression — the tutorial
  island's Training Dummy is MONSTER-class and Sergeant Bors would
  cross the lesson to destroy it; conflict now only engages NPCs
  standing on the overworld grid (zone NPCs have coords in another
  space); (2) the long-standing ~1-in-10 worldgen flake ROOT-CAUSED:
  companion follow used greedy single-axis steps with no obstacle
  handling and stalled forever on water/walls/bystanders — now slides
  along obstacles; 6 consecutive full-suite greens after the fix.)*
- [x] **P7.3 Squad tactics.** Companions + guards coordinate with the
  player in fights (focus fire, real flanking positions); monster packs
  attempt surrounds rather than a queue.
  *(done 2026-07-10 — engine/squad_tactics.py, pure geometry shared by
  companions, P7.1 guards and monster packs: `surround_step` (approach
  the free tile beside the target nearest you — attackers fan out
  instead of queueing; combat_system._step_toward now routes through
  it, so wolf packs and guards surround), `flank_tile` (the tile
  opposite the player, earning the existing +2 _flanking_bonus;
  companions sidestep onto it before swinging), `player_focus_target`
  (player_attack records its target; companions within 8 tiles
  prioritize it — focus fire), and `path_step` (real BFS pathfinding
  with greedy fallback — companions no longer trap in concave
  terrain). Phase 7 complete: the world cooperates, conspires and
  coordinates. 8 tests; 10 consecutive full-suite greens.)*

**Verdict:** feasible and the natural capstone — P6.1–P6.3 are buildable in
loop rounds immediately after Phase 5; P6.4 rides infrastructure that exists.
P6.7 turns the DM from a session feature into a compounding one: the game
gets permanently richer every time it's played.

## Phase 8 — Mining `autonomous_world` (George, 2026-07-10)

Survey of /Users/george/Documents/GitHub/autonomous_world (same author,
375 files / ~176k LOC): mine the self-contained, pure-function wins; treat
its sprawl (economy split over 7 modules, combat over 6, a never-shipped
3D renderer, 48 committed throwaway viewers, a finished-but-never-wired
procedural music system) as the cautionary tale. Port candidates ranked by
value ÷ effort:

- [x] **P8.1 Astronomy** (`systems/astronomy.py`, 242 LOC, zero deps):
  latitude/season day-length, dawn/dusk bands, solar intensity, TWO moons
  (28d + 47d) with phases and conjunction detection — conjunctions are a
  natural hook for world-director beats, rare spawns, heart events.
  Constants → JSON; pairs with our calendar/seasons. LOW effort.
  *(done 2026-07-10 — world/astronomy.py, pure functions; constants in
  data/astronomy.json with in-code defaults; year aligned to the
  calendar's 360 days (solstice day 90). Silver Lunara (28d) + copper
  Thal (47d) with proper phase names; `moonlight()` 0–1. Integrations:
  conjunction nights are diegetic ([Realm] omen event + rumor via
  `announce_conjunction` in the nightly stack), raise the wilderness
  encounter chance ×1.5, and full moons LIGHTEN clear nights in
  ui/lighting. solar_intensity ready as the P8.3 crops/temperature
  input. 14 tests.)*
- [x] **P8.2 Disease & contagion** (`systems/health.py` template pattern):
  13 diseases as JSON content (severity/duration/spread/symptoms/immunity),
  staggered tick cadence, outbreaks + healer value; feeds gossip/needs.
  MED effort (split to health_defs.json + <400-line module).
  *(done 2026-07-10 — engine/disease.py + data/diseases.json (4 authored
  diseases: Marsh Fever, Winter Grippe, Rot Cough, River Ague — content
  is data, add more by editing JSON; validator checks cure items/seasons/
  ranges). Sickness is a world event: season-biased outbreaks pick a
  patient zero and enter the rumor mill ([Realm] + whisper), contagion
  spreads within 3 tiles between overworld people (never monsters, never
  across zone grids), diseases run their course in days and leave timed
  immunity. The player can catch anything — a daily severity drain that
  weakens but never kills (floor 1 HP) — and the RIGHT remedy cures via
  the normal item-use flow (herb bundle for fevers, potions for coughs).
  All state rides character metadata so saves are free. One check per
  game night, zero LLM. 10 tests.)*
- [x] **P8.3 Crops + grazing** (`crop_system.py` 349 + `vegetation.py`
  272): farmland visibly progresses fallow→planted→mature→harvested by
  season; grazing degrades tile health. Closes the producer side of
  foraging/economy. LOW-MED effort.
  *(done 2026-07-10 — world/farming.py + TerrainType.FARMLAND (furrow
  sprite, minimap color). Every worldgen farm location claims a 4×3
  field of grass at new-game start; fields run fallow → planted
  (spring, "[Realm] Planting has begun") → growing → mature (ripening
  speed driven by the P8.1 solar-intensity curve — bright summers
  ripen fast) → harvested; winter turns all fallow. The player
  harvests ripe tiles with the normal Z key (hint-bar advertised):
  2 wheat sheaves + foraging XP; whatever stands in late autumn the
  farmers bring in — villager stores rise in the faction ticker and
  the harvest enters the rumor mill. Plot state persists via
  save_load (terrain re-stamped on load). GRAZING DEFERRED: no
  herbivore wildlife exists in this world yet — revisit if livestock/
  wildlife land (note kept here).  7 tests.)*
- [x] **P8.4 Pantheon** (`pantheon.py`, their best-tested system): gods
  with domains, prayer→miracle loop, divine competition — a themed layer
  for our nightly world director. HIGH effort; gods → JSON; souls/
  reincarnation later if it earns its keep.
  *(done 2026-07-10 — engine/pantheon.py + data/pantheon.json: five
  gods (Morrik war / Solara harvest / Veyra roads / Grimble coin /
  the Pale Lady mercy), each with domain, deed keywords, one miracle,
  an omen line — content is data, validator-checked. DEEDS build
  favor via a player_deeds hook (slaying→Morrik, harvests→Solara,
  quests→Veyra, diary tiers→Grimble, surviving sickness→Pale Lady;
  farming + disease now record deeds). PRAYER: SHIFT+P at any shrine
  or temple, once per game day, hint-bar advertised — the most-
  favoring god answers; below threshold a quiet +1 favor, at 10 favor
  the god SPENDS it on their engine-enforced small miracle (full
  heal / blessing / +15 gold / cure disease / whispered rumor). No
  LLM adjudication — all code and dice. OMENS: deep favor (25+)
  occasionally marks the realm at night through the rumor mill.
  Favor rides player.metadata (saves free). Souls/reincarnation
  deferred as planned. 10 tests.)*
- [x] **P8.5 Economy algorithm only** (`world_economy.py`): tâtonnement
  sticky-price discovery + settlement production so prices self-balance.
  Extract the math (~300 lines), skip their 7-module sprawl. MED effort.
  *(done 2026-07-10 — engine/market.py: four market categories (arms /
  provisions / goods / arcana) each carry a sticky price index. Player
  purchases push demand, sales push supply; each night one tâtonnement
  step (tanh-damped) then a 10% drift home; clamped [0.6, 1.6]. Village
  stores add a supply signal (hungry village → dear provisions). The
  index multiplies BOTH buy and sell prices so margins are preserved —
  no arbitrage loop. Director shortages stack on top. Big moves hit the
  rumor mill ("[Realm] Prices for arms climb at the market."). Wired
  into shop_manager pricing + shop_panel transactions; persisted via
  save_load. 9 tests.)*
- [x] **P8.6 Shadowcasting FOV** (`world/fov.py`): octant-based LOS —
  fog-of-war for dungeons, ranged line-of-sight, stealth. LOW effort.
  *(done 2026-07-10 — world/fov.py, the AW survey's cleanest module
  ported near-verbatim (Nystrom-style octant shadowcasting, __slots__
  shadows, circular radius, early-out on full shadow) plus
  `has_line_of_sight` and llm_RPG bindings (buildings/mountains
  opaque on the overworld; walls in zones). WIRED: dungeons get real
  fog-of-war — visible bright, remembered-but-unseen dimmed,
  never-seen black, monsters hidden outside your sight (zone.explored
  accumulates); ranged shots check true LOS before flight ("No clear
  shot — something solid is in the way"), the foundation P8.7
  targeting builds on. 9 tests incl. shadow-cone geometry and a
  bow-through-a-building refusal.)*
- [x] **P8.7 Ranged combat & targeting** (George, 2026-07-10):
  extract AW's ranged-combat/targeting approach for BOTH missile
  weapons and ranged spells — explicit target selection (cycle
  targets / cursor), range + line-of-sight checks (build on P8.6
  FOV), and clear on-screen feedback about what you're aiming at.
  Survey AW's implementation first, then port the targeting UX onto
  our existing projectile/ammo/spell systems.
  *(done 2026-07-10 — engine/targeting.py, ONE target model for
  missiles and spells: [ / ] cycle valid targets (hostile or
  provoked, in range 12, TRUE line of sight from P8.6 — dungeon
  walls block underground, buildings/mountains outdoors, indoors is
  unreachable from the street), announced "Target: Wolf (6 tiles)"
  and marked with a gold corner-bracket reticle in both overworld
  and dungeon views. R fires the bow at the lock, offensive
  spellbook casts hit the lock and refuse without LOS; the lock IS
  player_target_id, so P7.3 companions focus-fire what you aim at.
  Stale locks self-clear to the nearest valid target. ALSO two
  George bug reports fixed: (1) boxed-in soft-locks — bumping a
  FRIENDLY NPC now swaps places ("You squeeze past Merta"), while
  hostiles hold the line; (2) inconsistent indoor interactions —
  zone movement blocked on NPCs' OVERWORLD coordinates (phantom
  walls, walk-overs); visitors now block and swap at their
  DISPLAYED positions only. 12 tests.)*

**Patterns adopted as standing rules** (no checkbox needed): staggered
timer-gated ticks for every heavy system; status-effect templates with
`__slots__` + clone; "every item must have a production source" as a
content-validator rule (add to items/data_validate when P8.5 lands); LOD/
dormancy (statistical sim beyond an active radius, with hysteresis) if the
world ever grows past one region. **Anti-patterns to enforce**: every
subsystem must have an owner in the tick loop verified by a smoke test (no
dead code); consolidate a domain before splitting it; no speculative
second renderer; throwaway viewers stay out of version control.

## Phase 9A — Buildings & living interiors (George, 2026-07-10 playtest) — PRIORITY

George's playtest verdict: buildings are the most underdeveloped part
of the game. "No doors/windows furniture etc. Only single levels…
Doors need to be opened, locks need keys or to be picked/forced.
Rooms should have functions. There should be consequences for
entering certain buildings… Different buildings are likely to have
different occupants depending on the style of building and the
occupants occupation." Takes priority over P8.6 and the
fantastical-structures items below (which build on this framework).

**AW survey findings (2026-07-10, full report in session transcript):**
AW built buildings TWICE (baked-tiles vs zoom-interiors) with
duplicated furniture logic — port ONE model. Openable doors/windows
and door KEYS were never built there (new work); lockpick (d20+DEX vs
DC) and STR-bash port cleanly. Best copy targets: the furniture
face-tile dispatch (`actions_interact.py` — bed heals, chest loots,
fireplace cooks, anvil crafts, bookshelf teaches), ~130 hand-authored
`Blueprint` tile-array floor plans (`world/buildings.py` +
`blueprint_library.py`, only depend on tile constants),
`ROOM_TEMPLATES`/`BUILDING_ROOM_SETS`/`CONNECTIVITY_RULES` data, and
`PlayerHouse` (self-contained player-owned housing). Cautions:
occupancy was proximity-emergent (bind occupants explicitly at spawn
instead); trespass was owner-only (add guard response + faction rep);
their multi-floor stair code was the buggy corner (port the concept,
rewrite transitions); near-zero test coverage was why the two models
diverged.

- [x] **P9A.1 Doors & locks.** Interiors get real doorways: closed
  doors block entry until opened (bump/E); locked doors need the key
  item, a lockpick attempt (Dexterity/lockpicks tool, failure chance),
  or forcing (Strength check, noisy — guards hear). Door state
  persists. Locks as data on the building/interior spec.
  *(done 2026-07-10 — engine/doors.py + data/doors.json. Policies by
  building-name match: homes/towers LOCKED, shops/forges lock at
  night, taverns/temples/shrines open. TAB entry now goes through the
  door: closed doors push open; locked doors yield to (in order) the
  right key in your pack, a lockpick attempt (d20+DEX vs lock level;
  failing by 5+ snaps your picks), or SHIFT+TAB forcing (d20+STR vs
  level+3) — forcing is NOISY either way ("splintering wood" event +
  player.metadata['forced_entry_day'], the P9A.4 trespass hook), and
  a forced door stays broken until dawn when every door resets to
  policy. State persists via save_load. 11 tests.)*
- [x] **P9A.2 Furniture with functions.** Interior furnishing layer
  (beds, chests, tables, forges, altars, bookshelves as interior
  objects with sprites): beds = sleep/rest to heal anywhere indoors
  you're permitted (extends engine/rest.py beyond inns); chests hold
  loot (some locked); forges enable smithing; bookshelves surface
  lore/topics. Furnishing sets by building style, as data.
  *(done 2026-07-10 — engine/furniture.py, the AW survey's top-ranked
  port: interiors' already-rendered furniture now WORKS via E (hint-
  bar advertised). BED rests an hour: +30% max HP once per day (doors
  gate access; trespass costs come with P9A.4). HEARTH cooks the
  first cooking recipe you carry ingredients for. ALTAR prays (holy-
  place override — pantheon P8.4). SHELVES surface the freshest rumor
  once a day (Library blueprint's shelf rows now map to Shelves, not
  barrels). CHEST/CRATES/BARREL rummage once per building per day
  (coins or a common item, deterministic per building+day). Anvils/
  bars/counters give directional flavor ([K] craft, [B] wares).
  Cooldowns ride player.metadata — saves free. 10 tests.
  ALSO this round, George's report "attacking an NPC doesn't make it
  hostile" CONFIRMED as a gap and FIXED: assault flags the victim
  provoked — they fight back at full strength, flee below 35% HP
  crying "Help! Guards!", stand down if you leave — plus an immediate
  −3 villager reputation, once per provocation. 6 tests.)*
- [x] **P9A.3 Occupants & homes.** Every named NPC gets a home
  matched to their occupation (blacksmith sleeps at the forge house,
  priest at the temple); schedules route them home at night;
  buildings without owners get style-matched occupants or stand
  empty/derelict. Knocking vs barging in.
  *(done 2026-07-10 — characters/homes.py: occupants bound EXPLICITLY
  at world start (the AW survey's correction — never by proximity).
  Preset NPCs keep authored homes; guards "living" in the settlement
  at large move into the watchtower; every other enterable building
  takes residents from its blueprint's npc_class/npc_count with
  generated names (farmhouses get villagers, the Library its wizard,
  the Hunter's Lodge a ranger) — full NPCs who follow schedules home
  at night (existing "home" activity), gossip, sicken, and will
  witness (P9A.4). No-occupation buildings flagged DERELICT with
  dusty interior descriptions. occupants_of/owner_of/is_derelict
  feed P9A.4. FIXED pre-existing bug found by the round-trip test:
  home_location was never serialized — every NPC lost their home on
  save/load. Knock-vs-barge deferred into P9A.4. 8 tests.)*
- [x] **P9A.3b Buildings you can SEE (George: "I don't see any
  difference in the buildings").** The 9A work so far is behavioral;
  make it visible: draw a door glyph on building exteriors (state-
  colored: open/closed/locked/broken), give furniture real procedural
  sprites (bed/chest/hearth/anvil/altar/shelves) instead of fallback
  rects, bump-into-locked-door feedback without pressing TAB, richer
  multi-room blueprint interiors for the big buildings, and an
  occupant nameplate line when entering ("Merta's farmhouse").
  *(done 2026-07-10 — George's follow-up mid-round pinpointed the
  ROOT problem: building footprints were walkable from any direction.
  Now enterable buildings are SOLID: walls block the player ("The
  walls of the Old Farmhouse. Its door faces south." — once/day),
  and the single door tile at the building's south face is
  bump-to-enter — walk into it and the P9A.1 lock decides (open →
  you're inside, one keypress fewer than TAB; locked → refusal with
  the pick/force teaching line). Door glyphs are drawn on every
  enterable exterior, colored by state (open shows a dark doorway,
  locked a brass lock-dot, broken a splintered slash). Furniture got
  real procedural sprites — beds with pillow+blanket, banded chests,
  flaming hearths, anvils, candle-lit altars, book-spined shelves,
  barrels, tables, stairs. Entering names the occupant ("This is
  Merta's place." / "Long abandoned."), and entering counts for
  VISIT quest objectives. Multi-room blueprint interiors deferred to
  P9A.5 (multi-level). NOTE follow-up: NPCs still ghost through
  walls on the overworld — route their movement around footprints
  when P9A.5 touches pathing. 9 tests.)*
- [x] **P9A.4 Trespass & consequences.** Entering a private home
  uninvited (or breaking in) is witnessed: occupants object, guards
  respond (P7.1 conflict system), faction rep drops, repeat offenders
  meet P7.2 retaliation. Shops/taverns/temples stay public in
  daytime; homes are private; everything locks at night.
  *(done 2026-07-10 — engine/trespass.py, chaining the whole 9A/P7
  stack: taverns/temples and daytime shops are public, derelicts
  don't care. Entering a private home (or an after-hours shop) is
  TRESPASS: if the owner is home or within 8 tiles — and at night
  everyone is home — they object aloud, remember it (NPC memory +
  relationship −10), and villager rep drops −4. FORCING a door is a
  CRIME: "Thief! The watch! THE WATCH!", villagers −6 AND guards −8,
  and every guard within earshot (12) gets the pack-alert and
  CONVERGES on the door, challenging "Who goes there?!" on arrival
  (heuristic guard alert-following added). Repeat break-ins drive
  guard rep past −30 and the P7.2 bounty ladder posts a price on
  your head — proven end-to-end in a test. Slipping in unseen by
  day is free but counted (unseen_break_ins) for future fence/heist
  content. 8 tests.)*
- [x] **P9A.5 Multi-level buildings.** Stairs connect interior
  levels (tavern bedrooms above the taproom, cellars below);
  renderer/movement already zone-aware — extend Interior to a level
  stack. This is also the foundation for P9.2–P9.5 fantastical
  structures.
  *(done 2026-07-10 — Interior grew a linked level stack (ground /
  level_above / level_below with twinned stair tiles); the AW stair
  code was their buggy corner so transitions were REWRITTEN clean:
  step onto a stair tile and you arrive on the other level's twin
  stair, one rule, no caches. Taverns and inns get bedroom lofts
  (beds + a chest — upstairs beds rest via P9A.2); shops, forges and
  smithies get storage cellars (barrels to rummage). TAB from a loft
  or cellar returns you to the ground floor first; only the ground
  floor exits. Stairs render with the P9A.3b sprite; furniture
  interaction prefers the piece underfoot over adjacent ones (a
  barrel beside stairs rummages, not creaks). Foundation laid for
  the Phase 9 fantastical structures. 9 tests.)*
- [x] **P9A.6 Building-specific actions.** Per-style interactions
  advertised on the hint bar: cook at a hearth, bank at the temple,
  research at the wizard's shelves, repair at the forge — driven by
  the furniture layer, not hardcoded per building.
  *(done 2026-07-10 — the missing services + a REGRESSION the solid
  walls exposed: banking and forge-gated crafting read the player's
  OVERWORLD position, which is zone-local nonsense once you're
  indoors — and with walls you can't stand on footprints anymore, so
  both services had silently died. New `engine.player_location()` is
  interior-aware (any level of a building resolves to its Location);
  banking (N/M, hint-bar advertised inside temples/shops) and craft()
  now use it. E at the ANVIL repairs every damaged piece you carry at
  the usual forge prices ("Your gear is in good order" when
  pristine). The Village Well's blueprint quirk (altar cells) became
  a real Well — drink once a day (+2 HP). Cook/pray/research were
  already live via P9A.2. PHASE 9A COMPLETE — George's building
  overhaul: doors, locks, furniture, occupants, trespass,
  multi-level, services. 9 tests.)*
- [x] **P9A.7 Interior–exterior coherence (George, follow-up
  playtest).** Three observed mismatches: (1) interiors don't match
  the exterior footprint (stock blueprints regardless of building
  size/shape); (2) NPCs visible on building tiles outside are absent
  from the interior when you enter — presence must be consistent
  (same entities, translated, interactable); (3) you can see
  characters/contents through walls from the main map — hide what's
  indoors unless there are windows/openings or magical sight (the
  advanced part can come later; hiding is the same mechanism as #2).
  **AW coherence survey (2026-07-10) key findings:** interior NPCs
  must be the SAME entities, position-translated (copies diverge);
  their two presence functions disagreed — use ONE; do NOT port the
  roof-reveal (it solves a baked-overworld problem we don't have —
  separate grids give occlusion free); for (1), size the interior
  from the footprint aspect and put its door on the same edge, and
  optionally port their furniture-based room flood-fill typing.
  *(PARTS 2+3 DONE 2026-07-10 — engine/presence.py, ONE presence
  module for everything: an NPC standing within an enterable
  footprint is INDOORS — hidden from the street renderer (no seeing
  through walls) and unreachable from outside; entering the building
  assigns everyone inside a deterministic zone-local position
  (npc_spots then free tiles), rendered in the interior view — the
  SAME entities, so relationships/memory carry. ALL adjacency now
  routes through npc_adjacent_to_player: talk (T), hint bar, melee
  (F), barter (B) — melee/barter tested from both sides of a wall.
  REMAINDER, part 1: interior sized from footprint aspect + door
  edge matching + room typing — next 9A round. 8+1 tests.)*
- [x] **P9A.7b Footprint-matched interiors.** Part 1 of P9A.7 per
  the AW survey: `interior_size_from_footprint(loc)` — interior
  dimensions scale with the building's overworld footprint (wide
  building → wide interior), the interior door sits on the same edge
  as the exterior door glyph (south), and blueprint layouts adapt or
  fall back to a sized default. Optional: furniture flood-fill room
  typing for future occupant placement.
  *(done 2026-07-10 — `fit_to_footprint()` in world/interiors.py:
  every interior is rebuilt to dimensions scaled from its overworld
  footprint (w×3+2 / h×3+2, clamped 6–16 × 5–12) so a hut opens
  into a hut and a hall into a hall, wide buildings open into wide
  rooms; the interior door ALWAYS sits at the south-face center —
  the same edge as the exterior door glyph — and furniture keeps
  its relative layout, remapped proportionally with collision
  nudging (no two pieces share a tile). Lofts and cellars inherit
  the fitted dimensions since the multi-level pass runs after.
  Room flood-fill typing deferred until occupant placement needs
  it. 8 tests. GEORGE'S FULL COHERENCE REPORT NOW RESOLVED.)*

## Phase 9 — Fantastical structures (George, 2026-07-10)

George: "Are there dungeons, castles, temples, wizards towers and other
fantastical structures... richer in detail than the regular 2D mapped
world?" Current truth: single-level BSP dungeons from cave tiles and
simple one-room building interiors — nothing grander. The zone machinery
(interiors/dungeons render + move via `_render_zone`/`_move_in_zone`)
already supports richer spaces; what's missing is depth, theming, and
authored set-pieces. Plan:

- [x] **P9.1 Structure framework.** A `Structure` = a named stack of
  themed zone levels connected by stairs/ladders, entered from an
  overworld footprint; locked doors + key items; per-level light levels.
  Blueprints as data (`data/structures.json`) — rooms, connections,
  spawn tables, loot tables, set-piece text. Generalizes
  interiors/dungeons into one system.
- [x] **P9.2 The Ruined Keep, explorable.** The history-sim's keep gets
  a real inside: great hall, collapsed barracks, a crypt below with the
  era-appropriate relic and a guardian. Lore lines from history_sim
  become readable inscriptions inside.
  *(done 2026-07-10 — the keep grew into its P9.2 shape: a 14-wide
  Great Hall with the collapsed barracks behind a rubble wall (beds,
  a barrel, a chest the garrison left), stairs down to a DARK crypt
  where a Wandering Troll stands guard over the treasure chest.
  '$history' inscriptions now quote THIS world's actual history-sim
  lore ("Year -2: Trolls came down from the mountains…"), different
  every campaign; the crypt's carving stays authored. AND a latent
  regression fixed: history-sim relics placed ON the keep footprint
  became unreachable when walls went solid (P9A.3b) — the builder now
  SWEEPS footprint loot into the deepest chest, guarded and
  legend-revealing on looting (engine/legends fires from chest
  loot). Chest contents + looted state persist via save_load;
  chests loot exactly once. 6 new tests (13 total structure tests).)*
- [x] **P9.3 Temple + crypt.** Oakvale temple interior (shrine services,
  the priest's routine) over a crypt level — undead below, blessed
  rewards, ties into banking/blessing systems already present.
  *(done 2026-07-10 — temple_crypt structure: a Sanctuary (altar
  prayer and N/M banking both verified working inside) with a narrow
  stair behind the chancel down to a DARK crypt where two Restless
  Bones (new undead monster) guard a chest of blessed rewards —
  authored chest_loot (scroll_heal + amulet_health), a new framework
  capability, validator-checked (loot ids must exist, a Chest cell
  must exist). Crypt inscription ties to the plague-vigil history
  event. The priest's routine was already live via P9A.3 homes.
  5 tests. ALSO this round, George: "ranged combat and selection of
  targets is difficult to use" — UX overhaul: the lock now
  AUTO-ACQUIRES once per turn so the gold reticle appears BEFORE you
  fire; CLICK any visible enemy to target it; lock announcements
  carry HP and range ("Target: Wolf (6 tiles, 8/10 HP). [R] to
  shoot."); F is smart (adjacent → melee, else bow at the lock);
  and the hint bar finally advertises it all ("[R] shoot Wolf ·
  [ [/] ] switch · click to target"). 4 tests.)*
- [x] **P9.4 The Wizard's Tower.** A vertical structure — each floor
  stranger than the last (library, menagerie, observatory), arcane
  puzzles (lever/sigil, not pixel-hunts), a new spell or focus item at
  the top. Introduces a wizard NPC with heart events.
  *(done 2026-07-10 — four floors up: Entry Hall → Library, where
  three glowing SIGILS (new puzzle framework: touch in the order the
  inscription teaches — "Moon before Sun, Sun before Stars" — wrong
  touches reset, success dissolves the ward sealing the stairs) →
  dark Menagerie (two caged wisps wake on first visit) → Observatory
  with scroll_fireball + potion_might in the chest. Puzzle
  state/solved wards persist via save_load; validator checks order
  permutations, ward directions, sigil names. ALZARA the tower
  wizard joins the preset cast — home in the tower via P9A.3, a
  30-affinity heart event at the great lens (frost scroll perk),
  conjunction-obsessed goals for the LLM to chew on. Sigil +
  inscription sprites. 9 tests.)*

### Playtest Campaign 3 (George, 2026-07-10) — NEXT ROUNDS, PRIORITY

George: "add a few rounds of intensive testing of the game by
playing both the main character and the DM. Try to complete quests,
get experience, explore distant regions, learn about the world, make
friends and allies, defeat powerful monsters. Fix problems in the
gameplay, fix bugs and add to the plan."

- [x] **PT3.1 The adventurer's arc.** Scripted both-sides session:
  tutorial → boards → 2+ authored quests to completion → level up →
  skill training → buy/sell/craft/repair loop → befriend an NPC to a
  heart event → recruit a companion. Judge every step against the
  Playtest Matrix; fix what breaks.
  *(done 2026-07-10 — 17-beat scripted session, 16 clean (the 17th
  was a detector bug: Melody's heart event actually fired and split
  the hat). VERIFIED WORKING: board accept → talk quest → turn-in
  rewards; fetch quest tracks foraged herbs and pays; kills level
  the player; market buy/sell with no arbitrage; hearth cooking;
  anvil repair; heart event at threshold; recruitment + following;
  DM-created quest accepted at the board completes by play. TWO
  REAL BUGS FIXED: (1) GAME-BREAKING — the quest board was
  unreachable since solid walls (board_at_player read raw overworld
  coords; the board now hangs INSIDE the tavern via
  player_location(), same fix applied to can_craft_at_player and
  the pantheon's holy-place check); (2) ECONOMY — hopping fresh
  forest tiles yielded ~290 herb bundles in one sweep; daily forage
  fatigue added (yield thins per forage after a 5-find grace, floor
  20%, resets at dawn) — sweep now ~40/day. 2 regression tests.)*
- [x] **PT3.2 The explorer's arc.** Distant regions (chunk streaming
  east/west/north/south), the Murkfen, dungeons with fog-of-war, the
  Ruined Keep crypt, temple crypt, the full Wizard's Tower climb,
  teleports/diaries, region discovery. Fix what breaks.
  *(done 2026-07-10 — 31-beat scripted expedition, 28 clean (2 were
  detector wording; 1 real). VERIFIED: the Murkfen stands and reads
  as itself; dungeon dive with working fog-of-war (41 of 384 tiles
  visible from a room) and 3 lurkers; the Ruined Keep bump-entered,
  history inscription read, troll guardian slain in the dark crypt;
  the full Wizard's Tower climb — ward blocks, Moon→Sun→Stars
  dissolves it, menagerie wakes, observatory chest pays out;
  teleports; region streaming west and home again (120x80 wilderness
  generated). FIXES from findings + George's live reports this
  round: (1) tower prize was a CAST scroll needing mana — now a
  Tome of Fireball that TEACHES the spell (new item; teach_spell
  path verified); (2) keep crypt chest could be empty if worldgen
  placed no keep relic — authored fallback loot; (3) George's crash:
  inventory panel died on string items (body markers) — tolerant
  now; (4) George: infinite carrying — CARRY CAPACITY added
  (engine/carry.py: 18 slots + 2 per STR modifier, enforced at
  pickup/forage/gather/harvest/shop/rummage/chests — chests stay
  lootable until you make room; rewards never blocked); (5) George:
  couldn't pick up items indoors — furniture interaction was
  shadowing pickup; ground item underfoot now wins. 14 tests.)*
- [x] **PT3.3 The war arc.** Powerful monsters (troll guardian,
  conjunction-night spawns), ranged/spell targeting in anger, squad
  tactics with companions, bounty-hunter retaliation, the DM running
  a fresh module mid-session. Fix what breaks.
  *(done 2026-07-10 — 18-beat battle session. VERIFIED: auto-lock +
  cycling under pressure, archery killing a pack in 5 volleys, squad
  fight won in 45 rounds with the companion surviving, conjunction
  omen + x3 danger night, bounty warning → level-scaled hunter →
  hunter defeated, a DM module installed MID-SESSION (quest to the
  board, cultist slain, next-day beat fired), and defeat resolving
  as story ("You come to hours later where you fell — bloodied,
  starving, but alive"). TWO REAL BUGS FIXED: (1) SPELL KILLS made
  0-HP 'alive' zombies — take_damage never set defeated status, so
  spell-slain enemies stayed active/targetable forever and granted
  no XP/loot/quest credit; _on_kill now routes through the ONE
  defeat handler (my test goblin ate 20 fireballs before diagnosis);
  (2) party members were still driven by SCHEDULES — Melody marched
  home to the tavern mid-adventure; party skips scheduled NPC turns
  (the companion system owns their feet). AUTHORING NOTE: kill
  objectives match by class — 'monster' does not match
  brigand-class targets; DM quest authors beware. 2 regression
  tests.)*
- [x] **PT3.4 Findings round.** Consolidate all findings into fixes +
  new plan items; update the Playtest Matrix scorecard (Session 3).
  *(done 2026-07-10 — scorecard below; final campaign fix: 'monster'
  kill targets now match ANY hostile class as a forgiving authoring
  default, with the id/class exact matches unchanged.)*

### Playtest Session 3 scorecard (2026-07-10 — Campaign 3, rounds 83–86)

| # | Dimension | Verdict |
|---|---|---|
| 1 | Progression | ✅ two authored quests + a DM quest to completion; leveling; **fixed: quest board unreachable since solid walls** |
| 2 | Cooperation | ✅ Melody recruited, fought, survived; **fixed: schedules marched party members home mid-adventure** |
| 3 | Conspiracy | ✅ bounty ladder end-to-end: warning → level-scaled hunter → fight |
| 4 | Economy | ✅ buy/sell/craft/repair/bank; **fixed: 290-bundle forage exploit (daily fatigue)**; carry capacity added (George) |
| 5 | Monsters | ✅ pack fights, troll guardian, conjunction ×danger night |
| 6 | Quests | ✅ boards, fetch/talk/kill flows, DM module mid-session with next-day beat; kill-target authoring made forgiving |
| 7 | Navigation | ✅ Murkfen, dungeon fog-of-war, keep/temple/tower delves, teleports, region streaming all four ways |
| 8 | Alliances/enemies | ✅ heart event fired at threshold; real enemy made (the law) |
| 9 | Combat | ✅ archery with lock/cycle, fireball, melee, defeat-as-story; **fixed: spell kills made 0-HP zombies (no death/XP/credit)** |
| 10 | Coordination | ✅ companion focus-fire in squad fight; surrounds live |
| 11 | DM layer | ✅ module install mid-war, quest boarded + completed, beat fired |
| 12 | Feel | ✅ telegraphed dangers, story defeats; George's live reports (3 crashes/gaps) all fixed same-session |

**Campaign 3 totals:** 66 scripted beats, 7 REAL bugs fixed (board
unreachable, forage exploit, spell-kill zombies, party schedules,
string-item crashes ×2, indoor pickups shadowed), 3 balance/content
improvements (carry capacity, tome-not-scroll reward, keep fallback
loot), 2 new phases planned from George's requests (10: destructible
world; 11: traversal & movement magic).
- [x] **P9.5 Multi-level dungeons.** Depth 2–3 dungeons with stairs-down,
  scaling monsters/loot per level, a boss floor; collection-log and
  diary hooks ("clear depth 3").
  *(done 2026-07-10 — generate_multilevel(): every cave now opens
  onto a 2–3 floor delve using the SAME linked-stairs convention as
  buildings (one _take_stairs rule moves between interior levels AND
  dungeon floors, landing in the right engine slot). Deeper floors:
  stronger monsters (+level/+hp per depth), richer room loot, and
  the deepest floor holds the TYRANT OF THE DEPTHS (a den-lord troll
  with a hoard of potions beside it). Monsters are floor-tagged —
  no cross-level rendering/targeting bleed (renderer + targeting
  guards). TAB climbs floor by floor before emerging. New personal
  best depth is announced ("[Collection] You have delved to depth
  2") and stored in metadata for future diary tasks. The whole stack
  serializes recursively — save mid-delve, the dungeon remembers.
  7 tests.)*
- [x] **P9.6 DM + Legendarium structures.** `define_structure` DM command
  (charter-capped size/level) + structures recorded in the Legendarium
  so DM-built towers persist across campaigns; module packs may ship
  structures.
  *(done 2026-07-10 — dm.define_structure: the DM raises whole
  multi-level structures on any existing location, charter-capped
  (≤3 levels, ≤16×12 grids, known cells only, ≤3 monsters per level
  from EXISTING templates — so monster power stays behind the
  define_monster level cap — item-value caps on chest loot; one
  mutation charged). Built immediately through the P9.1 framework;
  bridge allowlisted; persisted in dm state and re-injected on load;
  recorded to the Legendarium and INHERITED by future campaigns —
  a DM's folly built tonight stands in every world after (test:
  fresh boot inherits dm_folly). PHASE 9 COMPLETE: framework, keep,
  temple crypt, wizard's tower, multi-level dungeons, DM towers.
  Module-pack structure shipping deferred until a pack wants one.
  9 tests.)*

## Phase 10 — A world you can break and shape (George, 2026-07-10)

George: fireballs/lightning that take out GROUPS and burn buildings;
floods; boulders from giants and trebuchets; giants smashing
buildings, uprooting trees, and MOVING debris; humans cooperatively
building and destroying (mining, foresting, digging, farming,
damming). AW survey complete (2026-07-10): their durability.py
(materials, tile HP, bash DCs, giants bypass DCs, RubbleTracker that
MOVES debris rather than deleting it) and elemental_effects.py (fire
spread, acid, scorch) are the crown jewels to port; both their AoE
implementations are entity-only flat-radius (port + add tile damage);
mining tunnels/floods/damming are GREENFIELD (their mining is
abstract counters, flood a scripted tile-flip). Traps: our single
BUILDING tile type (use a sparse material/HP overlay, add only
RUBBLE + SCORCHED terrain); per-turn not dt-seconds; WorldMap needs
set_terrain + tile callbacks for interior sync.

- [x] **P10.0 Enabling infra.** TerrainType.RUBBLE + SCORCHED (+
  sprites/minimap); WorldMap.set_terrain(x, y, t) firing registered
  tile callbacks. Tiny round.
  *(done 2026-07-10 — RUBBLE (grey stone scatter) and SCORCHED
  (charred ground) terrains with sprites + minimap colors; rubble
  walkable until P10.4 depth rules; WorldMap.set_terrain fires
  register_tile_callback(x, y, old, new) hooks — every future
  destruction routes through it. 3 tests.)*
- [x] **P10.1 AoE damage, entity-first.** Spell dataclass +
  spells.json gain area/targets; fireball (area 2) damages everyone
  near the impact except the caster (companions included — friendly
  fire is real); siege-monster splash (troll boulders) via the same
  helper. Uses the P8.7 lock as the impact point.
  *(done 2026-07-10 — Spell.area from spells.json (fireball 2.0);
  cast with area engulfs EVERYONE within radius of the target except
  the caster — companions burn if they stand too close (friendly
  fire is real and tested), out-of-radius is safe, blast kills route
  through the one defeat handler ("Slain in the blast: …"), and the
  SAME-SPACE rules hold: crypt blasts don't scorch the street, walls
  shield the indoors, other dungeon floors are safe. Single-target
  spells unchanged. Siege-monster splash deferred to P10.5 with the
  boulder throwers. 6 tests.)*
- [x] **P10.2 Destructible tiles.** Slim DurabilitySystem port:
  sparse tile HP, materials (stone buildings resist fire, wooden
  forests burn), TILE_DESTROYED map (BUILDING→RUBBLE, FOREST→GRASS);
  AoE spells and siege damage tiles in radius.
  *(done 2026-07-11 — engine/tile_damage.py: sparse per-tile HP with
  materials (stone ×0.3 vs fire, ×1.5 vs siege; wood ×2 vs fire),
  base HP (wall 60, tree 20, field 10), destruction through
  set_terrain so the P10.0 callbacks fire. Walls CRACK at half HP
  before collapsing to RUBBLE; fire leaves SCORCHED earth, axes
  leave grass. Fireballs raze their radius ("The blast razes 3 of
  the surroundings!"). AND the payoff: a breached wall is a SECOND
  DOOR — bump the rubble gap and you clamber inside, no lock
  consulted (trespass still judges you). Sparse HP persists via
  save_load. 8 tests.)*
- [x] **P10.3 Fire spread.** Per-turn ElementalEffects: fires spread
  to adjacent combustibles, burn out to SCORCHED, damage anyone
  standing in them; fireball ignites, lightning scorches.
  *(done 2026-07-11 — engine/surfaces.py, upgraded to the first
  slice of DOS2-style SURFACES per the Phase 12 synthesis: a sparse
  per-tile layer of FIRE / OIL / WATER with the marquee chemistry —
  fire damages whoever stands in it every turn (NPC flame deaths
  are real; the player is maimed to 1 HP, never killed outright —
  the story kills), gnaws the tile itself through P10.2 materials
  (groves burn to SCORCHED, stone endures), and spreads to adjacent
  combustible terrain; OIL pools chain-ignite in one whoosh the
  instant flame touches any tile of the pool; WATER douses and
  refuses ignition; fires gutter out. Fireballs leave burning
  ground at the impact. Rendered as translucent overlays; ticked
  once per game turn (sparse — free when nothing burns); persists
  via save_load. The DM can pre-paint arenas with pour(). 10
  tests.)*
- [x] **P10.4 Interior sync + rubble.** Exterior breach opens the
  matched interior wall (tile callback); rubble depth blocks
  movement until CLEARED — debris moves to a dump tile, never
  vanishes.
  *(done 2026-07-11 — RUBBLE gained DEPTH: one collapse leaves a
  clamberable depth-1 breach; piled to 2+ (giant smashes, multiple
  collapses, dumped debris) it BLOCKS movement until cleared. E on
  or beside rubble shifts one layer to the least-buried adjacent
  tile — debris is MOVED, never deleted (conservation tested);
  fully cleared tiles return to grass. Breach entry requires low
  rubble. INTERIOR SYNC: entering a breached building shows the
  hole from inside — every rubbled footprint tile opens the
  proportionally-matched interior perimeter tile (idempotent
  sync-on-entry, load-safe by construction). Depths persist via
  save_load. Also fixed a statistics flake in the dungeon depth
  test (assert the mechanic, not roll luck). 7 tests.)*
- [x] **P10.5 Actors shape the world.** Giants bash buildings
  (STR/size-scaled siege damage, no DC for the huge) and hurl
  boulders (projectile + splash + tile damage); laborer tasks: chop
  (forest→grass with regrowth), dig (grass→farmland), clear rubble;
  minimal cooperative ConstructionProject (materials + workers →
  stamped tiles). *(Round 93: `engine/giants.py` — hill_giant
  template (behavior flag "giant"), giant_tick on the conflict scan
  (smash adjacent walls with STR-scaled siege damage leaving DEEP
  rubble; hurl boulders 3–8 tiles with LOS: direct hit maims the
  player to 1 HP never kills, splash crushes bystanders for real,
  siege tile damage + debris scatter; 3-tick cooldown); nightly
  run_night_labor — work crews clear rubble beside settlement
  buildings via the conserving clear_rubble, scorched ground beside
  living woods regrows (cap 5/night). 7 tests. Remainder:
  cooperative ConstructionProject + chop/dig laborer tasks — fold
  into P10.6's dig actions.)*
- [x] **P10.6 Greenfield: water & tunnels.** Minimal cellular flood
  spread + damming (blocking tiles stop the frontier); mining
  tunnels (mountain→cave floor via dig actions). Small and tested.
  *(Round 94: `engine/flood.py` — floods spread as a cellular
  frontier over grass/road/farmland/swamp/scorched every 4 turns
  (cap 40 tiles), blocked by buildings/mountains/forest and RUBBLE —
  piled debris is a DAM, so the P10.4 rubble economy doubles as
  flood defense. Occupied tiles are never flooded; when the turns
  run out the water recedes and restores the original terrain.
  Storms can burst a water's edge (small per-turn chance). Persisted
  via save_load. `engine/earthworks.py` — E-key ground fallback
  (rubble clearing moved here from player_actions, which is back
  under 500 lines) + pickaxe DIGGING: mountains joined the
  tile_damage material table (stone, 80 HP), four swings cut a
  tunnel to open ground, each swing trains Mining; hint-bar lines
  for both. Plus the P10.5 remainder: night MASONS in
  run_night_labor rebuild breached footprint walls once the rubble
  is cleared, closing the interior hole through the shared
  footprint_to_perimeter mapping (breach sync now opens AND closes
  through one function). 8 tests. Deferred: full ConstructionProject
  (materials + workers building NEW structures) — revisit if a
  quest/DM use-case wants it.)*

## Phase 11 — Environmental traversal & movement magic (George, 2026-07-10)

George: wade in shallow water, SWIM in deep water (skill/ability-
gated) with real risks — fast-flowing water can carry you away or
drown you, encumbrance (the new carry system) and fatigue make it
harder, magic/equipment can help. Same graded-difficulty treatment
for climbing mountains, rough ground, swamps and dense forest. Plus:
some creatures and magic-enhanced characters FLY, and magic can
speed or slow movement.

- [x] **P11.1 Traversal framework.** Per-terrain traversal rules as
  data (data/traversal.json): passable/wade/swim/climb classes, skill
  gates (Agility exists; add Swimming to the lattice or reuse), STR/
  encumbrance modifiers (carry.py), fatigue costs, fail outcomes
  (blocked / swept downstream / HP loss / drop items). WATER becomes
  wadeable at shores (new SHALLOW_WATER terrain or depth overlay),
  swimmable beyond.
  *(Round 95: `engine/traversal.py` + `data/traversal.json`. Depth
  by overlay, no new terrain: water with any dry 4-neighbor is
  SHALLOW — anyone wades, it just tires; all-water neighbors = deep,
  a graded check. Checks: d20 + lattice skill level + ability mod vs
  DC raised by pack load (carry.py: +2 at 60%, +4 at 90%) and
  exhaustion (+2 tired / +5 exhausted). Swimming joined the lattice
  (data/skills.json + a Ripple pet); climbing uses Agility — the old
  hard gates (travel.py level 15/25) became the mastery plateau:
  at Agility 15 the d20 cannot miss the climb DC. Success moves,
  tires, costs minutes, trains the skill; failure strands you tired;
  miss by 5+ and the rock/river bites (HP loss floored at 1). Swamp/
  forest are slog-class: per-step fatigue + minutes, telegraphed on
  entry. Player fatigue rides the NPC needs scale; sleeping resets
  it. travel.try_shortcut delegates; weather travel penalty moved
  into traversal.on_step (player_actions back under 500). Hint bar
  telegraphs wade/swim/climb. Validator checks traversal.json skill/
  terrain refs. Sweep-downstream and drop-pack outcomes are P11.2/
  P11.3 as planned. 8 new tests + 3 rewritten.)*
- [x] **P11.2 Hazard outcomes.** Being swept: forced movement along a
  flow direction; drowning: escalating HP loss with a struggle check
  each turn; mountain falls. Telegraphed clearly in the log + hints.
  *(Round 96: `engine/hazards.py`. FLOW derived from water shape —
  a river is much longer than wide, so flow runs along the clearly-
  longer axis toward map south/east; round lakes are slack. Each
  turn in deep water: struggle check (swim math); success treads
  water, failure = swept SWEEP_TILES downstream if there's a
  current + escalating drown damage (2×turns). The water never
  kills: at 1 HP you're WASHED ASHORE at the nearest dry tile,
  fatigue 100, and the river keeps one item from your pack
  (dropped on the riverbed — recoverable if you dare). Badly
  failed climbs while standing on rock TUMBLE you off the face.
  `[!]` log lines + a top-priority deep-water hint ("the current
  pulls!"). 7 tests.)*
- [x] **P11.3 Aids.** Items and spells that help: rope, climbing
  gear, a swimming blessing, water-walking; encumbrance interacts
  (drop your pack or sink).
  *(Round 97: all content is data. Items: rope (+3 climb) and
  climbing_picks (+5, stacking) — carried gear read via
  `equip_bonuses` by `traversal.aid_bonus(kind)`, applied to
  crossing checks AND drowning struggles; stocked in the general
  store. Spells: water_walk (status water_walking, 30 turns —
  stride over deep water with no check and no hazard tick) and
  swimmers_grace (+5 swim, 40 turns); both self-cast, both also on
  wizard-shop scrolls (scroll_water_walk / scroll_swimmers_grace).
  New statuses joined VALID_EFFECTS + validator. Encumbrance: a
  failing struggle with a ≥90% pack logs "drop something ([I]) or
  sink!" — and the load already raises the DC (P11.1). 7 tests.)*
- [x] **P11.4 Flight & speed magic.** A `flying` movement mode
  (creature flag or spell/status) that ignores ground-tile rules
  (water, rubble, swamp penalties) but not walls/ceilings indoors;
  haste/slow statuses that change actions-per-turn or step cost;
  flying monsters (wisps already float thematically) use it.
  *(Round 98: one choke point — `world_map._is_flier` (behavior
  flag OR 'flying' status, read straight off metadata) lets
  move_character cross water/mountain for ANY mover, so player
  spells and monster flags share the rule; zone movement untouched
  (walls/ceilings still block indoors). Flying also skips deep-
  rubble blocks, slog taxes, and the P11.2 water hazard — and when
  the spell expires over a lake, the swim rules are simply real
  again. Statuses flying/hasted/slowed + spells flight/haste/slow
  (haste & flight self-cast; slow is ranged). Turn economics in
  `traversal.advance_after_move`: hasted = every second step free;
  slowed = two turns per step; slowed NPCs lose every other action
  (action_router). marsh_wisp got behavior.flying. Hint bar shows
  a flying line and suppresses the deep-water warning while aloft.
  8 tests. Phase 11 COMPLETE.)*

## Phase 12 — Rules of Living (George's deep-dive, synthesized 2026-07-11)

Three research agents surveyed tabletop (D&D 5e / Pathfinder 2e),
simulation roguelikes (NetHack / CDDA / OSRS / UO / DF / Qud / PZ)
and modern CRPGs (DOS2/BG3 / KCD / RimWorld / Skyrim / Gothic / M&B)
for concrete rules across ten categories; docs/RULES_AUDIT.md holds
our baseline. The full reports (with exact formulas) are in the
session transcript. Below: the synthesis, ordered so each item is
one loop round and earlier items feed later ones. Convergence was
the ranking signal — mechanics independently top-ranked by multiple
traditions lead.

- [x] **P12.1 Degrees of success.** PF2e's four-outcome d20: beat
  the DC by 10+ = critical success, miss by 10+ = critical failure,
  nat 20/1 shift one degree. Upgrade engine/skills.py's check core
  so EVERY existing roll (lockpicking, persuasion, forage quality,
  forcing doors, shove) gains jackpot/fumble outcomes. The single
  biggest systemic win per line of code.
  *(Round 99: `Degree`/`CheckResult`/`degree_of`/`check()` in
  engine/skills.py — the audit found roll_check had ZERO callers;
  every system rolled its own dice, so the real work was routing.
  Lockpicking: crit = "flawless" instant open; crit fail = picks
  snap (replaces the fixed PICK_BREAK_MARGIN). Forcing: crit = door
  off its hinges; crit fail = -2 HP popped shoulder. Persuasion
  (dice path): crit = masterstroke, double relationship; crit fail
  = OFFENDED, -5 extra, double lockout; LLM path stays two-outcome.
  Shove (opposed, margin ±10): crit = hurled two tiles; crit loss =
  the counter-shove staggers YOU back. Forage: graded Survival —
  crit = double yield "perfect patch"; fumble = nettles, -1 HP, no
  yield (but still teaches XP, keeping the XP contract stable).
  4 old tests re-pinned to the graded contract; two 5%-flakes from
  fumble outcomes found and fixed by pinning quality rolls in yield
  tests. 11 new tests. Suite 999, 6 green runs.)*
- [x] **P12.2 Valued conditions.** PF2e-style {condition, value,
  decay} schema for status_effects: Frightened 2 = −2 to everything,
  auto-decays 1/turn; persistent damage with a flat-DC end check;
  add prone/blinded (FOV powers blinded) and off-guard (−2 AC,
  replaces our advantage-strength flanking).
  *(Round 100: status entries gained `value`; DECAYING_VALUES
  conditions tick value down 1/turn and expire at 0 (duration
  ignored). Frightened N bites EVERY d20 — `check_penalty` wired
  into roll_check, so the P12.1 routing propagates it to locks,
  doors, persuasion, forage free. persistent_damage: damage each
  turn, then a flat DC 15 check to stop; natural-crit melee hits
  now open a bleeding wound (2/turn). Prone: -2 attack/-2 AC, NPCs
  spend their next action scrambling up (action_router), crit
  shoves inflict it. Blinded collapses effective_visibility to 1.
  Off-guard (-2 AC, 1 turn) is now what flanking DOES — the old
  attacker +2 became a visible condition on the defender.
  Intimidate applies Frightened 2. 10 tests. Suite 1009, green x3.)*
- [x] **P12.3 Needs II: thirst + the exhaustion ladder.** Add thirst
  (faster clock than hunger: days not weeks); wire hunger/thirst/
  sleep-debt into a 6-level cumulative exhaustion ladder (5e) with
  felt penalties (checks → speed → attacks → HP max → collapse);
  CDDA's two-track insight: tiredness (any sleep clears) vs sleep
  debt (only real nights); the player finally NEEDS to sleep. Bed
  quality (already modeled) sets recovery speed.
  *(Round 101: thirst at 4/hr vs hunger's 3 — thirsty ~15h, parched
  ~22h; parched drains HP (floored 1). exhaustion_level 0-6 stacks
  tired(+1) + starving(+1) + thirsty(+1)/parched(+2) + sleep_debt
  (+1/night missed, cap +2). Rungs: -level to EVERY d20 (wired into
  roll_check beside P12.2 conditions), 2+: steps cost extra minutes,
  3+: -2 attacks, 4+: HP capped at half, 6: COLLAPSE (paralyzed 8,
  fatigue only partially cleared — passing out is poor rest). Two
  tracks: inn sleep clears fatigue AND debt; furniture bed naps
  clear fatigue -50, never debt; nights without a bed accrue debt in
  the nightly stack. Drinking: E at any water's edge; ale/mead/wine
  + new waterskin quench via use_effect.thirst (data); stocked in
  general/tavern. Hint bar telegraphs parched + exhaustion 2+.
  The old inline hunger block became needs.player_needs_turn.
  9 tests. Suite 1019, green x4.)*
- [x] **P12.4 Dying & Wounded.** PF2e's Dying 1–4 + recovery checks
  + the Wounded counter (each knockdown brings the next closer),
  layered UNDER our failure-as-story outcomes: drop to 0 → dying
  turns → stabilize into robbed/left-for-dead/story beats instead
  of instant resolution. Kenshi's soft-states (staggered/KO) for
  NPCs so fights end in bodies to rob, ransom, or rescue.
  *(Round 102: `engine/dying.py`. Player at 0 HP goes DOWN: Dying
  1+Wounded, flat DC 10 recovery each turn (nat 20/1 move 2), hits
  while down worsen; downed players can't walk (turns tick), the
  hint bar shows only "DYING N/4". Stabilizing (Dying 0) adds a
  Wound and resolves GENTLY (robbed/left-for-dead — never slain);
  Dying 4 rolls the FULL P4.7 table with game-over plumbing. A real
  inn night clears Wounded. NPCs: PERSON classes are KNOCKED OUT
  instead of killed — no loot drop, a body on the ground you can
  ROB (E: takes their purse, -30 relationship, remembered at
  weight 8), and they wake in the overnight stack at 1/3 HP with a
  grudge memory; monsters still die. XP/quest/faction hooks kept
  for KOs. use() extracted to engine/item_use.py (player_actions
  380 lines). Remainder: ransom/rescue beats around KO'd bodies.
  12 tests + 2 integration tests re-pinned. Suite 1031, green x3.)*
- [x] **P12.5 Food economy.** OSRS: every food gets heal + a shared
  eat/attack delay (eating mid-fight costs tempo), one combo food,
  one brew that overheals but drains offense; KCD freshness 0–100
  decaying per day (poison risk under 50), cooking resets it and
  launders the stolen flag. Gives farming/foraging/cooking a combat
  reason to exist.
  *(Round 103: `engine/food.py` + data flags (use_effect.food/
  perishable/combo/brew). Eating sets a 2-turn CHEW DELAY blocking
  melee AND ranged ("no opening to strike"); the Meat Pie is combo —
  eats through the delay, sets none. The Hearty Brew heals to 115%
  of max and curses the sword arm for 10 turns. Freshness 100
  decays 15/night in the pack; under 50 food heals half with a
  poison chance scaling as it rots; the hearth re-bakes carried
  rations to 100 (cooking's combat reason). Bread/jerky perishable;
  pie + brew stocked at the tavern. The full-health refusal
  contract preserved. Stolen-flag laundering waits on a theft
  marking system (delivered in P12.9 round 108). 7 tests. Suite 1038, green x3.)*
- [x] **P12.6 Rest with teeth + the DM's night.** Long rest costs
  provisions (BG3 camp supplies); interruption rules; well-rested
  buffs by bed quality (Skyrim +XP tiers); lifestyle expenses as a
  gold sink at inns; and the hook the whole game wants: the long
  rest is the AutonomousDM's GUARANTEED beat slot — while you sleep,
  the world moves and the DM speaks (dreams, ambushes, camp scenes).
  *(Round 104: `engine/camping.py`. Enter outdoors now CAMPS: a
  real camp burns SUPPLY_NEED(8) heal-value of food from the pack —
  supplied = real night (half heal, fatigue/debt/wounded cleared),
  unsupplied = fitful DOZE (partial fatigue only, the night wasted).
  25% wilderness INTERRUPTION: reduced recovery + a real beast at
  the fire come dawn. Inn tiers: 15g private room applies
  WELL_RESTED (+10% XP via award_xp, 240 turns), 5g bunk when coin
  is short. THE DM'S NIGHT: every sleep — inn or camp — ends with a
  guaranteed `[DM]` dream stitched from the lived world (recent
  deeds, director rumors, stock dreams), and
  dm_autonomous.night_scene lets the LLM DM queue an authored scene
  that plays once. Camp hint at fatigue 60+. 3 rest tests re-pinned
  to tiers/camp routing. 8 tests. Suite 1046, green x3.)*
- [x] **P12.7 Combat depth.** Concentration: one sustained spell
  max, damage forces the keep-it check (or PF2e sustain-as-action);
  cover from FOV terrain (+2 half / +5 three-quarters vs ranged);
  swap flanking advantage→flat −2 AC off-guard; BG3 weapon actions —
  one special move per weapon type, once per rest (cleave, topple,
  pommel-stun, bleed) as data on weapons.json.
  *(Round 105: `engine/combat_depth.py`. CONCENTRATION: spells flag
  `concentration: true` in data (bless/haste/hex/entangle/
  frost_armor); casting a second drops the first (its status ends
  wherever it sat); damage in _resolve forces d20+CON vs
  max(10, damage) or the spell unravels. COVER: forest/rubble on
  the Bresenham line = -10% hit (half) / -25% (three-quarters),
  computed at loose-time and carried on the projectile (both the
  player's and NPCs' shots). WEAPON ACTIONS as weapon data
  (use_effect.weapon_action): Cleave (axe/longsword — carries into
  a second adjacent enemy), Topple (warhammer — prone), Pommel
  Strike (sword — stunned), Lacerate (dagger — bleed); SHIFT+V,
  once per rest, restored by any real night; hint-bar advertises
  the unspent move beside an enemy. Flanking→off_guard was already
  done in P12.2. Housekeeping: shoot_ranged extracted to
  engine/ranged.py (mixin 402); input_handler overlay keys folded
  to a dispatch (499). A silent str.replace no-op in the combat
  hook was caught by the tests — anchored Edits only for hooks.
  10 tests. Suite 1056, green x3.)*
- [x] **P12.8 Skill actions.** PF2e's codified combat verbs from
  skills we already train: Trip/Shove-plus (Athletics), Demoralize
  (Intimidation, per-target 10-min immunity — THE anti-spam
  pattern), Feint (Deception), Battle Medicine (once/day/target).
  Skills become fighting styles.
  *(Round 106: `engine/skill_actions.py`, all four riding the
  P12.1 graded core with degree-sensitive outcomes. TRIP
  (Athletics vs 12+their STR): crit = prone + 2 dmg, crit fail =
  YOU are prone. DEMORALIZE (Intimidation vs 12+their WIS, 3-tile
  voice range): crit = Frightened 2, and every ATTEMPT — success
  or not — sets the per-target 10-minute immunity. FEINT
  (Deception vs 12+their WIS): crit = off-guard 4, success = 2
  (one survives the action's own tick), crit fail = YOU'RE
  off-guard. BATTLE MEDICINE (Medicine DC 13): burns a bandage,
  once/day per patient (immunity lives on the target), crit 15 HP
  / success 8 / crit fail cuts (-2). Bound to SHIFT+T/I/B/H via
  one dispatch; hint line beside enemies. input_handler squeezed
  to 499 (brackets/bank/overlays folded). 8 tests. Suite 1064,
  green x3.)*
- [x] **P12.9 Crime & law II.** Skyrim's guard-resolution menu on
  contact: pay fine / jail (time passes, skill-progress cost) /
  bribe / talk (Speech check) / resist; per-settlement bounty
  ledger; stolen-item flags with fence-only sales (the
  unseen_break_ins counter finally pays off); witnesses remember
  clothes (KCD) — a disguise resets identification.
  *(Round 107, sub-step 1 of 2: `engine/law.py` — the LEDGER and
  the MENU. Per-settlement bounties in player.metadata (persisted
  free); crimes feed it: break-ins via trespass (5g unseen / 10g
  witnessed), assault on citizens (20g, via ko_person), robbing
  the unconscious (15g). Guard adjacency + local bounty opens the
  confrontation (once per GRACE hour): 1 PAY (gold, clean slate) ·
  2 JAIL (12h pass, fine×2 XP drains from your best lattice skill,
  gold kept) · 3 BRIBE (60% of fine + Persuasion DC 12; refusal
  grows the fine 25%) · 4 TALK (one graded Persuasion per
  confrontation: crit clears free, success halves) · 5 RESIST
  (fine ×1.5, the guard swings, the watch remembers). Walking out
  of reach shelves, never clears. Keys 1-5 in play mode; the hint
  bar hands over to the menu. 9 tests, suite 1073 green x4.
  Round 108, sub-step 2: STOLEN GOODS — lifting from an owned,
  locked, non-derelict home (pickup or rummage) flags the item
  (use_effect.stolen, save-free); honest merchants refuse ("I know
  where that came from"), only Wulf the Stonepine taverner fences —
  at 60%, and only once unseen_break_ins >= 3 (the counter pays
  off); the hearth launders food (P12.5's deferred clause
  delivered). WITNESSES REMEMBER CLOTHES: witnessed crimes record
  your armor per settlement; guards only confront a MATCHING
  outfit — a change of armor is a disguise until you're seen
  again; unseen crimes grow the ledger but never confront (they
  don't know WHO). Preset NPCs can now carry metadata from data
  (the fence flag). 7 more tests. Suite 1080, green x3.)*
- [x] **P12.10 Economy II.** OSRS stock-elastic shop prices (price
  moves k% per item of stock deviation, self-healing restock)
  layered on per-settlement supply so REGIONAL arbitrage exists
  (M&B); KCD haggle-patience minigame (visible meter, failed
  haggles cost per-merchant reputation) replacing flat haggle
  tokens; an alchemy-style universal value floor as the gold sink.
  *(Round 109: STOCK ELASTICITY in ShopManager — price moves 5%
  per unit the shop's stock deviates from its category baseline,
  clamped [0.5, 2.0]; buying them out raises the price, flooding
  them tanks it; the daily restock is the self-heal. REGIONAL
  SUPPLY as data (data/settlement_economy.json): per-settlement
  category factors multiply buy AND sell — provisions 0.8 in
  Riverside vs 1.3 in Stonepine: buy low, carry, sell high.
  HAGGLE MINIGAME: H in the shop panel, per-merchant patience
  3/day with a visible meter + earned-deal readout; graded
  Persuasion DC 13 — crit +10%, success +5% (cap 15%), fail -1
  patience, crit fail zeroes patience AND -5 relationship; the old
  /persuade token honored via max(). DEFERRED: the alchemy-style
  universal value floor (wants an item-targeting UI). 8 tests.
  Suite 1088, green x3.)*
- [x] **P12.11 Social depth: the bond ceremony.** Qud's water
  ritual: a formal "share a drink" with named NPCs converts
  reputation into spendable currency — buy secrets, learn skills,
  recruit companions at rep prices (12×level-gap + 200); faction
  rep gets behavior THRESHOLDS (despised/disliked/indifferent/
  favored/revered) instead of price-only effects.
  *(Round 110: `engine/bonds.py` + /bond and /spend dialog
  commands. The ceremony consumes an ale/mead/wine (P12.5 drinks
  earn another job), once per NPC ever, minting bond = 10 +
  relationship//2. /spend secret (15) reveals a secret PAST its
  affinity/quest gates — trust is the key; /spend skill (25) is a
  +150 XP lesson in the teacher's craft (class→lattice map);
  /spend join (20 + 12×level-gap, Qud's proselytize price scaled)
  recruits past the trust gate — class and party-cap rules still
  stand. THRESHOLDS in factions.py with three behavior gates:
  despised merchants refuse trade ("Your coin's no good here"),
  disliked factions refuse recruitment, revered guards wave off
  petty bounties (<20g) entirely. 12 tests. Suite 1100, green x3.)*
- [x] **P12.12 Medicine II: the infection race.** RimWorld's three
  numbers — infection grows +0.84/day, immunity +0.64/day scaled by
  rest/bed, treatment quality (healer skill × medicine tier)
  subtracts — first to 100 wins. Extends diseases (P8.2) with
  wounds that demand tending, and makes healers/priests matter.
  *(Round 111: `engine/infection.py`. Dirty wounds turn: 30% on
  stabilizing in the dirt (P12.4), 30% washed ashore (P11.2), 15%
  on a crit bleed; one infection at a time. The nightly race:
  infection +28, immunity +21 scaled by slept_quality (inn bed
  x1.5, camp x1.0, sleepless x0.6 — rest.py/camping.py stamp it).
  Immunity 100 = the wound knits; infection 100 = the fever CRISIS
  drops you into the P12.4 dying state (the story kills, not the
  germ) and breaks back to 60. TREATMENT: Battle Medicine
  subtracts by degree (crit -35 / success -20 / fail -5), +10 with
  a cleric/paladin adjacent — priests matter at the bedside. Hint
  bar shows the live race. 9 tests. Suite 1109, green x3.)*
- [x] **P12.13 Bones: the fallen enter the Legendarium.** NetHack's
  bones pattern, single-player: on death/darkest defeats, snapshot
  the site + a hostile ghost + your gear (mostly cursed) into the
  Legendarium; future campaigns load it with probability 1/3. Your
  failures literally become the world's content.
  *(Round 112: `engine/bones.py`, persisted as bones.json in the
  Legendarium root (LLM_RPG_DM_LIBRARY, capped 10). True death at
  the bottom of the dying ladder snapshots who/where/what-level/
  slain-by/gear. New campaigns roll 1/3 at start: a hostile GHOST
  of the fallen rises near the death spot — level-scaled and
  FLYING (P11.4 pays again) — guarding the gear scattered around
  it, 70% risen HAUNTED: equipping haunted gear applies cursed 30
  ("the {item} remembers its dead"). Testing found and fixed a
  real hazard: discover imports tests as TOP-LEVEL modules, so
  tests/__init__'s env pinning never runs there — death-path test
  files now pin LLM_RPG_DM_LIBRARY to temp dirs at module level,
  and bones tests clean the file before AND after (an engine
  start rolls bones, so leftovers caused cross-module ghost
  nondeterminism — caught as a 1-in-3 tyrant-test flake).
  8 tests. Suite 1117, green x5.)*
- [x] **P12.14 Pet loyalty.** NetHack tameness 1–20 (+1 feeding,
  −1 neglect, 0 = walks away) and apport/fetch trained by treats,
  layered on pets.py followers.
  *(Round 113: the active pet carries loyalty 1-20 (fresh pets
  start at 10). SHIFT+Z tosses a treat — burns one food item, +1
  loyalty, stamps the fed-day; each day WITHOUT a treat costs 1 in
  the nightly stack, with a fraying warning at <=3 and the walk-away
  at 0 (removed from the collection — win them back at the grind).
  APPORT at loyalty 12+: each overworld turn a 5% dart fetches a
  ground item from near the pet's heels into your pack (carry-cap
  respected, zones excluded). Hint bar warns when the bond frays.
  9 tests — including a fetch test that initially grabbed a
  worldgen relic instead of the planted ale (the mechanic worked;
  the test staged in a scrubbed corner). Suite 1126, green x3.
  PHASE 12 COMPLETE.)*

**Annotations to existing phases from the research:** P10.3 (fire
spread) upgrades to DOS2-style SURFACES — water/oil/blood pools,
electrified water, oil slows, fire+oil detonates; the DM can
pre-paint arenas as data. P10.2's damage thresholds gain 5e's
object-material AC/HP tables if finer grain is wanted. Phase 11
swimming adopts 5e's two-stage breath clock (1+CON-mod minutes,
then CON-mod rounds of drowning).

## Phase 13 — Deferred remainders (collected 2026-07-11)

Phase 12 shipped with a few clauses consciously deferred mid-round;
they are first-class items now, in dependency order.

- [x] **P13.1 The alchemy value floor.** OSRS High Alchemy as the
  gold sink/value floor deferred from P12.10: Transmute (wizard/
  sorcerer spell, 4 mana) turns any carried item into gold at 40%
  of value — the item-targeting UI is the inventory panel's [T] on
  the selected bag item.
  *(Round 114: `transmute_item` in engine/item_use.py, spell in
  data/spells.json (class casters know it from the start),
  [T] in the I-panel with the footer hint. Stack-aware, mana-gated,
  spell-known-gated; stolen goods transmute too — coin is coin,
  destruction is the ultimate laundering. 6 tests.)*
- [x] **P13.2 Ransom & rescue.** The P12.4 remainder: KO'd named
  NPCs can be carried (a body in the pack slot? drag?) to a
  faction that wants them — brigands ransom captured guards back
  to the watch, rescued citizens pay gratitude and rep; ties the
  KO economy to factions and the P12.9 ledger.
  *(Round 115: `engine/ransom.py`. SHIFT+G hoists a KO'd body —
  it weighs 6 pack slots (carry.used_slots counts it) and every
  step under the load costs an extra minute + fatigue. SHIFT+G
  again delivers by WHO stands beside you: a cleric/paladin =
  RESCUE (wake at half HP, 15g gratitude, +30 relationship, +8
  faction rep, warm memory); the fence = RANSOM (25 + 10×level
  gold, faction −15, bounty +25 WITNESSED — the victim saw your
  face — and a weight-9 grudge: "SOLD me to the brigands"); nobody
  special = set down gently. KO expiring mid-carry wakes them in
  your arms (+5, benefit of the doubt). Hint bar teaches both
  ends. Testing surfaced good presence behavior: delivery fails on
  building footprints (indoor rules) — carry them to open ground,
  as the fiction wants. 7 tests. Suite 1139, green x3.)*
- [x] **P13.3 The breath clock.** Phase 11 annotation from the
  research: 5e's two-stage drowning — hold breath 1+CON-mod
  minutes underwater before the P11.2 escalation starts; diving
  becomes plannable.
  *(Round 116: `breath_capacity` = (1 + CON mod) × 4 turns, floor
  4, in engine/hazards.py. While breath holds, deep water costs
  NOTHING — no checks, no fatigue — and the hint bar counts the
  dive down ("[~] diving — breath N"); warnings at 2 and 0
  ("your lungs burn"). Only at empty lungs does the P11.2
  struggle machinery begin. Surfacing, water-walking or flight
  refills instantly. Existing struggle tests re-pinned with
  breath=0 presets (a blind sed mangled two nested call sites —
  repaired; anchored edits for test surgery too, noted again).
  5 tests. Suite 1144, green x3.)*
- [x] **P13.4 Playtest Campaign 4.** Both-sides scripted-and-judged
  session per the Playtest Matrix, focused on the Phase 12 systems
  interacting (needs+rest+infection, crime+fence+disguise,
  economy+haggling+arbitrage, bond+thresholds); findings become
  fixes or Phase 14 items.
  *(Round 117: four acts, 15 beats, both sides played. ACT A (the
  wound): crit cut → sepsis → sleepless night loses the race →
  priest-assisted Battle Medicine → the inn night wins it, with
  the DM's dream and well_rested both firing on the same sleep.
  ACT B (the thief): witnessed vs quiet break-ins behave
  differently (Karim rounds on you at HIS watchtower — correct),
  theft flags, honest refusal, fence at 60% behind quiet-hands,
  armor disguise walks past the guard, plain clothes confronted,
  talk-then-pay clears. ACT C (the trader): buyout raises the
  smith's price, the haggle meter nods 5%, the bread run pays
  0.8→1.3. ACT D (the friend): the cup mints 30 bond, trust opens
  Goren's locked secret, despised merchants show the door, and
  exhaustion-3 reaches Persuasion through the check core.
  FINDINGS: 0 expectation failures; one real fix — Battle Medicine
  burned a bandage + the daily immunity for +0 HP on a whole,
  uninfected patient; it now refuses ("save the bandage") with a
  regression test. One emergent charm noted, not fixed: the bond
  ceremony happily shares a STOLEN bottle. No Phase 14 forced —
  the next phase should come from George's own play. Suite 1145,
  green x3.)*

## Phase 14 — Hygiene & horizons (opened 2026-07-11)

With every feature phase complete, this phase holds engineering
debt and the door to whatever George's next play session surfaces.

- [x] **P14.1 The engine under the line.** game_engine.py had sat
  at 784 lines against the hard 500 rule since the subsystem count
  exploded. Split without behavior change: `engine/engine_setup.py`
  (`build_subsystems` — construction in dependency order, moved
  verbatim from __init__) and `engine/turn_pipeline.py` (`run_turn`
  — the whole per-minute pipeline including the nightly stack,
  moved verbatim from advance_turn; block order is load-bearing).
  game_engine.py is 438 lines; NO file in the repo now exceeds
  the rule. Suite 1145 green x3 through the split (two extraction
  slips — module-scope imports and an indent — caught by the suite
  within minutes).
- [x] **P14.2 Candidates awaiting a pull** (pick when wanted, no
  order) — ALL PULLED: ~~DOS2 leftovers (blood pools, electrified water)~~
  *(Round 119, done: serious wounds (damage ≥5, overworld) splash
  BLOOD pools (40 turns, dark red overlay); blood CONDUCTS but
  never burns. `surfaces.electrify(x,y)` races a charge through
  every connected conductor — water surfaces, WATER terrain, blood
  bridges — cap 30 tiles, 3 turns of 4/turn zap (player floored at
  1 HP), fading back to plain water. The shock spell triggers it
  at a wet target: lure them into the puddle, then shock it. 9
  tests. Suite 1154, green x3.)*; ~~module packs shipping
  structures~~ *(Round 120: packs gain a "structures" section —
  each spec runs the DM charter (define_structure) budget-free;
  known ids skip (Legendarium inheritance); refusals log, never
  kill the pack; structures-only packs valid; validator checks
  cells/monsters/loot. Shipped sample:
  data/module_packs/smugglers_cache.json — a dark cellar under the
  Old Farmhouse: Restless Bones on guard, a chest of lockpicks and
  wine, and a beam scratched "Wulf pays best. Ask no names.")*;
  cooperative ConstructionProject (lands in P15.7); ~~magical sight
  through walls~~ *(Round: done — a `keen_sight` status effect + the
  "Keen Sight" self-buff spell (wizard/cleric/druid, 4 mana, 20 turns).
  While it lasts, `presence.sees_through_walls` is true and the renderer's
  `presence.hidden_by_walls` stops hiding indoor NPCs from the street —
  you glimpse the merchant at his counter through the wall. SIGHT ONLY:
  `npc_adjacent_to_player` is untouched, so reach still stops at the stone
  (you see him but can't barter through it). 6 tests. Suite 1828, green.)*;
  ~~windows~~ *(Round: done — `presence.at_a_window` (the player stands
  within a tile of a building's footprint) folds into the same
  `hidden_by_walls` seam: beside a building you glimpse its occupants
  through the windows, from afar the walls still hide them, and — like
  keen_sight — it's SIGHT not reach (the wall keeps them). 5 tests. Suite
  1833, green.)*. With that the whole P14.2 backlog is emptied.
- [x] **P14.3 Playtest findings (George, live, 2026-07-11).**
  a) "The event log shows events occurring a long distance away" —
  `presence.in_earshot` (Chebyshev radius 14) gates actor-local
  events: NPC-vs-NPC defeats, knockouts, distant giant smashes,
  overnight wakes. The player's own actions and [Realm]/[Board]/
  [DM] world news stay global by design. b) "There should be
  bridges when paths cross water" — TerrainType.BRIDGE: all three
  generated roads lay planked bridges over water instead of
  skipping it; walkable, plank-over-water sprite, wood in the
  tile-damage tables (30 HP — a bridge can burn down to open
  water), floods never claim one. 8 tests. Suite 1162, green x3.

## Phase 15 — Advanced gameplay & superior graphics (George, 2026-07-11)

George: "develop a plan for further development. This should
include more advanced gameplay and superior graphics." Two tracks,
rounds alternating so neither starves. Graphics stays pygame (no
engine swap): the wins are an art pipeline, animation, light, and
UI polish.

**Track G — superior graphics**
- [x] **P15.1 Tileset pipeline.** Loadable PNG tilesets
  (data/tiles/<set>/, one image per TerrainType + entity kind)
  with graceful fallback to the procedural sprites; config toggle;
  a documented contract so any CC0 16/32px pack (e.g. Kenney)
  drops in. One round that turns all later art into data.
  *(Done in commit 9f1e480: `sprite_loader` resolves a tileset via
  `config.TILESET_NAME`/`LLM_RPG_TILESET`, loads+scales one image per
  terrain/entity with per-image procedural fallback; contract in
  `data/tiles/README.md`; `tests/test_tileset.py`. Checkbox missed at
  the time; ticked Round 154.)*
- [x] **P15.2 Animation pass (foundation + first consumers).** The
  math behind the pixels, pulled out of the renderer into a pure,
  headless-testable `ui/animation.py` (the move `battle_camera.py`
  made for the battle screen): interpolation vocabulary
  (`clamp`/`lerp`/`smoothstep`/`lerp_color`), a two-frame animation
  clock (`frame_index`), the P10.3 surface palette as data-with-flicker
  (`surface_fill` — fire flickers, electrified water crackles, water
  shimmers; oil/blood inert), and an eased day/night curve
  (`ambient_darkness`) that ramps the sky minute-by-minute through
  dusk/dawn instead of snapping between morning/evening/night. Wired
  two consumers: `ui/lighting.py`'s night overlay now eases via
  `ambient_darkness` (the moonlight/weather modifiers layer on top,
  fallback to the old discrete table), and `ui/renderer.py`'s surface
  overlays call `surface_fill` (which also SHRANK the renderer, moving
  the colour table into tested math). 19 tests. Suite 1465, green.
  *(Remainder — the entity-animation half needing renderer plumbing
  and/or new frames, tracked as P15.2b: attack lunge + hit shake,
  richer floating damage/heal numbers, lerped camera, two-frame
  terrain sprites. `lerp`/`smoothstep`/`lerp_color` are the ready
  vocabulary for those and for P15.3/P15.4. Walk-bob already exists in
  `body_renderer.update_anim`.)*
- [x] **P15.3 UI skin (styled log + minimap fog).** The message log
  and minimap, coloured. Pure `ui/hud_style.py` (the `ui/animation.py`
  move): `line_color(text)` paints each event-log line by its
  load-bearing prefix ([!] red, [Law] gold, [DM] violet, [Home] tan,
  [Bond] green, … the full family) and falls back to the SEMANTIC
  category — reusing `event_filter.categorize`, the single source — so
  unprefixed lines still read right (a foe's blow orange, your own acts
  neutral, ambient chatter dim); and `dim`/`fog_terrain_color` give the
  minimap the P15.11 fog of war the main map already has — full colour
  where visible, dimmed where only remembered, near-black where unseen,
  with NPCs hidden on tiles you can't currently see. Wired into
  `hud.draw_event_log` (`_draw_lines` gained a per-line `color_fn`) and
  `hud.draw_minimap` (guarded `_minimap_fog`, so it draws in full before
  discovery has ticked). 12 tests. Suite 1489, green. *(Remainder
  P15.3b — the untestable pixel half: 9-slice paneled borders and the
  procedural NPC-portrait face compositor for the dialog box.)*
- [x] **P15.4 Light & weather II (colour + atmosphere).** The
  colour decisions behind the lighting, pulled into a pure
  `ui/light_palette.py` (the P15.2/P15.3 move): `light_color(kind)`
  gives coloured light SOURCES (forge orange, marsh-wisp blue-green,
  torch warm, …) and `sky_tint(hour, conjunction, weather, season)`
  gives the whole-sky wash — a green AURORA on clear conjunction nights
  (P8.1's two moons together) and a cool winter CHILL while it snows or
  on a deep winter night — fading in on the same eased night curve
  (`ambient_darkness`). Wired into `ui/lighting.py`: marsh wisps now
  punch blue-green light into their bog (distinct from your warm
  torch), and after the darkness pass the overlay blends the sky tint
  (`_apply_sky_tint`). 14 tests. Suite 1511, green. *(Remainder
  P15.4b: shadow direction by sun hour, rain ripples on P10.3 water
  pools, and forge/hearth interior colour — the pieces that need new
  render passes rather than a tint.)*

**Track A — advanced gameplay**
- [x] **P15.5 Companion depth.** Loyalty arcs on the bond system:
  personal quests at bond thresholds, authored travel banter
  (data, per NPC), tactical orders (hold / focus / flee at hp%),
  and a camp-scene role in the P12.6 night.
  *(Round 122, gameplay-first per George: PERSONAL QUESTS gated by
  a bond high-water mark — quests.requires_bond, unlocked once
  bond_earned (trust is not un-earned by spending) crosses the
  threshold; ships Melody's "The Lost Ballad" at bond 25. BANTER
  from data/banter.json (per-NPC + per-class fallback), one line
  every 45 quiet turns, cycled per companion, in the turn
  pipeline. TACTICAL ORDERS via /order follow|hold|flee (party
  only): hold plants them (fights adjacent, never trails), flee
  breaks a wounded companion (<30% HP) away from melee. CAMP
  WATCH: a companion on the P12.6 night drops the ambush chance
  25%→10% ("takes the first watch"). 8 tests. Suite 1176, green
  x3.)*
- [x] **P15.6 Boss set-pieces.** Three authored boss fights as
  data: telegraphed AoE, phase changes at hp thresholds, arena
  surface play; loot worth the fight; Legendarium record on the
  kill.
  *(Round 126: `engine/bosses.py`, data-driven via a `boss`
  behavior block. TELEGRAPHED AoE — the boss marks a tile this
  turn ("the ground blackens beneath you — MOVE!") and blasts it
  next turn (maims, never kills), so attention saves you;
  `boss_tick` runs it from the conflict scan. PHASE CHANGES —
  `boss_on_damaged` fires once-only actions at HP fractions:
  the Giant Warlord ENRAGES at 40% (+STR), the Tyrant of the
  Depths FLOODS its den at 50% (P10.6) and SUMMONS bog lurkers at
  25%, the Wisp Queen ELECTRIFIES her pool (P14.2a) and calls
  three wisps at 50%. Three boss templates in monsters.json; the
  deepest dungeon floor now spawns the real tyrant_depths. Loot +
  the Legendarium record ride the normal defeat path (a slain boss
  is a legend free). 9 tests. Suite 1213, green x3.)*
- [x] **P15.7 Claim a home.** Buy a derelict from the homes
  system; the ConstructionProject candidate lands here (repair to
  move in): storage chest, private-room rest quality, hearth
  kitchen, boss trophies displayed.
  *(Round 155: `engine/homestead.py`. CLAIM — stand inside an unowned
  derelict (the P9A.3 homes system already flags them) and press E to
  buy it for a size-scaled price; ownership rides `location.properties`
  (already save-serialised). REPAIR — a staged ConstructionProject
  (3 stages, each spending timber + stone + coin + a couple of hours,
  E to advance, trains Crafting); the final stage clears the derelict
  flag, restores the interior description, and FURNISHES it — a bed,
  hearth, and storage chest are guaranteed. LIVE IN IT — sleeping at
  home rests you Well Rested for FREE (wired into `rest.py`; a broke
  hero can still sleep in their own bed), the hearth cooks (existing
  P9A.2 furniture), and the chest is your own persistent storage
  (deposit from the I-panel with H, withdraw at the chest with E) held
  as item dicts on `player.metadata` — save-safe, round-tripped through
  a full save/load in the tests. One home at a time. E-key + hint-bar +
  I-panel wired. 12 tests. Suite 1477, green. REMAINDER (P15.7b): boss
  TROPHIES displayed in the home, a pick-any storage panel (withdraw is
  top-item-first for now), and the cooperative multiplayer
  ConstructionProject.)*
- [x] **P15.8 Roads earn their keep (speed core).** ROAD/BRIDGE
  travel is now genuinely faster: `traversal._road_pace` makes every
  Nth stride on fast ground FREE — the world doesn't tick, so a road
  costs fewer minutes AND meets fewer wilderness encounters (the safe,
  quick way), mirroring the P11.4 haste turn-economy. A clean integer
  stride counter (free every 3rd step ≈1.5× pace; every 2nd ≈2× while
  `mounted` — the forward hook for the mule) resets off-road, and the
  road advertises itself once ("You make good time on the road.").
  Wired into `advance_after_move` ahead of the haste check; state on
  `player.metadata` (save-free). 8 tests (the stride pattern on/off a
  mount, bridges count, open ground never frees + resets, a free step
  skips the tick, six road strides cost 4 turns vs 6 on open ground,
  the one-time advert). Suite 1497, green.
  *(Remainder P15.8b DONE — the pack MULE: `engine/mount.py`. Bought at
  a stable (`buy_mule`, `stable_nearby`, 120g), it adds +8 carry slots
  (`carry.capacity`), flips `mounted` so every SECOND road/bridge step
  is free (the 2× road pace the P15.8 counter already had wired), and
  trails a step behind you (`mule_follow`, run from `player_actions.move`
  beside the pet trail). E-key at a stable buys it, hint-bar advertised;
  state on `player.metadata["mule"]` round-trips a save. 11 tests
  (none-at-start, stable-only sale, buy costs gold & grants it & lifts
  carry, the mule takes the overflow, it flips mounted, no-stable/
  can't-afford/no-second-mule refusals, it trails behind, release lets it
  go, survives a save). Suite 1847, green. Remainder P15.8c: the mule as
  a KO-able body under ransom rules (a real follower entity), and the
  diary-unlocked Stonepine BOAT crossing.)*
- [x] **P15.9 Character detail: body-part health (George, live
  2026-07-11).** DETAILED HEALTH SYSTEM: body-part damage (head/
  torso/arms/legs) with consequences, layered under HP/dying.
  *(Round 123: `engine/wounds.py`. Five parts, severity 0-3
  (sound/bruised/wounded/crippled). A hit for 6+ rolls a random
  part up one rung (torso weighted 2x — biggest target); chance
  scales with the blow. HEAD wounds dock every d20 (into
  roll_check beside conditions/exhaustion), ARM wounds dock attack
  (the BETTER arm swings — worse arm ignored), LEG wounds add
  minutes per step (into traversal), TORSO wounds drop the
  effective-HP ceiling 15%/rung (needs turn; a no-op with a sound
  torso so it never claws back the Hearty Brew overheal — a real
  interaction the suite caught). A CRIPPLED limb festers (raises
  P12.12 infection). Knit: 2 rungs per inn night, 1 per camp,
  worst-first; Battle Medicine (P12.8) also sets the worst limb.
  Hint bar reads what's broken. State on player.metadata (save-
  free). 12 tests. Suite 1188, green x3. REMAINDER: the "more
  skills beyond the 8" half — track separately as P15.9b when
  wanted; the health system was the meatier request.)*
- [x] **P15.10 Equipment II (George, live 2026-07-11).** Equipment
  management that "makes sense": two-handed rules, set bonuses,
  durability + encumbrance surfaced.
  *(Round 125: TWO-HANDED enforcement in equipment.equip — a
  two-handed weapon needs both hands, so equipping one STOWS any
  shield ("both hands on the X"), and a shield is refused while a
  two-hander is held ("no room for a shield"); one-handers leave
  the shield up. SET BONUSES: armor pieces tag metadata.armor_set;
  2+ matched worn pieces (armor/shield/boots) grant +1 AC each,
  folded into effective_ac — the Iron set (chainmail + iron_shield
  + iron_boots) rewards a full kit +3. The I-panel already showed
  durability per row; added a status line (effective AC, active
  set bonus, pack N/capacity). 6 tests. Suite 1204, green x3.
  REMAINDER: the character SPRITE reflecting worn gear —
  body_renderer draws weapons by CLASS, not the equipped item;
  that's a Track-G graphics round (P15.10b) since it's untestable
  pixel work.)*
- [x] **P15.11 Fog of war / map discovery (George, live
  2026-07-11).** The overworld is NOT known at start: an explored/
  visible mask over the map — tiles are unseen until in view (the
  P8.6 FOV shadowcaster already blocks LOS through buildings/
  mountains/forest), then remembered as "explored" (dimmed) once
  left. Unseen tiles hide their NPCs and monsters. Reveal by
  exploring, by bought/found maps (a data item that paints a
  region explored), by being told (an NPC marks a POI), or by
  magic (a Farsight spell). Renderer draws unseen black, explored
  dim, visible full; the minimap follows.
  **Event-log corollary (George, live 2026-07-11):** the log obeys
  the same visibility — it describes only what the character can
  see or hear. P14.3a already gated actor-local combat events by
  earshot; this round EXTENDS that audit to every actor-local line
  (spell hits far off, surface fires, NPC schedule moves) using the
  FOV mask, not just Chebyshev distance. Deliberately KEPT global:
  [Realm]/[Board]/[DM]/[Legend] world news and rumor — those ARE
  the "revealed by another route" the request allows (word travels,
  the DM narrates, the board posts).
  *(Round 127b, George's follow-up "the log still shows too much,
  especially inside buildings; give the player display options":
  `engine/event_filter.py` — a DISPLAY-side filter (memory keeps
  every line, load-bearing). Events categorize by
  prefix/content (critical/combat/player/news/law/social/ambient);
  a per-player VERBOSITY (quiet/normal/verbose, SHIFT+L to cycle,
  default normal) gates categories, and INSIDE a building ambient
  overworld noise (footsteps, [Clash] street fights, idle NPC
  barks) is hidden — you can't see the street — while news/rumor
  still reaches you. HUD shows the filtered last 10 with the mode
  in the title. 8 tests.)*
  *(Round 124: `engine/discovery.py`. Per-turn `update` recomputes
  the VISIBLE set from the player via the P8.6 shadowcaster
  (buildings/mountains/forest block sight) out to
  effective_visibility()+2, folding it into a persistent EXPLORED
  set on player.metadata (save-safe: the JSON encoder now writes
  sets as sorted lists, round-tripped back). Renderer draws unseen
  black, explored dim (shaded), visible full; actors on unseen
  tiles aren't drawn (actor_hidden). REVEAL ROUTES: walking; a
  Regional Map (charts settlements) and Explorer's Chart (the whole
  realm) as use_effect.reveal items (general store); and the
  Farsight spell (wizard/druid, self-cast) charts an 18-tile disc.
  EVENT-LOG COROLLARY: NPC-vs-NPC defeats and [Clash] lines now
  gate on `can_witness` (fresh overworld_los, not a stale cache),
  so only fights the player can SEE are logged — extending P14.3a's
  earshot to true sight; world news/rumor stays global. Lesson: the
  first cut gated targeting on the per-turn cache and broke 21
  combat tests that stage mid-turn without a FOV recompute — the
  targeting gate was redundant with can_hit's own true-LOS, so it
  came out, and can_witness switched to fresh LOS. 10 tests. Suite
  1198, green x3.)*
- [x] **P15.9b Skill breadth (deferred half of P15.9).** More
  lattice skills for richness beyond the 8 (a combat/social/craft
  spread), each with a pet, a teacher, and a use-site that trains
  it — sized as its own round.
  *(Round 159: three new lattice skills across the spread —
  **bartering** (social), **hunting** (combat), **carpentry** (craft) —
  each shipped with the full kit: a definition in `data/skills.json`, a
  skilling PET in `data/pets.json` (Sterling the magpie / Scout the
  hound / Chip the beaver), a TEACHER via the bond lesson (new
  `CLASS_TEACHES` rows rogue→bartering, barbarian→hunting,
  artificer→carpentry), and a USE-SITE that trains it: every completed
  shop deal sharpens bartering (`economy_system` + the B-key
  `shop_panel`), felling a WILD BEAST (not a person or construct) trains
  hunting (`combat_system._handle_defeat` → `skill_progression.
  train_hunting`), and repairing your home trains carpentry
  (`homestead.repair`). A shared `skill_progression.train_skill(engine,
  id, xp)` helper is the one-liner every use-site calls — award XP, log
  the level-up, roll the pet — and it fixed a latent P15.7 bug where
  home repair awarded XP to a non-existent "crafting" skill (silently
  dropped). 10 tests. Suite 1521, green. The pattern is now a template
  for any future skill.)*
- [x] **P15.12 Playtest Campaign 5.** Both-sides session across the
  P15 systems; findings become fixes or Phase 16.
  *(Round 160: drove the P15 mechanisms end to end — homestead, roads,
  skill breadth, the atmosphere layer, the agent roster. Most passed
  clean (roads saved time on the real move path, a trade + a hunt
  trained bartering/hunting, a snowy conjunction night rendered with a
  wisp, an agent hero moved on its own). ONE real finding, fixed this
  round: the only derelicts a fresh world produced were a WELL and a
  SHRINE — so P15.7 homestead was both nonsensical (you could "buy the
  village well") AND unreachable (no derelict dwelling existed). Fix in
  four parts: `homestead._is_dwelling` rejects infrastructure kinds
  (well/shrine/stall/…); `homes.assign` marks any "Abandoned …" building
  genuinely derelict with no residents; a "cottage" keyword maps to a
  farmhouse dwelling interior; and an **Abandoned Cottage** is seeded in
  the wilderness — so 8/8 sampled worlds now offer a claimable starter
  HOME (the Cottage + the already-present Abandoned Watchtower). A
  fragile worldgen-RNG assumption in `test_foraging` (first water tile =
  fishing) surfaced from the new building shifting placement; hardened
  to pick a genuine fishing node. `tests/test_playtest5_findings.py`
  (8 checks) locks the scorecard. Suite 1529, green.)*

## Phase 16 — Living world imports (Autonomous World survey, 2026-07-11)

George asked for another pass over the sibling `autonomous_world`
project (worldgen, building graphics/types, economy & resource
creation). A survey agent ranked the highest-value imports NOT yet
taken. Ordered by value; each is a data-first port sized to
llm_RPG's architecture (no chunk streaming — our map is a fixed
grid).

- [x] **P16.1 Supply-chain data model.** Port AW's
  `data/supply_chains.py` shape as `data/production.json`: every
  item gets an ORIGIN — raw materials (gatherer profession, source
  tile, yield, tool) and crafted goods (crafter profession,
  workstation, skill, level). Pure data; gives every object a
  producer and every profession a purpose. Foundation for P16.2.
  *(Round 161: `engine/production.py` builds ONE unified `origin_of`
  view, DRY by construction — the mining/woodcutting/fishing raws come
  from `gathering.json` and the crafted goods from `recipes.json` (so
  those single sources never drift), merged with `data/production.json`,
  which adds only what they lack: the profession layer (miner/smith/
  cook/…→skill), the workstations (smithing→forge, cooking→hearth, …),
  and the farmed/foraged/hunted raws outside the gathering nodes
  (wheat_sheaf/herb_bundle/bogcap/wolf_pelt). 13 raws + 12 crafted, the
  full ore→bar→sword chain intact. Queries: `origin_of` / `is_raw` /
  `is_crafted` / `raw_materials` / `crafted_goods` / `producers(prof)` /
  `profession_of` / `inputs_of` / `source_of` / `all_professions`.
  Validator `_check_production` cross-refs skills/items/professions/
  sources; 12 tests including a coverage sweep (every gathering tier +
  recipe has an origin) and a chain check (every crafted good grounds
  out in raws). Suite 1541, green. The producer/profession map P16.2's
  NPC work loop stands on.)*
- [x] **P16.2 NPC production loop (gather + craft core).** AW
  `systems/npc_work.py` FSM adapted: instead of pathing every villager
  to a tile each tick (a forbidden per-tick cost), the economy resolves
  ABSTRACTLY once per game-day in the nightly stack beside the faction
  ticker. `engine/production_loop.py` `ProductionSystem`: each
  settlement keeps a STORE ({item: qty} larder); its resident producers
  work it — GATHERERS (woodcutter/forager/fisher/hunter) pull their raw
  into the store, CRAFTERS (cook/alchemist/smith) consume the inputs the
  store holds and turn them into goods. Who works where is FREE from
  existing data: an NPC's class → skill (`CLASS_TEACHES`) → profession +
  outputs (P16.1) — so a village of villagers, a cleric and a wizard
  quietly turns fish/herbs/logs into cooked meals and potions, night
  after night, and the log breathes one quiet line a day. Settlement
  detection excludes buildings that merely carry the word (the "Village
  Well" is not a town — same P15.12 lesson). Larder capped; heuristic,
  no per-tick LLM; stores persist (save_load + a round-trip test). 10
  tests. Suite 1551, green. *(Remainder P16.2b — merchant ARBITRAGE
  done: production_loop._arbitrage runs each night after production —
  for every good a caravan carries CARAVAN_LOAD from the settlement
  with the GLUT to the one with the SCARCITY when the gap is real
  (CARAVAN_MIN_GAP), so plenty flows to want (the villages' surplus
  drifts toward the consuming town/castle) and the log breathes one
  quiet '[Realm] A caravan carried N from A to B' a day; nothing is
  minted or lost. 7 tests. Suite 1854, green.)*
  *(Remainder P16.2c — SHOP STOCK feeding done: `shop._stock_from_surplus`
  (run when a merchant (re)stocks) moves up to `SHELF_STOCK` of each good
  in the NEAREST settlement's production store onto the merchant's shelves
  and decrements the store — the village that cut the logs (or, with a
  crafter, cooked the fish) now SELLS it, composing with the P12.10
  elastic prices and the merchant's gold budget scaling to the fuller
  stall. The produce → caravan → shop → player loop is closed; nothing is
  minted moving to the shelf. 6 tests. Suite 1860, green. Remainder
  P16.2d: the smith/ore chain stays dormant until a MINER profession has
  an NPC class to inhabit it (no class teaches mining yet).)*
- [x] **P16.3 Building-type catalog + room classification.** AW
  `settlement_buildings.SPECIALIZATION_BUILDINGS` + `zones._classify_room`
  as data: ~40 typed buildings (dock/warehouse/mill/granary/
  smelter/sawmill/bakery/brewery/stable...) beyond our six, a
  settlement specialization ("mining town → smelter+mine+
  warehouse"), and furniture→room-function so an anvil-bearing
  room IS a smithy whose owner works there. Ties P9A furniture to
  occupations.
  *(Round 163: `data/building_types.json` — a 24-kind catalogue mapping
  each building KIND → a FUNCTION, the producer PROFESSION that works
  there (from P16.1's set, or null for civic/service), and the MARKER
  furniture that identifies the room — plus three settlement
  SPECIALIZATIONS (mining/farming/coastal). `world/building_types.py`
  loads + queries it: `profession_of_kind`, `is_workshop`,
  `classify_interior` (an anvil-bearing room → smithy, an altar room →
  temple). Wired straight into the P16.2 loop: an NPC's trade now
  follows their WORKPLACE building first (`_building_profession` — by
  blueprint kind, else by furniture) and only falls back to their
  character class — so the Old Farmhouse's villagers are FARMERS (were
  woodcutters-by-class), the Hunter's Lodge a hunter, the forge a smith,
  the Wizard's Tower an alchemist. Validator `_check_building_types`
  cross-refs professions + specialization kinds; 10 tests. Suite 1561,
  green. *(Remainder P16.3b: worldgen PLACING the new economic kinds
  (mine/bakery/sawmill/dock) and applying a settlement's specialization
  — which is what finally staffs a MINER and lights the dormant ore→bar→
  sword chain from P16.2.)*)*
- [x] **P16.4 Resource nodes & regrowth.** AW resource tiles
  (ORE_VEIN/HERB_PATCH/BERRY_BUSH...) with `leaves_tile` +
  `forest_regrowth`: gathering becomes destructible-tile
  interaction (composes with P10.2) that regrows over time.
  Feeds P16.1's raw-material sources.
  *(Round 164: `world/resource_nodes.py` `ResourceNodeSystem` — a node
  sits on matching terrain with CHARGES; harvesting spends one, and a
  dry node TRANSFORMS the tile (`leaves_tile`) so it can't be worked
  again until it REGROWS after `regrow_days` and the ground returns.
  Seeded at world start (12% of matching tiles), ticked nightly, hooked
  into `gathering.gather`, persisted. This first cut ships GROVES: chop
  a forest tile four times and it falls to GRASS — which, being no
  longer a woodcutting node, takes itself out of the gathering pool, so
  a stretch of woodland can be logged out — then after six days the
  forest grows back and refills. Kinds are data (`resource_nodes.json`);
  ore veins / herb patches / berry bushes are a config addition
  (P16.4b). The P16 economy validators moved to `items/validate_economy.py`
  (data_validate was brushing 500). 10 tests (seed on forest +
  idempotent, harvest spends a charge, wrong skill spends nothing,
  felling → grass + regrow scheduled, regrows only after its rest,
  chopping a grove via the real gather path, and a full save/load).
  Suite 1571, green.)*
- [x] **P16.5 2.5D building render.** AW
  `ui/renderer_buildings.py` (`_draw_building_heights`,
  `_draw_pitched_roofs`, per-kind roof tiles): a render pass that
  gives top-down buildings lit cube faces + pitched-roof shading,
  tileset-compatible (shades over the P15.1 PNG base). The biggest
  single graphics upgrade for the least code — belongs in Track G.
  *(Round 165: `ui/renderer_buildings.py`, the Track-G way (pure math +
  a thin pass, like animation/hud_style/light_palette). Each BUILDING
  tile becomes a little block — its roof LIFTED by a per-KIND height
  (`height_for`: a wizard's tower stands taller than a farmhouse than a
  well), a shaded FRONT wall below it (`cube_faces`), and the roof split
  by a ridge line into a lit northern slope and a shadowed southern one
  (`roof_faces`) — drawn OVER the flat P15.1 tiles the main renderer
  already lays down (so it shades, doesn't replace), respecting the
  P15.11 fog (unexplored tiles skipped). Wired as a guarded one-call
  pass after the terrain loop. 11 tests: heights ordered by kind +
  default + min + scaling, the top face lifted and the front wall
  reaching the base, the ridge splitting lit-north/shadow-south, the
  lit roof brighter than the shadow and the wall darker still, and a
  smoke render over a real building tile. Suite 1582, green. *(Remainder
  P16.5b: per-kind roof COLOURS/tiles — one roof palette for all right
  now.)*)*
- [x] **P16.6 Worldgen leap (elevation rivers core).** AW
  `river_gen._trace_river_path` (elevation → downhill rivers) +
  settlement-site scoring (`world_plan._score_city_location`: near
  water, varied neighbors, off-edge) + shore autotiling. Bridges
  already landed (P14.3b). Replaces "two settlements + a straight road"
  with a seed-reproducible watered map. ADAPT (not full chunk streaming).
  *(Round 166: `world/river_gen.py`, all pure + seed-reproducible.
  `elevation_field` carves a meandering low VALLEY across the map;
  `trace_river` follows its floor downhill from the left edge to the
  right, one water tile per column, its course bending toward the lowest
  of the three tiles ahead — steepest descent, so the water hugs the
  valley. Wired into `WorldGenerator._add_river`, REPLACING the old
  random-walk with a genuine elevation-driven meander (seed stored so
  it's reproducible). Also `score_site` (near-water + terrain-variety +
  off-edge, AW's city scoring) and `is_shore` (land touching water) —
  the ready helpers for settlement placement + shore autotiling. 11
  tests (field shape/determinism/valley, river one-per-column +
  connected + off-edge + follows-the-valley, shore + site scoring, and a
  generated world has a river). The river shift tripped two
  worldgen-position-fragile tests (a fishing shoreline that now touches
  a forest, a place-discovery corner now inside a nested location) —
  both hardened to resolve by property, not position. Suite 1593, green
  x2. *(Remainder P16.6b: ADOPT `score_site` for settlement placement
  and `is_shore` for render-side shore autotiling.)*)*

*Survey SKIPs (recorded, not building): Voronoi/BSP city districts
(overkill for small towns), banking/loans/bonds, and copying AW's
procedural pygame.draw art (we have the P15.1 PNG pipeline — take
the techniques, not the draw code).*

## Phase 17 — The battle screen (George, 2026-07-11) — MAJOR

George: a large-scale tactical COMBAT SCREEN for skirmishes,
battles, sieges, castle assaults and large dungeon/building
encounters — commanders issuing orders to troops, siege engines vs
buildings, cavalry, units cooperating toward commander goals, and
the player able to act as ONE soldier OR as a commander sending
orders. Zoomable (interior-screen scale). Reachable from the START
MENU as a standalone TESTBED, so we prove it in isolation and fold
lessons back into the main game. A deep-research pass (tactical-
combat mechanisms + a sweep of the sibling autonomous_world
project) produced the architecture below.

**Key finding:** autonomous_world already holds a near-complete
tactical brain (`game/systems/colosseum.py` — target-select with
focus-fire, morale/rout, role movement kite/flank/intercept,
rally, siege) and army tables (`game/systems/warfare.py` —
UNIT_STATS, MATCHUP rock-paper-scissors, FORMATIONS,
FORTIFICATION_STATS, a Lanchester auto-resolver). They are
FLOAT/real-time-coupled so NOT importable — but the DATA TABLES
lift verbatim to JSON and the AI HEURISTICS are a ready design
spec to port onto our grid. And our OWN engine already has the
siege primitives: tile_damage (walls→rubble breaches), earthworks
(breach mapping + night masons), surfaces (oil/fire/electrified),
multi-level interiors/structures (wall-walks), squad_tactics
(flank/surround/focus/BFS step), FOV/LOS. The battle SCREEN is the
genuinely new work; most of the phase is porting + integration.

Model: a SQUAD is the commandable object (N soldier tokens, ONE
morale bar — the Total War model) with a Mount&Blade order grammar
(select group → verb). RTWP tick loop decoupled from world-minutes,
seeded/deterministic, heuristic (no per-tick LLM). Zoom = tile-size
LOD: soldiers when zoomed in, one banner+bar blob per squad zoomed
out. Package `engine/battle/` (each file <500 lines):
battle_data / battle_unit / battle_field / battle_orders /
battle_ai / battle_flow / battle_resolve / battle_session, plus
ui/battle_screen and data/battles/*.json. Ordered so each round
is shippable and testable, de-risking UI last:

- [x] **P17.1 Data tables + auto-resolver (headless).** Port
  autonomous_world's warfare tables to data/battles/*.json
  (units, formations, matchups, fortifications) and
  `battle_resolve.resolve(seed)` (Lanchester melee/ranged/siege).
  Validator extended for battle content. Deterministic headless
  tests assert winners/survivors by seed — NO UI. Doubles as the
  richer resolver for faction_ticker/retaliation off-screen fights.
  *(Round 127: `engine/battle/` package — battle_data (loaders over
  data/battles/units·formations·matchups·fortifications.json, all
  16 AW unit archetypes + RPS matchups + terrain + formations +
  fort stats), battle_resolve (Army/Unit/Fort + a seeded
  `resolve`). Two combat laws faithful to AW: melee casualties
  reduced by target DEFENCE (fixed AW's latent bug where defense
  was computed but unused), ranged square-Lanchester softened by
  the RPS matchup and target SPEED (fast cavalry closes and eats
  fewer volleys). Cavalry CHARGE front-loads rounds 1-2; spears
  BLUNT the charge (reduce incoming cavalry); an intact WALL keeps
  besiegers off the garrison (only engines + ranged reach) while
  siege engines batter it to a breach; casualties shield siege
  engines behind the front line. 11 seed-deterministic tests
  (numbers win, cavalry>archers, spears blunt cavalry, commander
  tips it, shield wall holds attrition, siege breaches). Validator
  checks the tables. Also fixed a round-126 bug the suite surfaced:
  tyrant_depths had dungeon:true, adding the boss to the RANDOM
  spawn pool → 2-3 Tyrants intermittently; bosses are placed
  explicitly, dungeon:false now. Suite 1224, green x5.)*
- [x] **P17.2 Squad & soldier model + field.** `battle_unit.py`
  (Squad = tokens + one morale bar; Soldier grid token;
  to_dict/from_dict) and `battle_field.py` (a grid wrapping
  TileDamage + SurfaceLayer). Save round-trip test.
  *(Round 128: `battle_unit.py` — Soldier (light grid token,
  hp/pos/alive) + Squad (owns soldiers, archetype, team, ONE morale
  bar on the body per Total War, order + target, formation,
  commander flag; `raise_squad`, casualties shrink strength,
  morale crossing the threshold ROUTS the whole squad, centroid,
  full to_dict/from_dict). `battle_field.py` — a self-contained
  grid (its own terrain strings, not the world enum): WALL/GATE as
  HP structures that break to a RUBBLE breach ("a breach is a
  lane" — marching-through tested), soldier occupancy so two
  can't share a tile, a squad registry with team/enemy queries,
  and to_dict/from_dict for mid-battle saves. Dependency-light and
  headless. 12 tests incl. squad + field round-trips. Suite 1244,
  green (the two intermittent misses were pre-existing disease/
  director RNG flakes — the battle modules import nothing from the
  game engine).)*
- [x] **P17.3 Group AI ticking a skirmish.** Port the colosseum
  brain grid-native into `battle_ai.py` (focus-fire target select,
  morale/rout, role movement) + `battle_flow.py` (one BFS flow
  field per objective). `battle_session.run_headless(scenario,
  seed, max_ticks)` runs two squads to a result; tests assert it
  converges.
  *(Round 129: `battle_flow.py` — multi-source BFS distance field
  per team (O(map) not O(units)); soldiers step the gradient toward
  the enemy and THROUGH breaches once a wall falls to rubble.
  `battle_ai.py` — focus-fire target select (ordered squad first,
  then lowest HP, then nearest), a self-contained d20 strike
  (melee reach 1 / ranged 5 vs the archetype's stats), role
  movement (archers KITE off an adjacent enemy, everyone else
  advances the flow), and squad morale (strength ratio, local
  outnumbering, allies routing — all on the ONE bar).
  `battle_session.py` — the deterministic tick loop:
  run_headless(max_ticks) returns the resolver's result shape.
  Combat is self-contained on the battle's Soldier tokens (the
  bridge to combat_system for surfaces/wounds is P17.7's embodied
  mode — the headless skirmish stays pure so it tests instantly).
  7 tests: converges to a winner, seed-deterministic, numbers win,
  lines close the distance, the broken side routs, archers trade
  well, result-shape matches P17.1. Suite 1251, green x3.)*
- [x] **P17.4 The battle screen + zoom/LOD.** `ui/battle_screen.py`
  reusing MapRenderer with a variable tile_size {8,16,32,48} and a
  float camera; LOD blob-per-squad below ~16px. Reachable from the
  start menu ("Battle Testbed" → scenario picker). Render only —
  the sim already runs headless.
  *(Round 130: `ui/battle_camera.py` — the pure zoom/pan/LOD math
  (tile_size steps 8→16→32→48, float centre, world↔screen, visible
  bounds, blob_mode < 16px), unit-tested headless. `ui/battle_screen.py`
  — a standalone pygame view (no engine) that watches a
  `BattleSession` tick, drawing terrain, soldiers-or-blobs by LOD,
  and a HUD (tick, per-team strength bars, play/pause, winner banner);
  SPACE play/pause · N step · R reset · +/- or wheel zoom · WASD pan.
  `engine/battle/battle_scenario.py` + `data/battles/scenarios.json`
  — four staged set-pieces the same builder feeds to the screen AND
  the tests: open_field (even melee), numbers_tell (mass wins),
  cavalry_raid (shock horse), storm_the_breach (garrison holds a
  wall gap). Wired into the start menu (Battle Testbed → picker) and
  main.py (menu loops back after a battle). Validator gained a
  scenario cross-check; the module_pack + battle checks were lifted
  to `items/validate_packs.py` + `items/validate_battles.py` to keep
  data_validate under the line. NOTE: "reusing MapRenderer" proved
  the wrong fit — MapRenderer is bound to the world engine/zone, so
  the screen paints the battle's own string-terrain grid directly
  with a shared tile_size concept. 12 tests; suite 1263 green.)*
- [x] **P17.4b Richer testbed (from playtest feedback).** The screen
  works; make it show more.
  *(Round 130, same round: (a) UNIT-TYPE ICONS — `ui/battle_camera.py`
  gained `category_shape` + `marker_points` (pure geometry): a glyph
  per category — infantry circle, cavalry triangle, archer diamond,
  siege square, beast hex, medic cross — drawn in the team colour, so
  an icon reads WHO it is and which side. (b) RANGED TRACERS — the
  session records each ranged shot fired that tick as `(x0,y0,x1,y1)`
  in `session.tracers` (reset every tick, never read by the sim so
  determinism is untouched); the screen draws them as fading arrow
  lines — you can SEE the bows work now. (c) BIGGER BATTLES —
  `grand_clash`: a 120×80 field, 296 soldiers, infantry centre / horse
  wing / archers behind. ~40ms/tick, well under the screen's 220ms
  budget, so it plays smoothly; the exhaustive convergence test caps
  big fields at 25 ticks so the suite stays fast. 8 more tests
  (icons, tracers, scale); suite 1271, green. (d) still open: COVER
  types that blunt ranged fire → folded into P17.6; richer commander
  tactics → P17.5.)*
- [x] **P17.4c Movement speed — the fidelity keystone.** The grid sim
  moved every soldier one tile per tick, ignoring the `speed` field
  the data already carried (cavalry 2.0–2.2, foot ~1.0, catapult 0.2);
  so cavalry couldn't catch archers and "Charge" would mean nothing.
  Fix: a per-soldier fractional movement budget.
  *(Round 131, greenlit "highly realistic battles": each `Soldier`
  gained a `move_accum` (round-trips in to_dict/from_dict); each
  marching tick adds the squad's `speed`, whole tiles are spent and
  the remainder carries — so cavalry cover ~2 tiles/tick, crossbows
  ~0.8, a catapult one tile per five ticks (`MAX_STEPS`=3 caps a
  tick). `Squad.speed` reads the archetype. Wiring this exposed a
  latent pathing gridlock: at 296 units the two masses froze 3 tiles
  apart because the flow field aims at the enemy CENTROID, whose
  front tiles are occupied — `battle_ai.step_toward` adds a greedy
  "push into contact" fallback toward the nearest enemy soldier when
  the flow is blocked (melee units only; archers still hold), and
  `grand_clash` now resolves (~88 ticks, was a 500-tick stalemate).
  Determinism preserved. NOTE: speed alone does NOT flip cavalry-vs-
  archers — massed bows still win, because they fire every tick with
  no reload and arrows ignore armour; those are the next fidelity
  steps (reload/aim, armour/damage-types + shields, then AoE/magic)
  toward the realism arc. 4 tests (cavalry outruns foot, siege
  crawls, deterministic, accum round-trip); suite 1275, green.)*
- [x] **P17.5 Orders & commander overlay.** `battle_orders.py`
  (Move/Hold/Charge/FocusFire/FallBack/SetFormation + Objective
  types capture-point/breach/protect) and the command UI (select
  group → verb). The player commands allied squads.
  *(Round 132: `engine/battle/battle_orders.py` gives the verbs real
  behaviour — `advance_intent(squad)` maps the order to what a soldier
  out of reach does: HOLD roots in place (fights only what comes),
  FALL_BACK withdraws from the nearest enemy at speed, MOVE marches to
  an ordered tile ignoring the foe, CHARGE/FOCUS_FIRE close into
  contact (focus_fire also concentrates target selection, via
  `is_focus` — the legacy "focus" spelling still works). The session
  routes movement through `_order_move` → `_retreat`/`_goto`/`_advance`;
  `pick_target` reads `is_focus`. Command UI in `battle_screen.py`:
  the player commands their team — TAB / left-click selects an allied
  squad (highlight ring), C/H/F/G issue Charge/Hold/Focus/Fall-back
  (Focus & Charge auto-target the nearest enemy squad), M arms a
  click-to-Move; a CMD line shows the selected squad and its order.
  Held defenders now hold the breach instead of marching out — more
  realistic sieges. 11 tests (intent map, hold roots, fall-back
  retreats, move marches, focus concentrates, legacy spelling +
  command smoke); suite 1282, green. REMAINDER: SET_FORMATION is
  settable/plumbed but its grid effect (spacing/defence) lands with
  P17.10; objective types are scaffolded (`OBJECTIVES`) with the
  capture-point VICTORY condition already homed in P17.6.)*
- [x] **P17.6a Cover (playtest ask + realism arc).** Battle terrain
  carries a `cover` value that blunts incoming RANGED hit rolls
  (mirror the P12.7 soft-cover model), with a variety of cover types
  and a scenario that turns on them.
  *(Round 133: `data/battles/terrain.json` gives each grid-terrain
  kind a cover fraction — forest 0.5, sandbags 0.5, hedge 0.35,
  rubble 0.3, open ground 0 — loaded by `battle_data.terrain_cover`.
  forest/hedge/sandbags join the field's PASSABLE cover terrains;
  `BattleField.cover_at(x,y)` reads it. `battle_ai.attack` adds
  `round(cover*10)` to the DC of a RANGED shot only (a swordsman in
  the trees is no harder to hit hand-to-hand). Scenarios can paint
  terrain rects (`build_field` lays them before walls/squads); the
  new `treeline_defense` stands 12 longbows in a wood against an
  18-strong open-field assault, and cover lets the bows hold the
  treeline. Screen renders the new terrains; validator checks cover
  ∈ 0..1 and scenario terrain rects. Measured: forest cuts an
  archer's hits ~1480→1010 per 2000, rubble ~1195. 7 tests (cover
  values, cover_at, ranged-reduced, deeper-shields-more, melee-
  unaffected, treeline paints + converges); suite 1289, green.
  REMAINDER: the AI does not yet actively SEEK cover — units use it
  only where the scenario places them (→ P17.6b).)*
- [x] **P17.6b Siege battering.** Walls/gates are already HP
  structures that breach to RUBBLE (P17.2); make SIEGE units batter
  them — `structural_dmg` applied to an adjacent wall, opening the
  breach the flow field then routes through.
  *(Round 134: `Squad.structural_dmg` exposes the archetype's wall
  damage (ram 25, catapult 35, trebuchet 50; 0 for everyone else).
  The tick loop batters as a siege engine's FIRST action — adjacent to
  a wall (nearest the enemy) it hammers `damage_struct` and does NOT
  shoot the garrison through the stones; the wall drops to rubble and
  the recomputed flow field pours the assault through. Out of reach
  with no adjacent wall, `_siege_approach` crawls the engine to the
  nearest wall (`battle_ai.nearest_struct`); infantry can't breach at
  all, so siege is REQUIRED. New `siege_assault` scenario: an intact
  12-tile palisade, four rams + sixteen foot vs a garrison — the rams
  breach ~tick 15 and the assault takes it. 6 tests (structural_dmg,
  nearest_struct, ram batters, infantry can't, breach→rubble lane,
  siege wins); suite 1295, green. KNOWN SIMPLIFICATION: ranged units
  still have no line-of-sight block through walls in the open field —
  true battle LOS rides with P17.9.)*
- [x] **P17.6c Capture-point victory.** A squad holding an objective
  tile wins without wiping out the enemy — the `OBJECTIVES` scaffold
  from P17.5 made real.
  *(Round 135: `BattleField` carries `objectives` (id/tile/radius/hold
  + mutable holder/hold_count/captured_by), round-tripped in
  to_dict/from_dict; `team_counts_near` tallies who contests a point
  and `captured_team` reports a seizure. Each tick the session runs
  `_update_objectives`: the team that OUTNUMBERS the other inside the
  radius pushes the meter (`_dominant` — a strict lead; a tie is
  contested and bleeds progress back), and holding for `hold` ticks
  seizes it. `over()`/`result()` end on a capture — the winner and a
  new `objective` key name it, so a battle can be won by seizing the
  crest, not only by annihilation. New `seize_the_hill` scenario (a
  central point in a wood): an 18-strong assault takes the hill from
  a dug-in 9 at ~tick 24 while the defenders still stand. Screen draws
  the radius ring, a flag coloured by the holder (filled once taken)
  and a capture meter; HUD says "(captured)". Validator checks
  objective tiles/radius/hold. 7 tests (counts, dominant lead,
  hold-wins-without-massacre, contested-no-progress, round-trip,
  scenario builds + is won by capture); suite 1302, green.)*
- [x] **P17.6d Ranged siege bombardment.** Artillery (a siege engine
  with a `ranged` stat — catapult, trebuchet) stands off and pounds a
  wall from a distance instead of crawling to touch it.
  *(Round 136: `SIEGE_RANGE`=10; the tick loop now picks a siege
  engine's wall-attack reach from whether it has `ranged` — a ram
  (reach 1) must touch the wall, artillery hits any wall within
  SIEGE_RANGE and leaves a lobbed-shot tracer, so it never has to
  close and never shoots the garrison through the stones.
  `_adjacent_struct` generalised to `_wall_in_range(sol, reach,
  target)` (used by both the bombard check and the range-aware
  `_siege_approach`). New `bombard_the_keep` scenario: three
  trebuchets emplaced 8 tiles off a stone wall crack it at tick 4 and
  the footmen storm the breach (red 8/8). 3 tests (artillery bombards
  from range without closing, a ram deals nothing until it touches,
  the scenario breaches + wins); suite 1305, green.)*
- [x] **P17.6e Siege III — AI seeks cover (the tractable third).** The
  boiling-oil `surfaces` paint landed in P17.E4 (`battle_fire.pour_oil`);
  wall-walk elevation via the multi-level stacks stays deferred (it
  needs a multi-LEVEL battle grid the field doesn't have yet — noted
  below). The third piece, **the AI actively seeking cover** (deferred
  from P17.6a), is done. *(Round 144: `battle_ai.cover_seek_step` — a
  foot archer (`category == "archer"`) already in shooting range but
  caught in the OPEN sidesteps to the best adjacent COVER that keeps the
  shot alive (the tile is in `ranged_reach` AND has LOS to the target),
  hunkering in the treeline instead of trading arrows in the clear;
  returns the tile or None to hold. The session's `_seek_cover` fires it
  in the shoot branch — an in-range foot archer ducks to cover this tick
  (spending it) and looses from cover next, converging on the local
  cover max and then holding (no thrash). Mounted archers, siege, and
  melee never hunker. 7 tests (finds the treeline; holds on best cover;
  won't break range for far cover; only foot archers; in-battle: moves
  into the wood then holds, and still kills from cover). Suite 1728,
  green. Remainder: wall-walk elevation (multi-level battle grid) and
  the AI seeking cover WHILE advancing (only the in-range hunker is done)
  — both niche; could yield to P17.7 role-swap.)*
- [x] **P17.7 Player role-swap.** An `embodied` flag on the
  session: set → input routes to normal grid-soldier controls,
  camera locks in; None → commander order layer, free camera; TAB
  toggles. The player's squad runs the same AI, skipping the
  driven soldier.
  *(Round 145: `BattleSession.embodied` = the sid of the ONE soldier
  the human drives. The tick's action loop SKIPS it (`if sol.sid ==
  self.embodied: continue`) so the rest of its squad fights on around a
  soldier the AI leaves alone; the human moves and fights it via
  `embody_move(dx,dy)` (steps one tile, sets `moved_last` so a shot the
  same beat pays the P17.9 move penalty) and `embody_attack` (strikes
  the best in-reach foe through the same `battle_ai.attack` the squad
  uses). `embody(sid)`/`unembody`/`embodied_soldier` round it out (a
  dead driver reads back None). GUI (`ui/battle_screen.py`): **E** drops
  into the selected squad's lead and toggles back out (TAB stays the
  P17.5 squad-cycler, so E is the role-swap key — the one deviation from
  the sketch); in-body WASD/arrows drive the soldier and F strikes; the
  camera `center_on`s the driven soldier every frame (locks in); ESC
  releases to command before it leaves the screen; the command line
  becomes an EMBODIED readout (hp + controls). 11 tests: embody/unembody
  state, dead-driver → None, the tick skips the driver while its mate
  charges on, embody_move steps/blocks-on-a-wall/needs-a-body,
  embody_attack hits an adjacent foe / whiffs out of reach, and a
  headless screen-wire smoke test (E drops in, camera-lock render, ESC
  releases then exits). Suite 1739, green.)*
- [x] **P17.8 Fold-back.** `battle_resolve.resolve` replaces the
  dice in faction_ticker/retaliation off-screen battles; commander
  orders extend to overworld `[Clash]` events; a castle assault in
  the overworld reuses the siege field. Playtest, then Phase 18.
  *(Round 146 — part 1 (faction raids) done: `engine/faction_battle.py`
  bridges the abstract faction layer to the P17.1 Lanchester resolver.
  `army_for(faction, strength)` dresses a faction's 0-100 STRENGTH as a
  real little Army — body count scales with strength, split across troop
  types by shares in `data/battles/faction_armies.json` (guards field
  spears+swords+bows, brigands a mounted rabble, monsters beasts);
  `resolve_raid(atk, atk_str, def, def_str, rng)` fights it with
  `resolve()` and reads back the winner + both sides' survivor RATIOS.
  `faction_ticker._brigand_raid`/`_guard_patrol` now settle the clash
  through it instead of a d10 — the winner is the real battle outcome
  and the strength shed scales with the mauling (`_casualty_hit` = the
  share of the army lost, 1-10, clamped). So a brigand horse-rush can
  founder on the guards' spears, and a beaten side bleeds strength in
  proportion. Validator gained a `_check_faction_armies` referential
  check. 11 tests (army scaling + roster character + fallback + token
  force; stronger side wins, ratios bounded, winner mauled less,
  deterministic; ticker fold-back both ways + bounded casualty hit).
  Suite 1750, green.)*
  *(Round 147 — the faction-ticker fold is now COMPLETE: the three
  off-screen battle events all route through a shared `_clash(atk, dfn,
  terrain)` helper. `_monster_incursion` joined `_brigand_raid` /
  `_guard_patrol` — a beast tide out of the wilds (`terrain="forest"`)
  falls on the village militia, the resolver weighing the beasts'
  terror & charge against the peasants' numbers, and the loser bleeds
  strength by `_casualty_hit`. Retaliation was examined and left alone:
  its `run_night` SPAWNS a converging bounty-hunter NPC for on-screen
  combat, not an off-screen army clash, so there's nothing to hand the
  resolver. 3 tests (beast tide presses in, militia drives them back &
  the warband loses strength, the clash helper). Suite 1753, green.
  Remainder P17.8b (narrowing): the castle-assault-reuses-the-siege-field
  part is DONE — the `castle_siege` scenario ("The Siege of Bloodstone")
  is a full siege set-piece over the P17 field: a stone curtain wall with
  a gatehouse, corner towers and boiling oil, the Bloodstone Guard (spears
  + longbows + keep-guard) defending, and a host with rams + catapults
  that batter the gate down and storm the breach (the victors always pay
  a toll to the walls). 6 tests. Suite 1810, green.)*
  *(P17.8c OFF-SCREEN siege done: `faction_battle.resolve_siege` settles a
  castle assault through the resolver's siege math — `army_for` gains a
  `forts` param so the defender fights from behind walls (a `Fort`), and
  the new `besiegers`/`crown` rosters give a proper siege host (rams +
  catapults) and the garrison (spears + bows). The walls decide it: the
  crown garrison that loses 0/30 in the open HOLDS 30/30 behind its wall
  against a rabble with no engines, while a besieging host with engines
  breaches 30/30. So off-screen faction sieges now reuse the same siege
  field as the on-screen scenario. 5 tests. Suite 1815, green.)*
  *(P17.8d LIVE trigger done — ITEM COMPLETE. `engine/castle_siege_event.py`
  makes the castle a target in the world sim: fired nightly from the
  day-change stack, when the strongest hostile faction swells past
  SIEGE_THRESHOLD it may raise a HOST and march on the castle (a `type:
  castle` location carrying a `garrison` strength, planted by
  `castle_region`). `lay_siege` settles it through `resolve_siege` — the
  Bloodstone Guard fights from behind its walls, so a raw host (≤ the ~100
  faction cap) is turned back at the stone and shattered (loses strength),
  a `[Realm]` "the walls held" beat; only an overwhelming host breaches
  the gate and the castle FALLS (flagged, not besieged again), a `[Realm]`
  "has FALLEN" beat. 7 tests (no castle → no siege; the walls turn back a
  raw host & bloody it; an overwhelming host takes the keep; the trigger
  needs real pressure; a strong realm raises a host; a fallen castle is
  spared). Suite 1822, green. Deliberately deferred: "commander orders in
  overworld `[Clash]`" — the P7.1 overworld conflict is individual d20,
  not squad-based, so the P17.5 order layer has nothing to attach to
  until/unless that becomes group combat; the fold-back's real intent
  (off-screen battles on the real resolver + a castle assault that reuses
  the siege field, now LIVE) is complete, and Phase 18 is built.)*

### Combat fidelity arc (user: "highly realistic battles")
Speed (P17.4c) is the keystone; these layer real tactics on the grid
sim, each data-driven, deterministic, and testable. Sequenced by
payoff — do NOT try to do them all at once. **Researched priority
order** (classical→medieval tactics survey, Spartan/Macedonian/Roman/
Carthaginian/Byzantine/Mongol/medieval — see P17.14 doctrine block):
FACING+FLANK/SURROUND first (P17.11 — highest impact, self-contained),
then positional morale (P17.15), then FORMATIONS with cohesion (P17.16
— the user's "different formations" ask), then bracing/RPS spine
(P17.17, half-done via P17.13), then combined-arms & reserves (P17.18),
then doctrine AI (P17.19), then envelopment/feigned-retreat (P17.20).
Ranged fidelity (P17.9) and armour/shields (P17.10) slot in as the
damage model deepens. The BATTLEFIELD-ENVIRONMENT block (P17.E1–E4:
elevation, terrain/obstacles, LOS, fire) is a parallel track.
- [x] **P17.9 Ranged fidelity.** Per-unit range from `range_factor`
  (longbow reaches farther than a thrown axe); a RELOAD cooldown so
  crossbows/catapults don't fire every tick (they load, then loose);
  a MOVE-AND-SHOOT penalty — shoot accurately only if you held still
  last tick, so archers must stop to aim and horse-archers trade
  accuracy for mobility (the Parthian shot). This is what lets bows
  be devastating-but-slow instead of devastating-every-tick.
  *(Round 141: `Soldier` gains `reload_left` + `moved_last` (both
  round-trip). `battle_ai.ranged_reach(squad)` = `int(RANGED_REACH ×
  range_factor)` so a longbow (1.5 → 7) outreaches a crossbow (1.3 →
  6) outreaches a base archer (5); `reach_of`/`attack`/the session's
  in-reach gate all read it. Loosing a weapon with `reload > 0` arms
  `reload_left = reload + 1`; the session ticks every timer down at
  end of tick and gates the shot (and its tracer) while loading — so
  a crossbow (reload 1) looses every OTHER tick, a catapult (2) every
  third, a trebuchet (3) every fourth, while a reload-0 longbow is
  never gated. The session snapshots start-positions each tick and
  flags `moved_last`; `attack` docks `MOVE_SHOOT_PENALTY` (−4 to-hit)
  from a shot the tick after the shooter moved — UNLESS it's a
  `can_parthian` horse-archer, which looses accurately on the move.
  Data: crossbow reload 1, fire-archer 1, catapult range_factor 2.0 /
  reload 2, trebuchet 2.0 / reload 3. 10 tests (range scaling &
  out-of-range; reload arms/holds/ticks-down-over-a-battle; longbow
  fires freely; move penalty reduces hits but the Parthian shot
  ignores it; round-trip). Suite 1698, green.)*
- [x] **P17.10 Armour, shields & damage types.** Split `defense`
  into armour (value + weight) and a shield (front-arc bonus, worth
  MORE vs ranged than melee); damage carries a type (slash/pierce/
  blunt) that armour resists unevenly (mail shrugs slashes, a pick
  punches through); armour weight taxes `speed`. Now heavy cavalry
  survive the arrow-storm — the missing half of cavalry-vs-archers.
  *(Round 142: `engine/battle/battle_armour.py` (pure) over
  `data/battles/armour.json` — armour CLASSES map an `armour_type` to
  a per-damage-type resist multiplier (mail: slash 0.78 / pierce 1.1;
  plate: slash 0.6 / pierce 0.8 / blunt 1.2 — a mace still tells) and
  a weight; a SHIELD is a FRONT-ARC DC bonus worth more vs ranged
  (+3) than melee (+1). `battle_ai.attack` computes the defender's arc
  once → `shield_dc_bonus` on the DC and `apply_resist` on the damage;
  every field is OPTIONAL so an archetype naming none behaves exactly
  as before. Data: sword=slash+mail+shield, spear/pike=pierce+mail,
  archers=pierce+leather, cav lances=pierce (light+leather+shield,
  heavy+plate+shield), beasts=blunt/pierce. The RPS lands — arrows
  (pierce) shred mailed foot but glance off a plated knight, so heavy
  cavalry finally ride out the arrow-storm; a mace (blunt) is the
  answer to plate; a shield wall turns a frontal charge or volley but
  a flanker steps around it. Two fragile tests honestly retuned
  (elevation's marginal roll now clears the shield DC; the razor-thin
  `seize_the_hill` capture hold 14→10 so the win no longer hinges on a
  2-tick knife-edge). 12 tests. Suite 1710, green. Remainder P17.10b:
  the armour-WEIGHT→speed tax is built + tested in
  `battle_armour.speed_penalty`/`weight_of` but NOT wired into
  `Squad.speed` — the per-archetype speeds already encode heaviness,
  so layering the tax double-counts and, worse, the int-truncated move
  budget lets a 0.2 drop stop a unit moving every tick; wiring it
  wants a base-speed rebalance that separates raw mobility from weight.)*
- [x] **P17.11 Facing, flanking & surround (RESEARCH STEP 1).** A
  per-soldier facing (8-dir) + front/flank/rear arc test.
  *(Round 138: `engine/battle/battle_facing.py` — pure geometry:
  8 compass `DIRS`, `dir_index`, `face_toward`, and `arc(facing,
  attacker_pos, target_pos)` → front/flank/rear (front = the 3 tiles
  faced, flank = the 2 sides, rear = the 3 behind). `Soldier.facing`
  (round-trips) is set as a man moves (he faces the way he goes — so
  a runner shows his back) and as he fights (he turns to his target).
  `battle_ai._position_mods` folds three bonuses into every strike:
  FLANK +2 to-hit/×1.25 dmg, REAR +4/×1.5, a target with ≥2 adjacent
  foes +2/×1.25, and SURROUNDED (≥4 adjacent or boxed in) ×1.5 dmg
  taken. The charge landing also takes the arc bonus, so an overrun
  that carries a rider into a flank is murderous. Measured: a rear
  strike averages 4.25 dmg vs 2.59 to the front — a 64% edge from
  behind. 8 tests (arc geometry, escalating mods, gang-up, surround,
  rear-is-deadlier, facing-updates-on-move, round-trip); suite 1321,
  green. The morale side of flanking (rout acceleration, cascade) is
  P17.15.)*
- [x] **P17.12 Area effects & battle magic.** Catapult/trebuchet and
  fireball blast RADII hit a tile cluster and paint `surfaces`
  (fire/oil/electrify already exist); battle-mage units cast the
  existing spell effects. Explosions, boiling oil, and magic land
  here.
  *(Round 143: `engine/battle/battle_aoe.py` (pure over the field) —
  `tiles_in_radius` (the Chebyshev cluster, clamped in-bounds),
  `blast` (damage everything in the burst, fiercest at the point of
  impact fading one ring outward via `_falloff`; soldiers take
  armour-typed damage per P17.10, structures crack unless `hit_structs`
  is off; returns hit/killed), `fireball` (a blast that also IGNITES the
  cluster so the flame lingers & spreads via the E4 `battle_fire.tick`
  — fire ignores armour), and `cast(spell,…)` routing fireball / oil /
  plain blast. Wired into the session two ways: siege artillery with a
  `blast_radius` now SPLASHES the ranks packed around the wall it hits
  (the wall still takes the direct `damage_struct`; the splash is
  soldiers-only), and a new `battle_mage` archetype (spell `fireball`,
  reload 2) casts an AREA burst at its target's tile through
  `_cast_spell` instead of a single strike, reload-gated like any heavy
  shooter. Data: `battle_mage` support unit, `blast_radius: 1` on
  catapult/trebuchet, and a `the_war_mage` testbed scenario (mages
  behind a spear guard fireball a packed sword block — converges in
  ~25-30 ticks, leaving 17-42 tiles of scorched earth). 11 tests
  (geometry, falloff, struct cracking & spare, kill count, fireball
  paints fire & ignores armour, oil slick, in-battle: a war-mage
  scorches a cluster and a catapult splashes the man by the wall).
  Suite 1721, green.)*
- [x] **P17.13 Charge & overrun.** Charging cavalry (and huge beasts)
  RUN OVER loose infantry — trampling through — and only stop when
  killed, blocked, or braced against by spears.
  *(Round 137, playtest ask "charging cavalry should run over regular
  soldiers": `Squad.charge_bonus` (>1 = charge-capable — horse; beast
  data got `charge_bonus` too, elephant 1.8 + `structural_dmg` 20 as a
  "huge creature = siege engine"). In melee a charge-capable soldier
  resolves `battle_ai.charge_attack` not a plain strike: braced
  spears/pikes (`bonus_vs_cavalry`) strike the charge FIRST and either
  kill the horse/rider ("repelled") or stop it cold ("stopped");
  against loose foot the charge lands amplified by charge_bonus and,
  if it doesn't kill, `_shove` barges the survivor clear so the rider
  rides through ("overrun") — momentum carries the trample up to the
  unit's speed. A clean parry (miss) lets the footman riposte and
  maybe down the rider. `_charge_melee` rides into each cleared tile.
  Emergent RPS on the grid at last: cavalry 12/0 vs a sword line,
  0/12 vs spears, 0/12 vs pikes; elephants trample too but also die
  on the pike hedge. New `cavalry_charge` scenario (heavy horse ride
  down a sword line). 8 tests; suite 1313, green.)*

### Battle tactics — classical→medieval doctrine (researched)
From a survey of real tactics (hoplite phalanx/othismos, Macedonian
sarissa + Companion wedge hammer-and-anvil, Roman triplex acies/line-
relief/testudo/orbis, Carthaginian Cannae double envelopment, Persian
sparabara, Viking svinfylking, Byzantine Strategikon combined arms,
Mongol tulughma/feigned-retreat/Parthian shot, medieval schiltron/
Swiss pike/longbow-stakes/Wagenburg). Each maps to a concrete grid
mechanic on the existing systems (one morale bar/squad, d20 strike,
RPS+terrain table, cover, flow fields, charge/overrun). Sequenced;
build on P17.11 (facing) first.
- [x] **P17.15 Positional morale.** Feed local outnumbering, flank/
  rear hits, the SURROUNDED state, and an **adjacent-squad-routing
  CASCADE** into the per-squad morale bar; a routed squad flees the
  flow field and can be **run down** (bonus dmg). Cheap, uses P17.11 +
  existing morale, and makes flanking pay off in decisions, not just
  damage. (Also tempers the fragile morale seen in playtest — deep/
  cohesive squads resist; the shove/rout math becomes readable.)
  *(Round 167: four additions to `battle_ai`, the researched-priority
  next after P17.11 facing. A flank/rear HIT in `attack` now shakes the
  target squad's morale (−2 flank, −3 rear) — flanking pays in nerve,
  not just damage. `update_morale` gains the SURROUNDED penalty, but by
  the SHARE of the squad boxed in (≥30% → −4) so a deep squad shrugs off
  a couple of trapped men (the promised tempering), and the routed-ally
  penalty becomes a proximity CASCADE — a rout within 4 tiles panics a
  neighbour (−4, the wing-collapse) where a distant one only unsettles
  (−1). `_position_mods` runs down the broken — a routed target is
  struck at +4 to-hit ×1.5 dmg (fleeing men can't defend); routed squads
  already `_flee` the flow field, so the run-down lands on them as they
  break. 7 tests (rear > flank > front morale, a hemmed-in squad breaks
  but a deep one holds, run-down bonus, close rout panics more than a
  far one). Suite 1600, green.)*
- [x] **P17.16 Formations I — line & loose, with cohesion (the user's
  "different formations").** A formation is a squad property: assigned
  slots, a shared FACING, spacing, and a 0–1 COHESION (soldiers in-
  slot & facing right / living). Two archetypes first: **dense LINE**
  (shield-overlap +2 front-arc defense while a right-neighbour stands,
  depth raises the morale floor, ½ speed, slow to turn, full AoE) and
  **LOOSE/skirmish** (mobile, ½ AoE/missile dmg spread out, no overlap,
  weak floor, easily flanked). Formation BREAKS when cohesion drops
  (flanked slot, failed shove, charged unbraced) → bonuses gone, morale
  step-loss. Gives P17.5's `SET_FORMATION` real grid effects.
  *(Round 168: `engine/battle/battle_formation.py`. COHESION = the share
  of the squad that both faces the body's DOMINANT direction and stands
  beside a mate — a tight, unified line scores 1.0; scatter it or split
  its facings and it falls (a uniformly-TURNED squad stays cohesive,
  which is right). Below the break point (0.5) the formation is BROKEN:
  bonuses vanish and `check_break` latches a one-time −4 morale shock.
  LINE gives a man with a standing right-hand shieldmate +2 FRONT-arc
  defence (wired into `attack`'s DC), STEADIES morale by depth (+1..3/
  tick in `update_morale`), and marches at HALF pace (`_steps`); LOOSE
  takes HALF from missiles/AoE (wired into `attack`'s ranged damage) but
  gets no shield and no floor. `formation`/`formation_broken` round-trip
  in the Squad dict. 13 tests (cohesion of a tight line vs a split one,
  ½ speed, shield-overlap front-only + gone when flanked / mate-down /
  broken, a loose squad taking half a longbow volley, the one-time break
  shock, persistence). Suite 1613, green. *(Remainder P17.16b: explicit
  slot assignment — cohesion uses facing-unity + clustering as the slot
  proxy for now.)*)*
- [x] **P17.17 Bracing & the all-facing formation (RPS spine).** A
  BRACE flag (hold still + face the threat) makes pike/spear **negate
  the charge bonus and strike an interrupt first** (formalises P17.13's
  half-RPS into a stance, not an archetype quirk); the **all-facing
  formation** (orbis/schiltron ring) turns every arc to "front" —
  removes flank/rear bonuses (the surround-counter) at the cost of
  offense + mobility, and is missile-vulnerable (Falkirk).
  *(Round 169: BRACE became a stance — `charge_attack`'s anti-cavalry
  hedge now only fires when the target `_is_braced` (its new `braced`
  flag, or simply holding — so a pike line on `hold` still stops horse
  as before, but one ORDERED TO CHARGE with no brace gets trampled: the
  half-RPS is now a decision). The all-facing RING joined
  `battle_formation` as a third formation: `effective_arc` flattens
  every incoming arc to "front", wired into `_position_mods` AND the
  P17.15 flank-morale in `attack`, so a ring takes no flank/rear to-hit,
  damage, OR morale — the surround-counter. Its price: half speed
  (`speed_mult`), a −2 attack penalty (`attack_penalty`, offense traded
  for guard), and ×1.5 from missiles (`incoming_ranged_mult` — Falkirk).
  `braced` round-trips in the Squad dict. 9 tests (a braced hold-spear
  stops the charge while an unbraced charging one is overrun and a brace
  flag restores it; the ring denies the rear to-hit/damage/morale; ring
  is slow + missile-vulnerable + weaker on offense). No battle-session
  regressions (63 battle tests green). Suite 1622, green x2. *(Remainder:
  a commander BRACE verb + SET_FORMATION→ring in the order/UI layer —
  the mechanics are complete; only the button is glue.)*)*
- [x] **P17.18 Combined arms & reserves (hammer-anvil + wedge core).**
  Hammer-and-anvil (a squad PINNED in front then charged in flank/rear =
  rout trigger), soften-then-shock (a pre-melee missile volley strips
  cohesion/AC then the shock bonus applies — the Roman pilum), **line
  relief/reserve rally** (a spent front squad withdraws through a gap
  while a fresh one steps up / a shaken squad rallies on a reserve line
  behind), and **wedge** formations (Companion/svinfylking/cataphract)
  that concentrate the charge and breach a line.
  *(Round 170: the two self-contained "pin and break" mechanics.
  HAMMER-AND-ANVIL — in `attack`, a flank/rear blow that lands while a
  DIFFERENT enemy squad pins the target's FRONT (`_is_pinned(...,
  exclude=atk_squad)`) triggers a −6 rout-shock on top of the P17.15
  flank morale; the two-squad requirement is deliberate — a lone squad
  enveloping isn't a hammer-and-anvil (that's already the surround
  bonus), which also KEPT the cavalry-overruns-a-line RPS intact. WEDGE
  joined `battle_formation` as a charge formation: `wedge_charge_bonus`
  gives a charging wedge +3 to-hit in `charge_attack` to BREACH a line,
  bought with zero defensive bonus (a wedge is no shield wall). 6 tests
  (pinned+flanked routs, a flank without a pin is just a flank, one
  squad enveloping is NOT hammer-and-anvil; a wedge breaches a front a
  plain charge stalls against, and gets no LINE/RING guard). No battle-
  session regressions. Suite 1628, green. *(Remainder P17.18b: soften-
  then-shock (a softened debuff a follow-up melee exploits) and line-
  relief / reserve-rally (movement AI — a spent squad withdraws through
  a gap, a fresh one steps up).)*)*
- [x] **P17.19 Doctrine AI (brace-vs-charge + commit-reserves core).**
  Teach the commander AI to deploy in templates (screen → anchor centre
  → reserve cavalry → commit at the decisive point), **anchor flanks on
  terrain**, refuse a flank / oblique order, **brace when it sees a
  charge coming**, and commit reserves where a local advantage already
  exists. Makes the above legible to a watching player.
  *(Round 171: `engine/battle/battle_doctrine.py` — the squad-level
  instincts that finally make the AI USE the tactics layers, run each
  tick from the session. BRACE WHEN YOU SEE A CHARGE COMING: a brace-
  capable spear/pike (`should_brace`) sets `braced=True` the moment an
  enemy CHARGE unit (`incoming_charger`, charge_bonus > 1 within 6
  tiles) bears down, and stands the hedge down again once it's gone —
  so P17.17's brace stance happens without a human hand. COMMIT WHERE
  YOU WIN: a HOLDING reserve not itself facing a charge and not already
  in melee piles into a nearby fight (`should_commit` — enemy within 8,
  `local_advantage` ≥ 1.5) rather than sitting idle while a won flank
  goes unexploited. `apply` writes the stance back each tick;
  deterministic, no rng. 10 tests (sees/ignores a charge, only
  pike/spear brace, infantry isn't a charger; commits on advantage but
  not when charging / outnumbered / already engaged; a spear line
  braces inside a live `tick`). No regression across the 85 battle
  tests. Suite 1638, green. *(Remainder P17.19b: deployment templates,
  anchoring flanks on terrain, and refusing a flank — the setup-phase
  doctrine that needs a deploy step.)*)*
- [x] **P17.20 Envelopment & feigned retreat (Parthian-shot core).**
  Scripted feigned rout → wheel → sprung flank (with the **don't-over-
  pursue discipline check** that counters it), Cannae elastic-centre
  double envelopment, tulughma encirclement on open maps, and horse-
  archer kiting + the **Parthian shot** (fire while fleeing, no rear-
  facing penalty). Depends on facing+morale+formations+flow being solid;
  delivers the "wow" battles.
  *(Round 172: the iconic self-contained piece, the PARTHIAN SHOT. A
  data flag `parthian: true` on `cavalry_mounted_archer` + `ai.
  can_parthian`; in the session's `_flee`, a fleeing horse-archer looses
  at its pursuer within ranged reach BEFORE spurring on — no facing
  penalty because our model reads the TARGET's arc, not the shooter's,
  so a man firing over his shoulder is unhindered. This needed a real
  fix first: the tick built its soldier list from ACTIVE squads only, so
  a routed squad only fled the ONE tick it broke and then stood frozen;
  now routed-but-alive squads stay in the list and keep RUNNING (and
  Parthian-shooting) every tick. A probe: a broken horse-archer rode
  from (12,6) to (4,6) over three ticks while chipping its pursuer 20 →
  8. 5 tests (only the horse-archer can; it shoots the pursuer while
  fleeing and keeps moving; a routed FOOT archer only runs; a broken
  squad flees every tick, not once). No battle-session regressions. Suite
  1643, green. *(Remainder P17.20b: the scripted feigned-retreat maneuver
  + the over-pursue discipline check that counters it — which needs a
  FEIGN state distinct from a real rout to lure a chaser, since the AI's
  `pick_target` always finds a live foe and so never over-pursues the
  broken today — plus Cannae elastic-centre and tulughma encirclement,
  the deployment-driven envelopments.)*)*

### Battlefield environment (user: hills, ditches, LOS, fire)
Parallel track — the terrain itself as a combatant. Each is data-
driven and folds into the battle grid (its own terrain strings +
`cover_at` + `struct_hp` already exist).
- [x] **P17.E1 Elevation & high ground.** Per-tile elevation (hills,
  depressions, ramparts); attacking DOWNHILL gives +to-hit and adds
  charge momentum, UPHILL costs it; height extends ranged range and
  sight. Anchors the "advantage from being above an enemy" ask.
  *(Round 173: the battlefield-environment track opens. `BattleField`
  gains a sparse ELEVATION layer (`set_elevation`/`elevation_at`, 0 =
  flat, round-trips in the field dict), and `engine/battle/battle_terrain.py`
  turns a height difference into the classic edge, all pure: DOWNHILL
  you strike easier (+1 to-hit per level above, capped ±3) and your
  CHARGE gathers momentum (up to +30% dmg), UPHILL both cost you; and a
  bow on a HILL reaches farther (+1 tile of range per level, capped +2).
  Wired into `attack` (the ranged-range gate + the to-hit roll), into
  `charge_attack` (the momentum multiplier), and into the session tick's
  in-reach test. Zero-cost on flat ground, so every existing battle is
  untouched. 7 tests (the layer + its round-trip; up/down/flat/capped
  to-hit, charge momentum, reach; a downhill blow landing where the same
  roll glances off on the flat; a hill-top archer reaching a target a
  tile beyond ordinary range). No battle regressions. Suite 1650, green.
  *(Remainder P17.E1b: authoring elevation into scenario grids (the field
  API is ready; only the loader hook is missing), and the SIGHT half —
  moot until the battle sim has fog to see through.)*)*
- [x] **P17.E2 Terrain & obstacles.** Ditches/moats/streams/rivers as
  movement-cost or blocking tiles (wade slow, deep = impassable/anchor);
  a flank resting on impassable terrain (river/cliff/wall) **cannot be
  flanked on that side** (removes the arc — the first thing good
  deployment does). Extends the P11.x traversal ideas onto the battle
  grid.
  *(Round 174: two mechanics on the battle grid. OBSTACLES — moat/cliff/
  chasm join `BLOCKING` (impassable, can't be crossed), and stream/ditch/
  bog/marsh join `PASSABLE` but SLOW: `battle_terrain.move_cost` charges
  extra movement budget to enter one, and `_advance` now spends a real
  budget so a rider wading a stream makes visibly less ground than one
  on open turf. ANCHORED FLANK — `battle_terrain.anchored` checks whether
  the defender's flank/rear tile on the ATTACKER's side rests on
  impassable terrain (a river, wall, cliff), and if so `_position_mods`
  AND the P17.15 flank-morale treat the blow as front — so a line with
  its wing on a river takes no flank to-hit, damage, or morale from that
  quarter, the first thing good deployment buys. It matters most for
  RANGED flankers (an adjacent melee flanker can't stand on an impassable
  tile anyway). Zero-cost on open ground. 7 tests (moat/cliff block +
  can't wade; move-cost; wading slower than open ground in a live tick;
  the anchored predicate up/down/front; an anchored flank taking the
  front bonus and no morale where an open one takes the flank). No battle
  regressions. Suite 1657, green. *(Remainder shares P17.E1b's loader
  hook: authoring obstacle terrain + elevation into the scenario grids.)*)*
- [x] **P17.E3 Battle line-of-sight.** Trees/buildings/walls/ramparts
  BLOCK sight (reuse `world/fov.overworld_los`) so ranged units can't
  target through cover — closes the P17.6b "no wall LOS" gap and makes
  cover concealment as well as protection.
  *(Round 175: `battle_terrain.has_los(field, a, b)` walks the line
  between shooter and target and returns False if any tile on it is a
  SIGHT_BLOCK terrain (wall/gate/mountain/forest/building/cliff/rampart);
  the endpoints never block, so an archer fires FROM the edge of a wood
  but not THROUGH it, and low cover (hedge/sandbags) is seen over. Wired
  two ways: `attack`'s ranged branch refuses a shot with no LOS, and the
  session tick gates a ranged unit's in-reach test on LOS so a blocked
  archer REPOSITIONS toward a clear lane instead of freezing behind the
  wall. Started on `world/fov`'s FOV-per-shot but that doubled the suite
  runtime, so it's a Bresenham line-walk (O(distance), same semantics) —
  the suite is back to normal. 8 tests (clear/wall/treeline/hedge/self-
  in-wood LOS; no shot through a wall but a clear lane lands; firing from
  the edge of a wood). No battle regressions; cover is now concealment as
  well as protection. Suite 1672, green.)*
- [x] **P17.E4 Fire & the battle surface layer.** A sparse grid
  `surfaces` layer (port `engine/surfaces.py`): fire arrows, battle-
  magic, and boiling oil (P17.6e) IGNITE oil/forest/wooden structures;
  fire spreads tile-to-tile, damages occupants, and destroys cover/
  walls. Unifies P17.12 (AoE/magic), P17.6e (boiling oil), and the
  *(Round 176 — closes the environment track. `BattleField` gains a
  sparse `surfaces` layer (fire/oil, round-tripped), and
  `engine/battle/battle_fire.py` ports the DOS2 fire model to the grid:
  `ignite` lights a tile (a connected OIL pool floods to fire the instant
  flame touches any part of it), `pour_oil` slicks a patch (boiling
  oil/P17.6e), and `tick` runs each round from the session — a fire
  BURNS the soldier standing in it (−4/tick), EATS combustible terrain
  (a treeline or hedge → bare scorched ground, so cover is gone), GNAWS a
  timber gate/wooden wall to a breach (stone shrugs it off), SPREADS to
  neighbouring combustibles, then gutters out to scorched. A new
  `archer_fire` archetype carries `fire_arrow: true`, and `attack` lights
  the struck tile on a ranged hit — the wired ignition source (magic is
  P17.12). 11 tests (ignite/burn/eat-forest/gut-to-scorched; spread to
  forest but not bare ground; an oil pool all going up; a gate breaching
  while stone doesn't; a fire arrow lighting its target; the surface
  round-trip). No battle regressions. Suite 1683, green. The battlefield-
  environment track (E1–E4) is complete.)*
  Also unifies P17.12 (AoE/magic), P17.6e (boiling oil), and the
  user's "trees and buildings can be set on fire" into one system.

## Playability, UX & a GUI gameplay test (user-directed, HIGH PRIORITY)
User: "Add a major test of the gameplay from the GUI along with a
strong effort for improving the game UX overall and playability."
The battle layer is rich; now harden and smooth the CORE GAME. Take
these next, ahead of more Phase-17 depth.
- [x] **PUX.1 A major GUI gameplay integration test.** One scripted,
  headless end-to-end playthrough driving the ENGINE through the same
  calls the GUI/input_handler makes.
  *(Round 139: `tests/test_gui_playthrough.py` — 12 integration tests
  under one class, each booting a fresh heuristic engine and driving
  the real GUI code paths: new game boots a world with all subsystems
  wired; `move_player` runs the turn pipeline; a wolf spawned adjacent
  is killed via `combat_system.player_attack` and grants XP; `award_xp`
  levels the hero and grows his HP; an item is created, equipped and a
  potion healed; `interact_with_npc` returns dialogue; `accept_quest`
  lands it in `quest_manager.active()`; `economy_system.player_buy/sell`
  moves gold and goods with a spawned merchant; a taught spell is cast
  and spends mana; a building is entered and left; and a save→scribble
  →load round-trip restores gold/hp/position. A `test_full_core_loop`
  chains walk→fight→trade→save/load in one run. Spawns are made
  presence-adjacent by SEARCH (worldgen varies), so it's deterministic
  — 5/5 clean isolated runs, 0.33s. Suite 1335, green.)*
- [x] **PUX.2 Trading II — the merchant screen.** Enrich `ui/shop_panel`
  with quantity/bulk trade, price transparency, and inspect/compare.
  *(Round 140b: `engine/trade_info.py` — pure, tested helpers the panel
  renders: `item_report` (what an item IS), `compare_to_equipped` (its
  delta vs your worn gear), `price_factors`/`factors_line` (the
  reputation × shortage × market × stock × region multipliers that
  were always applied but never shown), `is_junk`/`junk_items`, and
  `affordable_qty`. The panel gained an INSPECT PANE under the two
  columns showing the selected item's stats, the compare line, and the
  buy/sell price WITH its breakdown; Shift+Enter buys/sells ×5 (halts
  when the purse runs dry), and `J` sweeps all common misc trinketry in
  one sell-all-junk. `_transact` refactored into `_buy_one`/`_sell_one`
  so bulk and junk reuse the real path (carry/afford/fence/market
  hooks intact). 15 tests (helpers + headless panel: bulk buy, bulk
  halts broke, junk sweep, selection, crash-free draw); suite 1353,
  green.)*
- [x] **PUX.3 Onboarding & hint audit.** New-player clarity: controls
  are discoverable, the hint bar advertises the help, the reference is
  complete.
  *(Round 141: the audit found the F1/? help overlay was a hardcoded
  ~50-line string list in `gui.show_help` that the text-overlay clipped
  at ~23 rows — HALF the controls never rendered — and it was missing a
  dozen real keys (skill actions SHIFT+T/I/B/H, pray SHIFT+P, carry
  SHIFT+G, pet SHIFT+Z, targeting [/], force-door SHIFT+TAB, log detail
  SHIFT+L, the 1–5 law menu). Fix: `ui/controls.py` — the controls as
  AUDITED, testable DATA (single source of truth, `documented_keys`);
  a `help_columns()` that splits the whole reference into two balanced
  columns at the best section boundary; a `hud.draw_help_overlay` that
  renders both columns so EVERY key fits one screen; a dedicated "help"
  GUI mode any key dismisses; and a standing `[?] all controls` hint in
  the bar when a slot is free (advertises the help itself). 6 tests
  (coverage of the once-missing keys + core verbs, balanced columns
  that fit, no line overflows, section headers, overlay opens/draws/
  dismisses). Suite 1359, green.)*
- [x] **PUX.4a Settings/options overlay + a quit confirmation
  (user-directed).**
  *(Round 142: `engine/settings.py` — the options as persisted DATA
  (`get/set/cycle_setting`, `enabled`): Event log (quiet/normal/verbose,
  sharing event_filter's `log_verbosity` store), Hint bar on/off,
  Mini-map on/off, Sound on/off, Map zoom 24/32/48 — all in
  player.metadata, so they survive saves. `ui/settings_panel.py` — a
  `,`-key overlay: ↕ pick a row, ↔/Enter cycle the value, Esc/','
  close; cycling both persists AND applies live — zoom re-sizes the
  renderer + clears the sprite cache, Sound mutes the SFX, and the HUD
  gates the hint bar / mini-map on their toggles each frame. Also fixed
  a real UX trap the user flagged: **ESC no longer drops the whole game
  outright** — it opens a "Leave the game?" confirmation ([Y] quit /
  [N] keep playing; the window-X still closes immediately). To make
  room, the dialog-typing handler was extracted to `ui/dialog_input.py`
  (input_handler back under 500). 13 tests (defaults/set/cycle/wrap,
  log-detail sharing the filter store, zoom-applies-live, and the
  ESC→confirm→Y/N flow). Suite 1366, green.)*
- [x] **PUX.4b Party panel — reclaim the dead zone.** A party/
  companions panel where nothing used to draw.
  *(Round 143: `gui._compute_layout` gained a `party` region filling
  the old 320×200 bottom-right dead zone — right of the mini-map,
  below the Quests panel — and `hud.draw_party_panel` renders the
  companions there: each ally's name + level, their current order
  (follow / hold / flee, colour-coded), and a health bar; when the
  party is empty it says how to recruit ([P]). 3 tests: the region
  fills the dead zone and overlaps no other panel, the panel draws
  empty, and it draws a recruited companion. Suite 1369, green.)*
- [x] **PUX.4c Responsive layout + resize/fullscreen.** The layout was
  hard-pinned to 1280×800; now it flexes with the window.
  *(Round 144: `_compute_layout` became a pure module function
  `compute_layout(width, height)` — the side/bottom panels scale
  within sane clamps (`MIN_W/MIN_H` floor) and the map fills whatever
  is left, so every region stays valid and disjoint at any size. The
  window is now `RESIZABLE`; the event loop catches `VIDEORESIZE` →
  `gui.resize` (re-lays and never shrinks below the usable minimum),
  and **F11** toggles fullscreen (`toggle_fullscreen`, remembering the
  windowed size) — both documented in the F1/? overlay. 5 tests: valid
  disjoint regions across seven sizes incl. below-min, the map flexes
  with the window, the party stays bottom-right, and a live GUI resize
  re-lays + floors at the minimum. Suite 1374, green. The remaining
  panel-consistency polish (I/B/K/X/J/O) folds into PUX.5's review.)*
- [x] **PUX.5 Playability review.** Run the Playtest Matrix as
  scripted-and-judged sessions; turn friction into fixes or plan items.
  *(Round 145: `tests/test_playtest_matrix.py` — a scripted session
  that WALKS the charter and asserts cross-cutting playability, not one
  system in isolation: (1) Progression — every authored quest's giver
  and every kill/talk target is present in the world or spawnable (NO
  dead ends); (4) Economy — a wolf kill earns loot, a sample recipe
  crafts once its ingredients are in the bag, and a bank/shop sink
  exists to reach; (2/10) Cooperation — a recruited companion joins
  the fight and wounds an adjacent foe; (7) Navigation — travel scopes
  each region's cast (no ghosts follow you over) and the player
  survives it; (12) Feel — quiet verbosity hides ambient flavour that
  verbose shows. All GREEN — the sweep found no critical friction (a
  synthetic "crow caws" line mis-bucketed as player was test noise,
  not a real game line; the event filter is sound). The playtest is
  now a repeatable regression net over the matrix. Suite 1379, green.
  Remaining panel-consistency polish is minor cosmetics; the richer
  next UX beat is the conversation menu (PUX.6).)*
- [x] **PUX.6 Conversation menu system (user-directed).** NPC dialog
  now shows the key things a talk reveals as numbered quick-picks.
  *(Round 146: `engine/conversation.py` — `menu(engine, npc)` builds
  the visible options as data: **Turn in / Accept** every quest this
  NPC gives or takes (`quests_to_turn_in_with` / `quests_offered_by`,
  turn-ins first), **Trade** if they keep a shop (`is_merchant` —
  merchant/cleric/wizard/ranger, correctly NOT guards or brigands that
  merely have an auto-stocked catalog), **Ask about …** each topic the
  player has heard that this NPC can answer (capped), and **press for
  a secret** when one is unlocked. The dialog box lists them numbered
  and grows to fit; the existing empty-field 1-9 hotkeys (which were
  invisible before) now dispatch the menu via `ui/dialog_menu.py`
  (accept/turn-in a quest, open the shop, speak a topic answer, reveal
  a secret) with free text still available. 6 tests (merchant offers
  trade / guard doesn't, a giver offers Accept, items well-formed,
  picking accepts a quest, picking Trade opens the shop, the box draws
  with a menu). Suite 1385, green.)*

## Phase M — Multiplayer & agent-driven characters (user-directed)

The user has asked for multiplayer / MMO: players on different machines
exploring alone or together, forming parties, fighting each other, or
independent; PLUS a way for an agent (Claude) to control a character
through the SAME engine route — to test, to enrich the world, and so a
character keeps living when its human logs off instead of vanishing or
being pure algorithm. This is a large arc; sequenced so the tractable,
networking-free value lands first and the hard client/server piece is
last. Networking was previously deferred — this supersedes that.
- [x] **M.1 The roster/controller keystone.** A clean "who is acting"
  abstraction over the single `engine.player`.
  *(Round 147: `engine/player_roster.py` — `PlayerController` (kind
  human/agent + name, round-trips) and `PlayerRoster` on `engine.roster`
  (wired in engine_setup). Deliberately ADDITIVE: `engine.player` stays
  the ACTIVE character so every existing call keeps working, and the
  roster tracks the wider set beside it — `add(char, controller)`,
  `set_active(char)` (engine.player follows, so all systems now act as
  that hero), `controller_for`, `humans()`/`agents()`. Controllers are
  keyed by character id and each character's kind rides on
  `metadata['controller']`, and `_sync_active` re-adopts the rebuilt
  player object after a load — so the roster survives save/load with no
  new save-format work. 6 tests (seeds the player as human, add an
  agent character, switch the active hero, reject a stranger, controller
  round-trip, survives a player rebuild). Suite 1391, green. REMAINDER
  (M.1b): render/move/save the NON-active roster characters as live
  world entities — this round is the abstraction only.)*
- [x] **M.1b Live roster characters in the world.** The non-active
  heroes now exist as real world entities.
  *(Round 148: `roster.add` places a non-active hero in the NPC pool
  (`npc_manager` — which the renderer draws from and save_load already
  serialises) and on the map, flagged `metadata['player_char']`;
  `set_active` SWAPS world presence — the new active leaves the pool
  (it becomes `engine.player`, rendered specially), the one you leave
  joins it as a live entity, preserving the invariant that the active
  player is never double-listed. `roster.rehydrate` (called at the end
  of `SaveManager.load`) rebuilds the roster from the reloaded pool's
  player-char flags, so a whole party survives save/load. The renderer
  draws every roster hero with the player body (not an NPC), and both
  NPC-turn loops SKIP player-characters so the ambient AI never drives
  them (their controller — human, or M.2's agent — does). 4 tests
  (add places in world, switch swaps presence, AI leaves them be, and
  a two-hero save/load round-trip that keeps the agent controller).
  Suite 1395, green.)*
- [x] **M.2 Agent-driven character (Claude joins).** An autonomous
  controller that plays a hero through the SAME player-action route a
  human uses.
  *(Round 149: `engine/agent_controller.py` — `AgentController` with a
  small utility POLICY (`decide`: fight an adjacent foe, close on a
  nearby threat within SIGHT, else wander toward a cached goal — LLM-
  free per tick, the DM's cached-plan discipline) that EXECUTES through
  the real engine actions (`engine.attack_character` / `move_player`),
  temporarily `acting_as` the character so the whole player API operates
  on it. `drive_agents(engine)` runs every agent roster hero once and is
  wired into the turn pipeline after companions; a re-entrancy guard on
  `advance_turn` (a `_advancing` flag) means a hero's move resolves but
  doesn't cascade a nested world tick. `PlayerController.driver` holds
  the brain. 6 tests (toward-vector, attacks-adjacent, hunts-in-sight,
  wanders-with-no-foe, take_turn wounds a foe through the real route,
  and drive_agents runs once-per-turn restoring the active player).
  Suite 1401, green. This is the piece that lets an agent JOIN and play
  a character; M.3 makes it take over an absent human's hero.)*
- [x] **M.2b Agent tactics & survival (from a played-it-myself test).**
  The naive charge-and-die policy is now a real one.
  *(Round 150: `AgentController.decide` is a priority utility policy —
  (1) SURVIVE: below 40% HP drink a healing potion (`_healing_item`,
  id-matched since the heal payload isn't on use_effect), else cast
  Heal if known + mana, else FLEE from the nearest foe; (2) don't stand
  and trade blows when SWARMED (≥2 adjacent + under 75% HP → back off);
  (3) FOCUS one target (`target_id` held until it dies/leaves) and SHOOT
  it if a ranged weapon is equipped and it's within range, else close;
  (4) a light OBJECTIVE — grab loot off the ground within 5 tiles;
  (5) wander. Still LLM-free. Executes through the real API (`use_item`
  / `cast_spell` / `shoot_ranged` / `pickup_item` / `attack_character`
  / `move_player`). SCORECARD — re-ran the playthrough: a ranged hero
  now KITES a 4-wolf pack for zero damage and levels up; a melee hero
  swarmed by four wolves FLEES and drinks a potion, surviving at 16 HP
  (was 1 HP, near-death). 5 new tests (heal/flee when hurt, back off
  swarmed, focus one target, shoot with a bow, grab loot). Suite 1406,
  green.)*
- [x] **M.3 Absent-player persistence.** When a human isn't at the
  controls, M.2's controller takes over their hero.
  *(Round 151: `PlayerController.away` + `roster.set_away/is_away/
  away_characters`, capturing an `away_home` (where to potter) when a
  human steps out. `drive_agents` now drives agent heroes AND any human
  hero flagged away — INCLUDING the active `engine.player` — through the
  M.2b policy, so an absent player's character keeps surviving, defending
  and heading home instead of freezing or going ghost; the controller's
  wander biases toward `away_home` (a light standing goal). The GUI
  freezes the world when idle, so `ui/away_mode.heartbeat` ticks it on a
  slow cadence while away (in the pipeline, so the away hero acts), and
  ANY keypress in play hands control straight back. A `,`-menu
  "Auto-play (away)" setting toggles it. 5 tests (away flag + home
  capture, the away hero is driven & defends, hand-back stops the agent,
  potters toward home, the heartbeat ticks only while away). Demo: a
  hero left AFK survived 20 world-ticks fighting off wolves at its home
  spot, then handed back on return. Suite 1411, green. The multiplayer/
  agent trio (M.1–M.3) is complete; M.4 is the networking layer.)*
- [x] **M.4a The authoritative session (the networking keystone).**
  Before any wire, the durable part of M.4 is the client<->world
  *contract*, and it now exists transport-free in `engine/netplay.py`:
  an **`Intent`** (the only thing a client may send — a whitelisted
  verb move/attack/say/wait naming the acting hero, round-tripping
  through JSON so the same object crosses a socket or a function call),
  and a **`GameServer`** that OWNS the engine. Clients never touch the
  engine: they `join` (a hero enters the roster + world, human or M.2
  agent), `submit` intents (validated, then applied through the SAME
  player-action route a human uses, acting AS that hero but with the
  world clock pinned so the action lands WITHOUT cascading a turn),
  read JSON `snapshot`s (every hero + nearby NPC body, no engine objects
  leaked), and `leave` (a disconnect hands the hero to an agent via the
  M.3 away path so it keeps living). The server alone drives the world
  via `tick`, so N players' actions resolve against one ordered
  timeline. 18 tests. *(This is to M.4 what M.1 was to the roster: once
  intents flow authoritatively and snapshots come back, the transport
  is a thin, separable layer — M.4b.)*
- [x] **M.4b The socket transport.** The replaceable wire over M.4a, in
  two layers. `engine/net_server.py` is transport-free: newline-JSON
  **framing** (`encode` + a `FrameDecoder` that survives split frames,
  packed frames, and garbage), a tiny **message protocol** (clients send
  JOIN / INTENT / LEAVE / POLL; the server answers WELCOME / RESULT /
  SNAPSHOT / ERROR), and **`NetServer`** — owns one `GameServer`, tracks
  connected clients, and is authoritative about IDENTITY: a client's
  intents are forced to act as the hero it JOINED as, so no client can
  puppet another's character; `tick_and_broadcast` advances the shared
  world and yields the frame every client receives. `engine/net_socket.py`
  is the real TCP pump over it: **`NetHost`** (a threaded
  `ThreadingTCPServer` + an optional background ticker that advances +
  broadcasts) and **`NetClient`** (connect / join / ship intents / read
  the latest snapshot). 17 tests — framing, dispatch (incl. the anti-
  spoof identity binding + disconnect→agent handoff), and a real
  end-to-end TCP round-trip (two clients sharing one world, a host
  broadcast reaching a client) that SKIPS where a sandbox forbids
  binding. The single-process game never imports the wire; it is opt-in.
  *(Remaining M.4c polish: a `--serve`/menu entry point, snapshot DELTAS
  instead of full snapshots, and reconnection — none blocking.)*
- [x] **M.5 The living away-hero (George, watching autoplay, 2026-07-12).**
  The autoplay/agent brain was a combatant — survive, fight, loot, wander —
  so a watched hero just moved a little and shot. Now it has a LIFE. Beyond
  combat, `engine/agent_controller.decide` chats with the folk it meets
  (`talk` → `dialog_system.player_to_npc`, once per soul), TAKES the quests
  they offer (`accept_quest` from `offered_by`) and pursues them (heads for
  a quest's target NPC or named location), RECRUITS willing allies
  (`recruit` when the party has room and regard is warm), and EXPLORES
  toward places its CALLING draws it — a warrior to lairs and keeps, a
  wizard to towers and standing stones, a bard to taverns — each a real
  named `Location`, marked visited so it moves on to the next. The player
  SETS the disposition first (a new `disposition` setting: balanced /
  valiant / cautious / sociable / explorer / greedy) and it biases the
  weighting — a cautious hero keeps its distance from a fight, a sociable
  one seeks people out, an explorer roams over its errands, a greedy one
  ranges wider for loot. And it leaves a TRAIL the player can review: its
  notable deeds go into the record as `[Away]` beats ("fell to talking with
  Brenna", "took up 'A Small Favour'", "recruited Ksana"), and its current
  aim rides `char.metadata["agent_goal"]`. Also fixed the dry-fire bug
  George caught (empty quiver → close to melee). 11 living-agent tests + 3
  ammo tests.
  **Freeze-proofing (2026-07-12b, watching live):** three distinct freezes
  hunted down and fixed — (1) a hero fleeing into a wall spun in place
  forever; `agent_nav.flee_step` now sidesteps to a walkable escape or,
  cornered, turns and fights; (2) inside a building it chased unreachable
  overworld goals; movement is now walkability-checked (`safe_step`) and it
  makes for the door and steps back out (`_zone_plan`/`exit_building`);
  (3) it "shot" a phantom foe seen at its overworld coordinates through an
  interior wall; `_colocated` now gates perception to the hero's own grid.
  New `engine/agent_nav.py` holds the movement-safety layer (keeps
  agent_controller under 500). +5 tests.
  **Loop-proofing (2026-07-12b, part 2):** the live watch surfaced four
  more loops, all fixed — a LOOT loop (a plain-string body marker counted
  as loot, and a full pack pumping pickup forever → `_nearest_loot` skips
  both), a DOORWAY shuffle (a building explore-goal auto-entered then
  exited then re-entered → the agent now skirts overworld buildings and
  marks a left building visited), a DEATH loop (planted in a lair's kill
  zone → new rule 2b retreats from a closing 3+ pack; 0 deaths across
  200-turn drives), and OSCILLATION (flee ping-pong + a sociable hero
  re-approaching greeted friends → a `recent` anti-backtrack trail and a
  leave-greeted-friends-be rule). Stateless helpers split to
  `engine/agent_sense.py`. Party capability CONFIRMED: the hero recruits a
  willing ally and adventures with it (the ally trails and fights) — but no
  demo NPC starts trusted enough (all rel 0) and a chat doesn't raise
  trust, so a party doesn't form in a short session (M.5b: earn trust via
  quests/bonds). +9 tests. Also `body_renderer.draw_glimpsed` draws an
  indoor NPC seen through a window behind glass (not on the wall).
  Remainder M.5b: a "while you were away" digest screen, finer
  per-disposition tuning, EARNING an ally's trust so a party actually
  forms, and the agent using the wider systems (bank, craft, pray, home).
- [x] **M.6 Adventurer NPCs — the world's other heroes (George, 2026-07-12).**
  "Apply the autoplay lessons to adventurer NPCs" + "make the party form."
  A new `engine/adventurers.py` (`AdventurerSystem` over
  `data/adventurers.json`) seeds a small band of adventuring-class NPCs
  (Kestrel the ranger, Bram the axeman, Sable the wizard) at the taverns,
  SEEKING a company — so `companions.can_recruit` now lets the player (or a
  driven away-hero) recruit a `seeking_party` adventurer before deep trust:
  **the party forms.** They ride the very same `AgentController` brain the
  away-hero uses — with all its freeze/loop fixes — but `social=False`, so
  they fight, loot and roam WITHOUT ever touching the player's quest log or
  party. Combat XP flows to whoever acts, so an adventurer grows in level by
  fighting; a seeking one loiters by its tavern, an un-recruited one strikes
  out. Driven each turn (capped at `MAX_DRIVEN`), skipped by the ambient NPC
  AI, and they ride the save. +9 tests. **Remainder M.6b (the big one):**
  adventurers taking their OWN quests and clearing dungeons, forming RIVAL
  parties, actively COMPETING with the hero for quests/loot/hoards, and the
  full fortune arc — growing powerful, or dying and losing everything.
- [x] **M.7 Hirelings & guilds (George, 2026-07-12).** Two linked ideas
  layered on M.6's adventurers.
  **(1) HIRELINGS — DONE (2026-07-12c).** Party members you PAY rather than
  befriend: `engine/hirelings.py` (`HirelingSystem`). `/hire` takes an
  upfront signing fee (level-scaled) and adds an adventuring-class NPC to
  the party on a contract (`npc.metadata["hire"]`: wage / term_end /
  paid_through); `/hire N` sets an N-day term, bare `/hire` an open salary.
  `run_day` settles wages nightly from the turn pipeline — pay the day's
  wage, end an expired term amiably, or (purse empty past one day's grace)
  let the hireling walk SOURED. Stateless; the contract rides the NPC save.
  Any M.6 adventurer can thus be befriended into a free companion OR simply
  hired. 8 tests.
  **(2) GUILDS as PLACES — DONE (2026-07-12d).** `engine/guildhalls.py`
  (`GuildHallSystem`) plants a named `Location` marker — the Adventurers'
  Guild by Oakvale, the Mercenaries' Rest by Riverside — beside a settlement
  at world start (from `data/guildhalls.json`), and the M.6 adventurers now
  gather at their home settlement's hall (`AdventurerSystem._gathering_spot`)
  instead of just any tavern. `roster(hall)` lists the blades on offer,
  `hall_at(pos)` names the hall you're standing at; the markers ride the
  world save + a small persisted index. So you know where to go to recruit a
  companion or hire a blade. 7 tests. Remainder M.7c: board-quests and
  TRAINING at the halls, an enterable interior, and a mages' college.

## Phase 27 — Autoplay-driven improvement backlog (ultraplan, 2026-07-12d)

Findings from a 500-turn autoplay observation session (balanced hero): the
agent genuinely PLAYS — it fought, fled, looted, took & completed quests,
recruited a party (two adventurers), and levelled 1→3. But the verb mix was
`flee 606 / loot 582 / attack 252 / move 1687` with only `talk 10 /
accept_quest 11`, the hero sat chronically wounded (12/37 HP), and it NEVER
cast a spell, crafted, gathered/foraged/mined/fished, cooked, rested at an
inn/camp, banked, prayed, shopped, trained a skill, or hired a blade. Whole
subsystems the game already has go untouched — by the agent AND, by
implication, by a casual human. This backlog turns that into rounds. Each is
a coherent, testable slice; ordered roughly by impact.

### M.8 — The away-hero uses the WHOLE game (deepen autoplay)
- [x] **M.8a Rest & recovery loop (2026-07-12d).** A SAFE, wounded hero now
  recovers (`agent_controller.decide` step 3b, `REST_HP` 0.55) instead of
  soldiering on at a sliver: a potion, a Heal spell, or — badly hurt on the
  open overworld and out of quick heals — making CAMP. Crucially the camp is
  gated on `agent_sense._provisioned` (a real camp needs food worth
  `SUPPLY_NEED`): without it, camping is a fruitless doze the hero would
  repeat every night — the first cut of this LOOPED 223 times. With the gate,
  a 400-turn autoplay session went from mean 0.40 HP / 289-turns-wounded (the
  rest-loop) to **mean 0.72 HP / 112-turns-wounded, zero rest-loops**, and
  fleeing nearly halved. Adventurer NPCs (`social=False`) never rest (they'd
  advance the world clock). 5 tests; the goal/disposition helpers split to
  `engine/agent_goals.py` to hold the line. Update (M.8d done): the camp path
  is fed by foraging BREAD (`use_effect.food`, heal 4) from forests — two
  loaves provision a real camp — so a forager can now mend in the wilds.
  Remainder: inn-rest wants the hero to seek an inn (M.8b navigation); fully
  ending attrition also needs P27.1 (combat density).
- [x] **M.8b Economy loop (2026-07-12d).** The hero SPENDS instead of
  hoarding: standing by a merchant (its social rounds already walk it up to
  folk) it strikes a deal — `engine/agent_trade.py` (`wants_to_trade` /
  `do_trade`) sells all its JUNK loot for coin and buys the essentials it's
  short of: a healing potion when it carries none (which FEEDS the M.8a
  recovery loop) and ammunition when it packs a bow it can't fire. Runs
  through new `ShopManager.buy_for`/`sell_for` (a programmatic mirror of the
  shop-panel transaction over the real catalogue — one buy path). A 400-turn
  autoplay session: 6 trades, and the hero ends CARRYING A POTION (loot →
  gold → readiness). 4 tests. Remainder: buying BETTER GEAR (compare &
  upgrade), banking a surplus, and reaching INDOOR shop merchants (the hero
  skirts buildings, so it trades the ones it meets on the street/at stalls);
  hiring a blade is already covered by M.6 free recruiting.
- [x] **M.8c Magic in the field (2026-07-12d).** A caster away-hero now
  FIGHTS with magic: `agent_sense._attack_spell` picks the most mana-EFFICIENT
  reachable damage spell it knows and can pay for (damage-per-mana, a bigger
  nuke breaking ties), and `decide`'s engage step casts it (the `cast` verb →
  `engine.cast_spell`) before blade or bow — falling back to melee/bow when
  the mana runs dry (the cheaper spells carry it further; the M.8a rest
  restores mana). Adventurer casters (Sable the wizard) fight this way too. A
  300-turn wizard session: 471 casts (468 magic_missile), NO melee, NO flee,
  ending at FULL HP level 3 — it kills wolves at range before they close, so
  it takes no damage. 4 tests. Remainder: UTILITY spells on the road
  (light/farsight/water-walk, self-buffs before a fight) and resting
  specifically to recover mana; ties into P26.2's magic overhaul.
- [x] **M.8d Gather & craft (2026-07-12e).** The hero GATHERS from the land
  (`agent_sense._gatherable` + the `forage` verb → `engine.forage`): standing
  on a workable mine/wood/fish node or a rich FOREST/SWAMP tile (and with room
  to carry) it stops to gather — herbs, ore, and from a forest BREAD, which
  is real food (`use_effect.food`, heal 4). That closes the loop with M.8a:
  two loaves provision a real camp, so the forager can now mend in the wilds.
  Plain grass is skipped (everywhere, barely worth it). 4 tests. Remainder
  (CRAFT): crafting potions/gear/ammo needs a workstation (a forge/alchemy
  table), which is INDOORS — and the away-hero skirts buildings — so active
  crafting waits on a "duck into a workshop" navigation step (with M.8b's
  indoor-merchant reach).
- [x] **M.8e Worship, consumables & buffs (2026-07-12e).** Two safe,
  always-worthwhile wins in `decide` (step 3d): the hero STUDIES a teaching
  tome / training manual it carries (`agent_sense._learn_item` → the `study`
  verb → `use_item`) — a `teach_spell` it doesn't know or a `permanent_stat`,
  a forever-benefit that used to rot in the pack — and PRAYS at a shrine/temple
  (`_can_pray` → the `pray` verb → `engine.pray`) for a god's boon, once a day,
  away-hero only (an adventurer's favour is meaningless). 6 tests; the take-turn
  action dispatch split to `engine/agent_exec.py` to hold the line. Remainder:
  TIMING-sensitive consumables — a buff/attack scroll or eating for the
  well-fed bonus is only worth it at the right moment (before/in a fight,
  when hungry with food to spare beyond the M.8a camp ration), so those wait
  on a little more context-awareness.
- [x] **M.8f Homesteading (2026-07-12e).** A base of operations for a
  long-lived hero (`decide` step 3e). STASH: a full-packed hero that keeps a
  furnished home shelves its SURPLUS (loot/materials — not gear/potions/food/
  ammo/tomes) in the chest (`agent_sense._can_stash`/`_surplus_items` → the
  `stash` verb → `homestead.deposit`, which reaches the chest from anywhere),
  freeing the pack to keep gathering and looting — a real answer to the
  recurring pack-full stall. CLAIM: standing at an affordable derelict
  dwelling it buys in (`_claim_target` → the `claim_home` verb). Rest-at-home
  is already M.8a's `sleep` (`can_rest_home`, free Well-Rested). 7 tests.
  Remainder — and the KEY cross-cutting gap for the whole indoor-M.8 cluster:
  a "seek and enter a specific building" navigation (the away-hero skirts
  buildings, so it rarely REACHES a derelict to claim, an inn to rest at, an
  indoor shop to trade at, or a forge to craft at). That one navigation step
  would light up M.8a inn-rest, M.8b indoor-merchants, M.8d crafting, and
  M.8f claim/repair together. Plus the staged home REPAIR project (needs the
  hero inside its home with timber/stone).
  *That completes the M.8 arc (a–f): the away-hero rests, spends, casts,
  gathers, worships and homesteads — it uses the whole game.*

### M.9 — Watchability: autoplay as a spectator feature
- [x] **M.9a "While you were away" digest (2026-07-12e).** When the human
  takes the reins back from the autoplay agent, a "While You Were Away" screen
  greets them with what the hero got up to — `engine/away_digest.py`:
  `set_away(True)` stamps a snapshot (turn/day/level/gold/party + a memory
  index), and `build_digest` reads it back to tally the DELTAS (days away,
  levels gained, purse change, new companions) and list the `[Away]` deed
  beats logged since, as a `(title, lines)` overlay — consuming the snapshot
  so it shows ONCE. The GUI's hand-back pops it as a menu overlay (and
  `continue`s so the very key that handed control back doesn't dismiss it).
  6 tests. Remainder: richer content (quests completed, deaths, weighty
  `[Legend]`/`[Realm]` beats), and a key to RE-VIEW the last digest.
- [x] **M.9b Autoplay speed & step (2026-07-12e).** The watcher now paces the
  autoplay: `ui/away_mode.py` `SPEEDS` (paused / slow / normal / fast / blitz —
  frames between auto-ticks), driven by `cycle_speed`, `single_step` and
  `handle_speed_key`. While away, `[-]`/`[+]` slow down / speed up (slowing
  past 'slow' PAUSES), and `[.]` single-steps one world tick — perfect for
  watching an action beat by beat, even while paused. The GUI loop intercepts
  these before the hand-back (so they neither end autoplay nor reach the play
  handler; they're also in `_OBSERVE_KEYS`), and the AUTOPLAY banner shows the
  current speed + the `[-/+] [.]` controls. `heartbeat` reads the chosen
  interval (None = paused). 6 tests. Remainder: persist the chosen speed as a
  setting.
- [x] **M.9c Spectator HUD (2026-07-12e).** While the hero is agent-driven, a
  small "what it's up to" card sits under the AUTOPLAY banner
  (`ui/away_mode.spectator_lines` → `hud.draw_spectator_panel`): its AIM (the
  live `agent_goal`), BEARING (disposition), STANDING (level · HP · gold) and
  BAND (party members, or "alone"). So watching reads as a story — you can see
  where the hero is headed and how it's faring — not a mystery. 4 tests.
  Remainder: richer renown (fame/reputation beyond level) and the exact
  current action verb.
- [x] **M.9d High-level goals & disposition presets.** Let the player set an
  AMBITION for the absence ("get rich", "clear the Dark Hollow", "become a
  master mage", "found a company") that biases the agent, beyond the six
  dispositions. *Done:* a fifth `ambition` setting (none/wealth/delve/
  mastery/fellowship) on top of the six dispositions. `agent_goals.AMBITION_DRAW`
  redraws where the away hero roams — wealth→markets/towns, delve→caves/ruins/
  lairs, mastery→towers/shrines, fellowship→taverns/guilds — OVERRIDING the class
  calling; wealth also widens the loot reach (greedy's r=8) and fellowship the
  social reach (sociable's r=8). Shown on the M.9c spectator card
  ("Ambition: delve"). `tests/test_away_ambition.py` (13).

## M.10 — Needs-aware autonomy & party welfare (George, 2026-07-12)

George, watching autoplay: "make sure the controlled players monitor their
needs and satisfy them sensibly (thirsty → find water, hungry → eat, injured
→ heal, tired → rest); don't die from thirst without trying. Do party members
suffer injuries in combat, and do they satisfy needs? They should work together
to keep everyone alive — or a member may have to LEAVE to survive." The driven
hero accrues `thirst`/`hunger`/`fatigue` (`characters/needs.py`) but the agent
today reacts only to HP — a real gap.

- [x] **M.10a Driven-hero needs self-care.** In `AgentController.decide`, a
  SAFE hero tends its body BEFORE it's dire: DRINK when thirsty (a carried
  drink item, or step to an adjacent WATER tile and drink from the river), EAT
  when hungry (a carried food), and REST when merely tired (not only when badly
  wounded). Sensing in `agent_sense`, execution in `agent_exec` (reusing
  `use_item`/`needs.drink`). So a driven hero never dies of thirst/hunger untried.
  *Done:* `agent_sense._thirsty/_hungry/_tired/_drink_item/_food_item/
  _adjacent_water/_water_toward` (thresholds 55/60/65, below the exhaustion
  rungs); decide's recovery block now handles thirst→hunger→HP→fatigue in that
  order (thirst is the fastest clock); `agent_exec` `drink`/`eat` verbs.
  `tests/test_away_needs.py` (12).
- [x] **M.10b Companion combat survival.** Confirm companions take combat
  damage (they do — HP drops, `_flee_step` reacts < 30%) and give a wounded
  companion self-preservation: quaff its OWN healing potion when hurt, and flee
  when critical even without the /order flee. A party member fights on too long
  and dies today. *Done:* `CompanionManager._self_heal` (below `SELF_HEAL_HP`
  = ½, quaff a carried potion — consumed, a beat) runs at the top of `update`,
  and the flee gate now fires for ANY order (survival before orders), so a
  companion still critical after healing BREAKS OFF even on follow/hold.
  Verified injuries flow through `_resolve`→`take_damage`.
  `tests/test_party_survival.py` (7).
- [ ] **M.10c Party welfare & cooperation (+ personality-driven aid).**
  Companions satisfy their own needs on the road (eat/drink), a HEALER companion
  mends the most-wounded ally, and a member at death's door with no way to
  recover LEAVES the party to save itself (a beat), rejoining when well. The
  party keeps everyone alive together. **But not uniformly** (George, 2026-07-12):
  a character's ALIGNMENT, its RELATIONSHIP/alliance/enmity toward the hero and
  each other, its PERSONALITY, and its MEMORIES drive how freely it gives aid —
  a selfish or hostile-leaning member is slower to spend its potion on someone
  it dislikes, a loyal or good-aligned one readily helps; the same forces shape
  behaviour OUT of a party too. Aid-willingness = f(regard, alignment, traits,
  recent memories), a gate on the heal/share decision.

### M.6b / M.7b — the living-world remainders (already scoped above)
- [~] **M.6b Rival adventuring parties.** Adventurers take their own quests,
  clear dungeons, band into rival companies, and COMPETE with the hero for
  quests/loot/hoards — a renown race — with a real fortune arc (grow strong,
  or die and lose it all). *Sub-step done (companies FORM):* `engine/companies.py`
  bands the seeking, un-recruited adventurers who share a home settlement into
  a COMPANY led by the strongest (`form`), gives it a stable name + a `[Realm]`
  forming beat, and has the followers TRAVEL with their leader (run_turn homes a
  follower's brain on the leader). `renown` = Σ member levels × 10 (the race's
  score); `dissolve` disbands a company whose leader falls or is recruited. All
  state on `metadata` (rides the save). `tests/test_companies.py` (14).
  *Remainder:* companies take their own QUESTS + clear dungeons, COMPETE for
  named hoards, renown grows on real wins (kill/quest ledger, not just levels),
  and the full fortune arc (a wiped company loses its renown for good).
- [ ] **M.7b Guild halls as places.** (see M.7 above) — where blades, quests
  and training reliably congregate.

### World balance & pacing (from the flee-heavy data)
- [ ] **P27.1 Encounter-density & danger tiers.** The overworld is too thick
  with lairs/nests (flee was 36% of turns). Scale danger by region/distance,
  keep roads & near-town safer, give the early game breathing room.
- [ ] **P27.2 Wound/recovery balance.** Chronic low HP shouldn't be the
  default state; make recovery accessible without trivialising wounds
  (pairs with M.8a).

*(Existing planned items that autoplay reconfirms as high-value: P21.6
Treasure & legend, P22.6 non-blocking spellcasting, P22.7 readable buildings,
P26.1 advancement rebalance, P26.2 magic overhaul.)*

## Phase 28 — Transport & travel (ultraplan, George, 2026-07-12e)

The teleport-trap fix (`travel._safe_landing`) opened onto a bigger idea:
travel as a real, item-gated, place-based network — and mounts of every
kind. Builds on `engine/travel.py` (teleports) and `engine/mount.py` (the
P15.8b pack mule).

### P28.1 — Teleport platforms as PLACES (a public magical transit network)
- [ ] **P28.1a Platforms & rings.** A teleport PLATFORM (a rune circle /
  waystone) is a physical `Location` seeded in each city/town/village —
  where folk safely teleport to and from. Using the network needs a
  teleport ITEM (a ring / bracelet / amulet), COMMON and provided by a
  powerful magical guild (the Wayfarers' / Arcane Conclave); **the player
  starts with one**. To travel you stand ON a platform, pick a destination
  platform (that you have an item for), and go — recasting the U-key teleport
  as place-to-place instead of anywhere-to-a-town-centre. Data:
  `data/teleport_network.json` (platforms + which settlements have them);
  the ring is a normal `data/items` entry with a `teleport_access` flag.
- [ ] **P28.1b Arrival collision → safe space.** If a platform is occupied
  (several arriving at once, or an NPC standing on it), the arrival is
  diverted to a CLOSE, SAFE tile beside it — reuse `_safe_landing`, extended
  to also avoid occupied tiles and fan out. So two travellers never stack.
- [ ] **P28.1c The network grows.** Later, platforms gate access to NEW
  REGIONS: an unlocked (quest / guild-rank / paid) far platform is how you
  reach a new area — the network as progression, run by the guild. Ties into
  P21.5 landmarks / chunked_world regions.

### P28.2 — Mounts of every kind (basically anything rideable)
- [ ] **P28.2a Data-driven mounts.** Generalise `engine/mount.py` (today just
  the pack mule) to a `data/mounts.json` roster: HORSE (fast road pace),
  MULE / PACK DONKEY (carry), ELEPHANT (big carry, slow, tramples),
  WAR-HORSE (a combat mount), MAGIC CARPET (flies)… each with speed, carry
  bonus, cost, where it's sold (stable / market / bazaar), and a trail-behind
  follower. "Basically anything can serve as a mount" — the data decides.
- [ ] **P28.2b Terrain abilities.** A mount's `traverses` list lets it cross
  what a walker can't — a magic carpet / griffon FLIES over water & mountains
  (compose with `world_map._is_flier`), a horse fords shallows, a camel
  shrugs off desert. Mounted travel reads the mount's abilities in
  `traversal`/`hazards`.
- [ ] **P28.2c Mount lifecycle & care.** Buy/stable/release at a stable;
  ride/dismount (a key); the mount can be spooked, tire, or (war-mounts) fight;
  loyalty/feed like the P12.14 pet. See `autonomous_world` for the breadth of
  rideable creatures.

## Phase 29 — The Productive World: NPC construction, terraforming & the material economy (ultraplan, George, 2026-07-12)

George: "NPCs and characters should be able to DESTROY and BUILD objects,
including buildings — given the right resources, tools and skills — as part of
their economy: harvesting, mining, crafting, selling, building, renovating.
NPCs hireable to build and TRANSFORM tiles (fell trees → timber, mine → metals,
quarry → stone); goods TRANSPORTABLE (pack animals, porters, magical transport);
magic-users conjure resources / terraform / raise buildings. It all feeds the
economy and drives NPC (and monster) action. See Autonomous World; research
efficient approaches."

**Grounding — a lot already exists to build on (mapped 2026-07-12):**
`engine/production_loop.py` (nightly settlement STORES; gatherers add raws,
crafters consume `inputs_of`→goods; `_arbitrage` caravans) but it works
ABSTRACTLY — never touches tiles/nodes. `world/resource_nodes.py`
(`harvest`→`_deplete` TRANSFORMS the tile; `run_day` regrows) but is called
only from the PLAYER gather path. `engine/tile_damage.py` (tile HP + materials;
BUILDING→RUBBLE, FOREST→GRASS, MOUNTAIN→GRASS via `damage_tile`/`damage_radius`)
— destruction is real. `engine/giants.py` `run_night_labor` (crews clear rubble,
masons rebuild breached walls) — the only NPC-construction template, hardcoded.
`engine/homestead.py` (a staged `ConstructionProject`-in-spirit: timber+stone+
coin+time→furnished building) but PLAYER-only, `player.metadata`-backed.
`engine/mount.py` (pack mule +carry), `engine/spells.py:171` (razes via
`damage_radius` — no symmetric CREATE path). `world/building_types.py`
(KIND→profession, `classify_interior`). Each sub-step below is one tested round.

- [ ] **P29.1 NPC terrain-harvesting (raws come from real tiles).** New node
  KINDS in `data/resource_nodes.json` — an ORE vein (mountain → depleted rock)
  and a STONE quarry — beside the shipped grove (forest → grass). Let an NPC
  PRODUCER working near a live node harvest it (generalise
  `ResourceNodeSystem.harvest` past the player-only path), transforming the
  tile; `production._work` gatherers pull from a real nearby node when present
  (abstract yield only as fallback), so store raws came from somewhere on the
  map. Extend `items/validate_economy.py` for the new kinds.
- [ ] **P29.2 A general `ConstructionProject` (NPCs build & renovate).** Extract
  the staged-construction pattern into a reusable `engine/construction.py`
  `ConstructionProject` (site + kind + staged inputs timber/stone/coin/labour +
  progress + on-finish effect), usable by NPCs, not just the player. An NPC crew
  with the materials + carpentry/masonry skill advances a project each day
  (generalising the `giants` mason loop); on finish it stamps a real BUILDING
  footprint or renovates a derelict. Its own persisted subsystem.
- [ ] **P29.3 The build economy drives NPC action.** A settlement with surplus
  raws + a need (a ruined/derelict/RUBBLE'd building, or growth) COMMISSIONS a
  project; producers route gather→haul→build, consuming materials from the
  store. Destruction feeds it (a burned building becomes a renovation job).
  Ties production stores ↔ building_types ↔ construction.
- [ ] **P29.4 Physical transport of goods (haulers).** Goods move as real loads,
  not abstract integers: a PORTER / pack-animal / caravan NPC carries a load
  from source (node/settlement) to workshop/market via `carry`/`mount`
  (generalise `mount.py` to NPC pack animals). Augments `_arbitrage` with a
  VISIBLE carrier when the player is near.
- [ ] **P29.5 Magic shortcuts (conjure & terraform).** Symmetric to the raze
  path: CREATION/TERRAFORM spells — conjure raw stone/wood into a store or pack,
  transform a tile (raise stone, grow forest, part water), or raise a simple
  structure — mana/level-gated, data-driven. A mage-for-hire shortcuts a
  construction project; conjured goods enter the same economy.
- [ ] **P29.6 Hire NPCs to build & harvest.** Extend `hirelings.py`: hire a
  labourer/mason/miner/mage to execute a specific JOB — fell a wood, quarry
  stone, build a structure, terraform a tile — for pay, on the player's behalf
  (e.g. to expand a homestead). The specialist runs a ConstructionProject or a
  harvest loop.
- [ ] **P29.7 Monsters & the economy react.** Monsters/tribes (P19.4) raid the
  material economy — burn buildings (making renovation jobs), plunder stores,
  occupy nodes (denying them) — and prosperity/scarcity (`market.py`, faction
  stores) drives encounter weight + NPC/monster behaviour. Closes the loop:
  production ↔ destruction ↔ prices ↔ action.

## What NOT to build (explicitly deferred)

- Continuous LLM agent simulation (Generative Agents-style) — cost-prohibitive; the
  director + salient-interaction pattern captures 80% of the value.
- 3D mode and a web UI — ROADMAP long-term, irrelevant to the
  quality/richness goals. (Networked multiplayer moved to Phase M.)
- LLM-generated main plot (AI Dungeon's trap) and voice I/O.
- Punishing survival mechanics for the player (needs stay light).

## Phase 18 — The Royal Castle (George, 2026-07-11) — MAJOR

George: "Introduce a huge castle with detailed buildings, courtyards,
ramparts, defenses and a royal family, staff, courtiers, soldiers.
Multiple levels, towers, battlements and an extensive dungeon... an
entire adventure to explore the castle and interact with all of its
inhabitants. A menu option to start the game in the castle. A populated
town nearby, surrounded by villages that have farms and other resources
to supply the castle."

**Research basis** (real castle architecture + game precedents). A
medieval castle is CONCENTRIC and layered: an outer CURTAIN WALL studded
with mural TOWERS and pierced by a GATEHOUSE (portcullis + murder-holes)
→ an OUTER BAILEY (stables, barracks, chapel, well, smithy — the working
yard) → an INNER WARD → the KEEP / donjon (the great hall on the ground,
royal solar and bedchambers above, storerooms and the dungeon/oubliette
below) → the BATTLEMENTS & wall-walk with crenellations and arrow-loops.
A LIVING castle (the Autonomous World lesson, cf. Skyrim's Whiterun /
Dragon Age's Denerim / CK-style courts) layers a social order on that
stone: a royal family with a line of succession, a steward/chamberlain
and household staff, courtiers and their intrigues, a garrison under a
captain, and a supply chain — the castle EATS, so a town clusters at its
gate and villages farm its hinterland. Our engine already has the pieces:
the P9.1 multi-level `structures.json` stack (keep + dungeon), NPC
presets + schedules (the cast), the P16 production/supply chain (farms →
stores → the castle larder), and the Phase-17 battle layer (siege
defense). This phase assembles them into one place.

Sequenced into tested rounds:

- [x] **P18.1 The castle keep & crypt (the stone).** A 5-level
  `bloodstone_castle` structure in `data/structures.json`: the Great
  Hall & Bloodstone Throne (entry), the Servants' Undercroft (kitchens/
  larders), the Barracks & Armoury, the Dungeons (cells, dark, guarded),
  and the Royal Crypt (dark, undead-warded, the legendary Crown of
  Bloodstone as its prize). Two signature treasures added
  (`crown_of_bloodstone` amulet, `royal_seal`). *(Round: the linear
  P9.1 stack fits a vertical keep→dungeon descent; battlements/towers
  (the UP direction) are P18.3. 6 tests: data shape, rectangular walled
  grids, build/link the 5-level chain, throne inscription + loot, the
  dark guarded crypt, the crown in the deepest chest. Validator clean;
  suite 1771, green.)*
- [x] **P18.2 The living cast.** The royal family (king/queen/heir/
  rivals), the steward + household staff (cook, maids, stablehands),
  courtiers, and the garrison (captain + guards) as `data/npcs/*` presets
  placed into the castle zones as friendly INDOOR occupants (extend the
  structure populator to seat NPCs, not just monsters), each with a
  schedule and a place. Court relationships + a few secrets/topics.
  *(Round: `data/npcs/bloodstone_castle.json` — 13 residents (King Aldric
  III, Queen Maera, Prince Cedric, the ambitious Duke Voss, steward,
  cook, maid, stablehand, court bard, chaplain, Captain Ser Brannock + 2
  guards), each `zone_bound` so `all_presets()` keeps them OUT of the
  open-world roster. The structure spec gains an `occupants` list per
  level; `StructureBuilder._seat_occupants` (called from `on_enter_level`)
  seats them via `make_npc` as friendly zone natives at their posts
  (royals in the Great Hall, staff in the Undercroft, garrison in the
  Barracks) — the same entities the dialog/memory systems already know,
  talkable through the presence layer. Court intrigue is seeded in the
  relationships (Duke Voss vs the heir). Validator gained an occupants
  check. 7 tests (cast authored + zone-bound, intrigue seeded, residents
  absent from the world, the hall seats the court, the King is talkable,
  no dup on re-entry, the crypt still holds its dead). Suite 1781, green.
  Schedules within the zone are a later refinement.)*
- [x] **P18.3 Battlements, towers & the gatehouse footprint.** The
  upward extension (royal apartments → wall-walk → tower tops with
  archer positions) as levels ABOVE the great hall, plus the overworld
  footprint — a curtain-wall + gatehouse building block the worldgen
  places so the castle reads as a fortress from the map.
  *(Round — the upward extension is done: the P9.1 structure stack was
  LINEAR (each level linked to one list-neighbour), so the ground could
  go up OR down, never both. Added elevation linking — a `floor` int per
  level; `StructureBuilder._link` links adjacent floors (so a mid-stack
  ground can carry storeys above AND a cellar below) and `_ground_index`
  makes the `floor: 0` level the entry (backward-compatible: no `floor`
  → the legacy linear chain + `levels[0]`). The castle grew to SEVEN
  floors: Battlements (+2, the crenellated wall-walk with archer posts
  and the seven-sieges motto) → Royal Apartments (+1, solar, bedchambers,
  courtiers' quarters, library) → Great Hall (0, entry — gained an
  up-stair) → Undercroft (−1) → Barracks (−2) → Dungeons (−3) → Crypt
  (−4). From the hall you now climb the keep to the battlements or
  descend to the crypt. `_sweep_footprint_loot` picks the deepest by
  floor. 4 tests (seven floors, floor range, hall branches up-2/down-4,
  the battlements are the roofless top). Suite 1783, green. Remainder
  P18.3b: the OVERWORLD footprint (curtain-wall + gatehouse block) is
  deferred to the placement rounds (P18.4/P18.5) — a fortress blueprint
  is dead code until the castle is actually planted in a world.)*
- [x] **P18.4 The castle town & supply villages.** A populated town at
  the gate (market, inn, temple, craftsmen) and a ring of farming
  villages whose P16 production feeds the castle larder — a real
  supply chain the player can see and disrupt.
  *(Round: `world/castle_region.py` — `build_castle_region(world)` plants
  the whole Bloodstone realm on a map. The FORTRESS: a curtain-walled
  keep with a single gatehouse in the south wall and a grass bailey,
  under the "Bloodstone Castle" location the P18.1-3 seven-floor
  structure attaches to — so this ALSO satisfies P18.3b (the overworld
  footprint; the castle now reads as a fortress from the map). At the
  gate, Kingsgate Town (The King's Rest Inn, Kingsgate Market, Temple of
  the Crown, the Royal Smithy — tavern/shop/temple/forge tagged). A ring
  of three farming villages (Wheatfield/Millbrook/Greenhollow), each a
  farmhouse beside a patch of FARMLAND the P8.3 farms + P16 loop bring to
  life. Roads stitch every village to the town to the gate — the supply
  routes. The town and villages register as P16 production settlements,
  so grain flows toward the crown by the existing loop. 7 tests (whole
  realm planted, the walled fortress with one gate, farmland, roads, the
  town's trades, the 7-floor structure attaches to the footprint, and
  the settlements are recognised by the production loop). Suite 1790,
  green. Planting this into a LIVE world (and dropping the player at the
  gate) is P18.5 — this is the reusable region the menu-start will call.)*
- [x] **P18.5 "Begin at the Castle" — the menu start.** A start-menu
  option that generates a castle-centered world (castle + town +
  villages) and drops the newly-made character at the gate.
  *(Round: a `world_kind` flows New Game → `main.py` → `GameEngine` →
  `initialize_demo_game`/`initialize_demo_world`. `world_kind="castle"`
  plants the P18.4 Bloodstone realm instead of the default world and
  spawns the player on the road just outside the gatehouse
  (`castle_region.gate_approach`); `start_game`'s `structures.build()`
  then attaches the seven-floor keep automatically. The start menu gains
  a "Begin at the Castle" new-game option that routes through the SAME
  character creator as Customize (you still make your hero) carrying a
  `pending_start="castle"` flag out with the finished spec. The default
  Oakvale start is untouched. 6 tests (the realm is the castle region,
  the hero stands at the gate on open ground, the keep is attached, the
  default start is still Oakvale, the option is on the menu, and choosing
  it routes through creation with the flag then resets). Suite 1796,
  green. The castle is now playable end-to-end from the title screen.)*
- [x] **P18.6 The castle adventure.** Quests and court intrigue (a
  succession plot, a spy in the household, the thing stirring in the
  crypt), and a siege set-piece that hands the P17 battle layer the
  castle's own garrison and walls.
  *(Round — the intrigue quest chain is done (all content-as-data, given
  by the P18.2 cast): 1) "An Audience with the King" (Captain Brannock
  presents you → talk the King); 2) "Whispers in the Hall" (Queen Maera →
  sound out the maid and the bard who see & hear all); 3) "The Spy in the
  Household" (Maid Rowena → recover Duke Voss's cipher, planted in the
  Royal Apartments chest, and deliver it to the Queen); 4) "The Duke's
  Gambit" (Prince Cedric → expose the plot to the King and face the Duke);
  5) "What Stirs Below" (Chaplain Aldith → lay the crypt's restless dead).
  Chained by `prereq_quest`; a new `dukes_cipher` evidence item. Two
  playtest guards taught to accept zone-bound (in-zone) quest givers &
  targets, not just open-world ones. 8 tests (chain authored, givers are
  the castle cast, the intrigue targets the rival/crown/dead, the cipher
  waits in the apartments, the audience gates the rest, turn-in unlocks
  the next, a TALK completes on the King, the crypt counts three dead).
  Suite 1804, green. Remainder P18.6b: the SIEGE set-piece — hand the P17
  battle layer the castle's own garrison (the P18.2 guard) and its walls
  for a defend-the-keep battle.)*

---

## The Ultraplan — playtest & survey findings (George, 2026-07-12)

A long driven playtest (grind to L20, recruit, fight the hardest monster,
probe coop) plus four parallel code surveys (monsters/combat, NPC depth &
group goals, adventures/puzzles/exploration, graphics/living-world) plus
cross-game research (Shadow of Mordor's Nemesis, Dwarf Fortress emergent
history/ecology, RimWorld's storyteller, Crusader Kings intrigue/ambitions,
Caves of Qud/DF active gods, Baldur's Gate branching, Kenshi living
factions). The verdict: the engineering is broad and clean, but the game
is **shallow where it should thrill**. Hard findings:

- **No dragons / apex tier.** Hardest monster is the L8 Giant Warlord.
  Worse: the built bosses (warlord, wisp queen, hill giant) have
  `encounter_weight: 0` — **fully-mechanical dead content, reachable only
  in tests.** A L20 party has nothing worthy to fight.
- **Monsters barely cooperate.** Only wolves howl (same-name convergence).
  The sophisticated Phase-17 `battle_ai` (focus-fire, flanking arcs,
  morale, rout cascade, hammer-and-anvil) is **walled off** from the
  overworld — the single highest-leverage asset in the codebase.
- **No monster tribes/populations.** Solo random spawns; no lairs,
  chieftains, growth, or raids. Group dynamics exist only for humans.
- **NPC goals are inert.** 1-3 goal strings are generated and shown in
  prompts but never drive a single action. No NPC↔NPC relationship graph;
  factions are two scalars with no agenda; society freezes off-screen.
- **Gods are passive bookkeeping.** They only react to the player and grant
  small self-buffs — no divine events, wrath, cults, or god-vs-god.
- **Adventures don't branch.** 19 quests chain but never fork; the `FAILED`
  state is defined and never used; no main arc / ending; one puzzle
  mechanic with one instance; off-origin world is procedural noise.
- **Graphics snap.** Procedural vectors, tile-to-tile teleport (no
  tweening), no attack/hurt animation, no portraits.

Phases 19–22 answer these directly. **The through-line: wire up what's
already built, then deepen.** Much of the highest value (the dead bosses,
the walled-off battle AI, the inert NPC goals) is *connection*, not new
tech — exactly the lesson of Phase 0.

---

## Phase 19 — Monsters & Menace  (George's Ultraplan, 2026-07-12) — the "Dragons? Coop? Tribes?" arc

The endgame has no teeth and the world's creatures don't behave like
creatures. This phase gives the player things worth fearing and monsters
that act like a coordinated, populous ecology. Content-as-data throughout;
leans on the existing boss framework (`engine/bosses.py`) and the
Phase-17 tactical AI.

- [x] **P19.1 The apex tier: dragons & fire-breath.** Author a true apex
  tier in `data/monsters.json` — a young + an elder dragon (and a wyvern /
  a drake / a lich as the roster grows), each a `boss` with a telegraphed
  breath, phases, and terror. Extend `engine/bosses.py` with a **`breath`
  telegraph kind** that scorches the struck tiles (dragonfire leaves
  burning ground via the surface layer) and a **`terror` phase action**
  that Frightens the player (P12.2 condition). Make the new tier
  **reachable, not dead**: deep dungeon den-lords draw from a depth-scaled
  apex pool (so the built-but-unspawnable warlord/wisp-queen/hill-giant
  finally appear), not only the Tyrant. Validator + tests.
  *(Round: a dragon family in `data/monsters.json` — `dragon_whelp`
  (L5 minion, the summon target), `young_dragon` (L12, hp120, fire breath,
  a terror roar at 50% then enrage at 30%) and `elder_dragon` (L16, hp190,
  a wider hotter breath, terror → summons whelps → full-wrath enrage). All
  `dragonborn`, `flee_below: 0` (they never rout), `encounter_weight: 0`
  (lair/dungeon content, never a wild wander). `engine/bosses.py` gains
  the `breath` telegraph kind (after the blast it `ignite`s the struck
  radius on the surface layer — dragonfire leaves the ground ablaze) and
  the `terror` phase action (`apply_effect` Frightened N on the player).
  Reachability: `world/monsters.apex_pool(depth)` returns the boss-tier
  templates a dungeon of that depth may crown its deepest floor with — the
  formerly test-only warlord/wisp-queen/tyrant opt in via a new
  `boss_depth`, and a young dragon waits below depth 3, an elder below
  depth 5; `world/dungeon.populate_dungeon` draws the den-lord from it
  instead of the hardcoded Tyrant. In a dungeon the breath telegraph is
  quiet (the conflict scan is overworld-only) but the terror/summon/enrage
  phases and the heavy melee make a genuinely hard fight; the full breath
  comes online when a dragon is met on the overworld (a lair — P19.2). 11
  new tests + 1 retuned dungeon test. Suite 1878, green.)*
- [x] **P19.2 Lairs on the overworld.** Seeded monster lairs (a dragon's
  roost on a peak, a goblin warren, a troll den) as overworld locations
  that hold an apex or a pack over a hoard; clearing one yields the hoard,
  a legend, and lasting quiet. The reachable, hand-placed home for the
  P19.1 tier outside dungeons.
  *(Round: `engine/lairs.py` `LairSystem` over `data/lairs.json`
  archetypes (occupants + hoard + gold + a `near` terrain affinity + a
  legend line). `seed()` (from `start_game`, after structures) plants up
  to one of each archetype on a walkable site near its terrain, ≥18 tiles
  from the player start and clear of towns; it spawns the occupants
  (tagged `metadata["lair"]`), drops a named `Location` marker so the
  place reads on the map, and records the lair. `check_cleared()` (per
  turn, cheap) watches each lair's defenders — when the last falls, the
  hoard spills onto the ground, the gold fills your purse, and a
  `[Legend]` line marks the deed; the lair stays cleared for good.
  Because a lair sits on the OVERWORLD, an apex there gets its FULL kit —
  the P19.1 breath telegraph fires (it only paints while `active_zone()`
  is None), so a roost is where you actually face a dragon breathing fire
  and scorching the ground. State persists (`to_dict`/`from_dict`
  registered in `save_load`; `_seeded` guards re-seeding on load). One
  latent bug surfaced and fixed: `find_character` returned the FIRST
  name match, so with a Wandering Troll now in both a den and a crypt,
  "attack the Wandering Troll" could reach for the wrong one — it now
  prefers the NEAREST active match (`_nearest_active`). 11 lair tests + 1
  retuned. Suite green.)*
- [x] **P19.3 Packs that fight like a group.** Bridge the walled-off
  Phase-17 `battle_ai` (or extend `squad_tactics`) so overworld monster
  packs focus-fire the softest target, flank, hold a leader, and break
  when the leader falls — real coordination, not incidental adjacency.
  *(Round: `engine/monster_packs.py` `MonsterPackSystem.update()`, run at
  the top of `process_npc_turns` (before the creatures act). Each turn it
  bands the hostiles near the player into packs — a lair's own occupants
  (shared `lair` tag, so mixed kinds band) or a cluster of the same kind —
  crowns the strongest as leader (remembered SYSTEM-SIDE across turns, so
  a survivor-only regroup can't quietly re-crown and hide the leader's
  death), and writes two intents the heuristic brain already honours:
  a shared **focus** (the whole pack piles onto ONE target — the softest
  it can reach, a wounded companion over a hale player) and **morale by
  leader** (`pack_broken` when the remembered leader has fallen). Two
  small hooks in `heuristic._hostile_action`: a broken-pack member breaks
  and flees (ahead of the default hostility), and the default attack aims
  at the pack's `focus_name` instead of always the player. Solo monsters
  and party-less fights are untouched — a loner has no pack, and with no
  companions the focus is just the player, exactly as before. No
  persistence (tags are transient, recomputed each turn). 11 tests
  (formation by kind and by lair; the lone beast; strongest-is-leader;
  stale tags cleared; one shared focus; focus on the soft ally then back
  to the player when healthy; leader-death breaks the pack; a broken
  beast flees; a steady pack attacks). Remainder P19.3b: explicit flank
  positioning via `squad_tactics.surround_step`/`flank_tile` (today's
  flanking is still the incidental +2, not planned encirclement).)*
- [x] **P19.4 Monster tribes as populations.** A monster faction
  (goblins / trolls) with a lair, a chieftain, population growth,
  territory, and raids on settlements — the human `faction_ticker`
  mirrored for monsters, so the world has a hostile society that grows,
  presses, and can be beaten back. The "actual populations" ask.
  *(Round: `engine/monster_tribes.py` `MonsterTribeSystem` over
  `data/tribes.json` (The Gorge Goblins, The Crag Trolls — each a race, a
  `strength` 0-100, a `growth`, a `raid_threshold`/`raid_cost`, a raider
  + champion template, a home terrain). `run_day()` (nightly, after the
  faction ticker) grows every tribe; a tribe over its threshold swarms out
  to raid the NEAREST settlement — draining that settlement's P16
  production store, spending `raid_cost`, and, when the raid is within
  sight of the player, spilling a raid party onto the map: raiders tagged
  `metadata["tribe"]` AND `metadata["lair"]="tribe:<id>"` so the P19.3
  pack brain runs them as a coordinated band under a champion (chieftain)
  that rides out at high strength. Beaten back: every tagged raider the
  player fells calls `on_defeat` (hooked in `combat_system._resolve`),
  knocking the tribe's strength down — repel a raid and the tribe drops
  below its threshold for nights, a `[Realm]` "beaten back" beat; ignore
  it and it grows and returns. Strength persists (`to_dict`/`from_dict`
  registered in `save_load`). 14 tests. Suite green. Remainder P19.4b:
  tie a tribe's home to a P19.2 lair so CLEARING the lair wipes the tribe;
  and scale the raider encounter weight by tribe strength.)*
- [x] **P19.5 The endgame curve.** Elite / champion variants and
  party-scaled packs so a high-level party meets worthy resistance; a
  roaming world-boss that stalks the map. No more trivial wilderness.
  *(Round: `engine/elites.py` scales the wild to the party WITHOUT
  re-authoring monsters. `party_level` reads the strongest member plus a
  nudge for party size. When a fresh wilderness spawn is out-levelled,
  `maybe_promote` may crown it an ELITE from `data/elites.json` tiers —
  a Dire (gap ≥2), a Champion (≥5), an Ancient (≥9) — retitled and buffed
  (hp ×, +levels, +STR, an `elite` tag), the tier and its odds climbing
  with the gap; and `extra_pack` draws a WARBAND (up to 3 extra beasts)
  for a strong party. Wired into `encounters.maybe_spawn`: the promoted
  spawn leads, the extras share a `warband:<id>` tag so the P19.3 pack
  brain runs them under it — cut the elite leader down and the warband
  breaks. The HUD line reflects it ("A fearsome Ancient Troll…", "A pack
  of Dire Wolves…"). Low-level play is untouched — no gap, no promotion,
  no warband. 11 tests (party level solo and with a party; no promotion
  without a gap; a high party promotes and the title/HP/level change; the
  chance can decline; the tier grows with the gap; `apply_tier` buffs;
  warband size and cap; a fixed-seed L20 field meets elites/warbands).
  Remainder P19.5b: a named ROAMING world-boss that stalks the overworld
  map (the apex that hunts YOU), distinct from the lair-bound P19.2 tier.)*
- [x] **P19.6 The Nemesis.** Named monster champions (Shadow-of-Mordor
  style) that survive a losing fight, remember the player, rise in power
  and title, recruit, and return for revenge — tied to the bones /
  legendarium so grudges become legend.
  *(Round: `engine/nemesis.py` `NemesisSystem` over `data/nemesis.json`
  (name pool, escalating titles, config). `intercept_death`, hooked into
  `combat_system._handle_defeat` BEFORE the person/monster split (so it
  works for a human or a beast) and gated to the PLAYER's own blade: an
  ELITE (P19.5) at death's door may be BORN a nemesis — given a name and
  a title — and flee the field instead of dying; an existing nemesis with
  escapes left flees and RISES (power +1, a grander title from the
  ladder); one out of escapes dies for real and passes into the
  Legendarium (`dm_library.record_legend`) with a `[Legend]` "falls at
  last" beat. `run_day` (nightly) brings a living, off-field nemesis back
  to hunt the player — a champion scaled by its power (level + HP + STR),
  tagged `elite` + `nemesis_id` so the P19.5 elite handling and the P19.3
  pack brain both apply. Ordinary foes are untouched (intercept returns
  early); the roster persists (`to_dict`/`from_dict` in `save_load`). 10
  tests (an ordinary foe dies; a nemesis escapes and rises and earns a
  grander title; out of escapes it dies and becomes legend; an elite can
  be born a nemesis; it returns scaled; `_on_field` liveness; no duplicate
  while on field; persistence; and killing a tagged elite in real combat
  makes it escape). This completes Phase 19's monster arc. Remainder
  P19.6b: nemeses that RECRUIT underlings and hold ranks.)*

## Phase 20 — The Living Society & the Gods  (Ultraplan, 2026-07-12) — the Autonomous-World imports

The player-facing NPC layer is excellent; the world *behind* it is inert.
This phase gives NPCs agency, a social web, and gods that act.

- [x] **P20.1 Ambitions that drive action.** A nightly, heuristic
  goal→action layer so an NPC's goal string produces real behaviour —
  save to retire, court a sweetheart, open a shop, avenge a wrong,
  migrate. The biggest "living world" gap: goals that *do* something.
  *(Round: `engine/ambitions.py` `AmbitionSystem` over
  `data/ambitions.json`. Each NPC's goal strings are matched by keyword to
  an AMBITION — wealth / romance / mastery / vengeance / escape (cached on
  metadata; a "duty" goal like "protect the village" earns none). `run_day`
  (nightly) accrues quiet progress toward it and, when it fills, REALISES
  it with a real, persistent effect and a `[Realm]` beat the gossip system
  carries: a merchant prospers and pockets a retirement nest-egg
  (`prospered`, +gold); two unattached civilians become sweethearts (a
  MUTUAL `partner` link + a +45 relationship — an emergent couple, a peer
  bond, not a spoke to the player); a crafter is hailed a master
  (`master`, +1 level); an old score is settled; a troubled past is laid
  to rest. Keyword coverage tuned to the real cast's authored goals
  ("make a profit", "earn coin", "advance in rank"), so ~8 of the Oakvale
  cast now pursue something. One quiet progress line a night so it's felt,
  not spammed; all state on `npc.metadata` (rides the NPC's save). 13
  tests (classification incl. a duty→none and caching; progress accrues;
  the goal realises and announces; done ambitions don't re-fire; wealth /
  mastery / romance effects; player-chars skipped). Remainder P20.1b:
  ambitions that MOVE the NPC (migrate, open a new shop building) and
  vengeance that seeks a real target.)*
- [x] **P20.2 The NPC social graph.** Peer-to-peer relationships
  (like / dislike / trust / rivalry) that form and evolve from shared
  events, gossip, and proximity — friendships and feuds in heuristic mode,
  not the LLM-only director path. A world of relationships, not spokes to
  the player.
  *(Round: `engine/social_graph.py` `SocialGraph.run_day()` (nightly,
  after ambitions). Each night it walks the cast (monsters excluded),
  picks each NPC an associate — same-faction peers plus a couple of
  outsiders so it isn't only cliques — and drifts their MUTUAL
  relationship: kin and same-faction folk warm (`+`), a settlement's
  neighbours grow familiar, the lawful and the outlaw grate (`−3`). Left
  to run, edges cross thresholds on their own: `FRIEND` (+55) mints a
  friendship, `FEUD` (−45) a bitter feud — each latched once in
  `metadata["social"]` and announced as a `[Realm]` beat the gossip system
  carries (the heuristic answer to the director's LLM-only feud). Every
  edge lives in the NPCs' own `relationships` + `metadata`, so the whole
  graph rides the save. Composes with P20.1 — the romance couples are this
  same graph at its warmest. 9 tests (same-faction bonds, lawful/outlaw
  friction, strangers-aren't-kin; crossing into friendship and into feud,
  mutual and announced-once; run_day drifts a private pair; monsters stay
  out; friends AND feuds emerge over 40 nights). Remainder P20.2b: gossip
  that SHAPES opinion (hearing ill of someone lowers your regard for
  them), and alliances/rivalries at the FACTION scale.)*
- [x] **P20.3 Faction agendas.** Factions gain objectives (expand / raid /
  ally / hoard) and pursue them with territory and diplomacy state — wars
  with aims, not dice.
  *(Round: `engine/faction_agendas.py` `FactionAgendas` layers intent onto
  the faction ticker's `{strength, stores}` state, over
  `data/faction_agendas.json`. Each faction holds an AGENDA — brigands
  expand, merchants hoard, guards protect, monsters spread, villagers
  prosper — and every night `run_day` (after the ticker's clash) PURSUES
  it, nudging that faction's own strength/stores toward the aim (which the
  ticker's raids and the wilderness encounter weight already read, so an
  expanding brigand faction really does put more bandits on the roads). A
  DIPLOMACY web drifts too: sworn enemies slide toward war (faster when
  both are strong), natural friends toward alliance, and crossing a
  threshold latches once and fires a `[Realm]` beat — "the brigands and
  the guards are at war", "the guards and the merchants have sworn an
  alliance". And an agenda SHIFTS on fortune: a faction grown strong turns
  to `dominate`, one beaten low falls back to `recover`, then resumes its
  nature. Agendas + relations + latches persist (`to_dict`/`from_dict`
  registered in `save_load`). 13 tests. Suite green. Remainder P20.3b:
  diplomacy that SELECTS the ticker's events (a war makes the two factions
  actually raid each other) and territory the factions hold and contest.)*
- [x] **P20.4 The active pantheon.** Gods that INITIATE: divine events,
  boons and wrath on factions and NPCs, god-vs-god tension, cults,
  festivals, demands with consequences. The Autonomous-World gods import
  the user asked for — the pantheon becomes a set of meddling agents.
  *(Round: `engine/divine_acts.py` `DivineActs` over `data/divine_acts.json`
  turns the passive pantheon into agents. Each night (after the pantheon's
  own omen tick) every god WEIGHS how its domain fares — Solara the harvest
  in the larders, Morrik the strife on the roads, Grimble the coin in the
  markets, Veyra the safety of travel, the Pale Lady the reach of death —
  read from the faction ticker's state and tempered by the favor you've
  built (`god_favor`, favor tips the scales toward a boon). A THRIVING or
  honored domain earns a BOON that swells the god's favoured faction; a
  NEGLECTED one earns WRATH that saps it — and because those numbers drive
  the ticker's raids and the wilderness encounter weight, a god's mood
  really moves the realm. Each act is a `[Realm]` beat pushed into the
  rumor pool. Opposing gods CONTEND: when two who stand against each other
  both act (Solara↔Pale Lady, Morrik↔Veyra), tension climbs the heavens
  until it breaks in a wild-weather storm. Composes with P20.3 — the
  agendas move the faction numbers the gods then judge. The only new state
  is the tension scalar, riding `player.metadata`. 9 tests (a thriving
  domain boons and a neglected one wraths, a middling one is left alone;
  favor tips a god to act; effects clamp; opposing gods build tension to a
  storm that resets while non-opposing acts don't; tension persists; a
  run_day announces divine beats). Remainder P20.4b: cults NPCs join,
  festival days, and a god's DEMAND with consequences.)*
- [x] **P20.5 Runtime history & the saga.** The chronicle accrues at
  runtime — player and faction deeds append to `world_history`, producing
  an emergent saga readable in the Y-journal, so the world remembers.
  *(Round: `engine/chronicle.py` `Chronicle`, registered as an observer on
  the event log (`memory_manager.add_observer`). It watches for the beats
  that shape an age — anything already marked `[Legend]` (a nemesis's fall,
  a lair cleared, a true death) plus the weightiest `[Realm]` beats caught
  by keyword (wars & alliances, a god contending, a tribe swarming out or
  beaten back, a siege, a slaying) — and writes each as a DATED entry into
  a growing saga, prefix stripped, consecutive repeats dropped, capped at
  60. The mundane `[Realm]` traffic (caravans, quiet production) is left
  out. `lines()` renders a "Chronicle of the Age" section the Y-journal now
  shows beneath the pre-game Legends (`gui.show_topics`), so the world
  remembers what you and the factions did to it — and it persists
  (`to_dict`/`from_dict` registered in `save_load`). Composes with the
  whole of Phases 19-20: the nemesis, the wars, the divine contentions and
  the tribe raids all write themselves into the record. 11 tests
  (worthiness of legends/saga-realm/mundane; dated & cleaned capture;
  mundane ignored; consecutive dups dropped; the cap; the observer wiring;
  the journal lines; empty saga; persistence). Remainder P20.5b: fold the
  saga into gossip so NPCs cite recent history, and a proper end-of-campaign
  "chronicle of your age" screen.)*
- [x] **P20.6 Romance & rivalry.** Courtship, friendship, rivalry and
  marriage with the player and between NPCs; jealousy. Turns the single
  affinity scalar into relationship *types*.
  *(Round: `engine/romance.py`. `/court` (a new dialog slash-command,
  wired beside `/bond`/`/persuade`) climbs a LADDER gated by regard —
  courting (rel ≥25) → sweetheart (≥50) → betrothed (≥70) → married (≥85)
  — a named relationship stored on `npc.metadata["romance"]`. Court a
  SECOND while another is already your sweetheart+ and the first grows
  JEALOUS: their regard drops 15 and a marriage is strained down a rung,
  with a jealous `[Realm]` beat. You can't wed two. And the ledger runs
  the other way: `provoke_rival` turns a deeply-soured NPC (regard ≤ −50,
  not a partner) into a declared RIVAL who won't be wooed. Weddings,
  betrothals and rivalries are `[Legend]` beats, so they write themselves
  into the P20.5 chronicle. A nightly `RomanceSystem.run_day` has a spouse
  quietly provide a small gift and hardens grudges into rivalry. Every
  thread lives on the NPCs' `metadata`, riding the save; `/court` is
  advertised in the dialog prompt. 11 tests (the gate refuses the cold;
  the ladder climbs; marriage sets the spouse; you can't wed two;
  jealousy cools the first and strains a marriage; a soured NPC turns
  rival and won't be wooed while a partner never does; a spouse provides;
  a wedding enters the chronicle). **Phase 20 (the Living Society & the
  Gods) is complete.** Remainder P20.6b: courtship BETWEEN NPCs beyond the
  P20.1 ambition-couples, and a spouse who lives with you at your P15.7
  home.)*

## Phase 21 — Adventures, Choice & Consequence  (Ultraplan, 2026-07-12)

- [x] **P21.1 Branching quests.** Choices, mutually-exclusive outcomes,
  reward-choice, and the long-dormant `FAILED` state wired in — side with
  Duke Voss or expose him; consequences that stick.
  *(Round: branching driven entirely through `quest.metadata` (no dataclass
  churn) in `quests/quest_manager.py`. `excludes` — accepting a quest FAILS
  its rivals (`fail_quest`, wiring the long-dormant `QuestStatus.FAILED`);
  `excluded_by` — a quest is locked out once its rival is taken;
  `prereq_flag`/`blocked_by_flag` — choice-flags (in
  `player.metadata["quest_flags"]`, set by a quest's `sets_flag` on
  turn-in) open and shut later paths; `reward_choices` + `choose_reward` —
  pick one of several payouts, folded in at turn-in. All gates fold into
  `is_unlocked`; `quest_templates` now carries the new fields through.
  Demonstrated in CONTENT: a new `castle_voss_gambit` ("The Duke's Offer")
  forks from `castle_the_spy` opposite `castle_gambit` — side with Voss
  (betray the Prince, take his gold) or expose him, and accepting one fails
  the other, each setting its own flag (`sided_with_voss`/`exposed_voss`)
  for the world to react to. Validator clean. 10 branching tests + the
  castle suite still green. Remainder P21.1b: NPCs/factions that REACT to
  the choice flags (Voss's faction favors a player who sided with him),
  and a dialog choice-menu to make the pick in-fiction.)*
- [x] **P21.2 The main arc.** An overarching questline with a spine, a
  climax, and an ending — a world-goal the campaign builds toward.
  *(Round: an authored five-stage main line in `data/quests.json`, each
  `main: true` and chained by prereq — Alzara the wizard reads dark omens
  (The Stirring Wilds → The Source in the Deep → The Old Lore →
  The Gathering Night → **The Reckoning**), climaxing in slaying the Elder
  Wyrm in its lair. `engine/campaign.py` is the thin spine over it:
  `main_line`/`finale_id`, `is_won` (the finale's `sets_flag` "campaign_won",
  P21.1), and `check_finale` (run each turn) which fires a once-only
  triumphant `[Legend]` ending the moment the campaign is won; `summary`
  composes the ENDING from the P20.5 chronicle — the saga you actually
  wrote closes the age, shown in the Y-journal. To let the finale target a
  NAMED quarry, `quest_manager.on_npc_defeated` now also matches a KILL
  objective by the monster's TEMPLATE (e.g. `elder_dragon`), not only its
  class — a general improvement radiant bounties can use too. Validator
  clean. 8 tests (the arc is authored & chained; the finale is the
  reckoning targeting the wyrm; the spine orders; a template-death completes
  the finale; turn-in wins; the ending fires once; it reads the chronicle).
  Remainder P21.2b: a proper full-screen ending sequence, and the arc
  reacting to the P21.1 choice-flags / the living-world state.)*
- [x] **P21.3 Puzzles II.** Levers & gates, pressure plates,
  riddles-with-answers, combination locks, item-fit puzzles — many
  instances, beyond the single sigil ward.
  *(Round: the sigil-ward plumbing generalised with a puzzle `kind` and
  two new types in `world/structures.py`. `pull_lever` — a LEVER-GATE:
  throw the levers until the thrown-set matches the mechanism's `pattern`
  and the warded stairs grind open (toggle a wrong one back off to
  recover). `offer_at_altar` — an ITEM-FIT altar: lay the item it
  `requires` upon it and the ward dissolves, the offering consumed. Both
  gate stairs through the existing `stairs_warded`. Wired through
  `furniture.py` (a "Lever" routes to `pull_lever`; an "Altar" routes to
  `offer_at_altar` ONLY when its level bears an altar-puzzle, else it
  falls through to prayer as before) and the grid builder (`L` = lever,
  numbered like sigils; `S` altar already exists). Lever progress persists
  (`lever_state` in `to_dict`/`from_dict`); the generic `solved` set carries
  the rest. Authored in CONTENT: a three-lever gate in the Ruined Keep's
  Great Hall wards the descent to the crypt — "throw the first and the
  last, but never the middle" (pattern [0,2]) — the game's second puzzle,
  and the first of a kind. Validator learns `L`. 9 tests (both mechanics,
  the recover-from-wrong toggle, furniture routing incl. the plain-altar
  prayer fall-through, the keep's authored gate, persistence). Remainder
  P21.3b: riddles-with-typed-answers, pressure plates, and more authored
  instances.)*
- [x] **P21.4 Set-piece variety.** Escort / protect, stealth / heist,
  timed / chase, and boss-tied quests; a player-joinable siege or battle
  (the P17 layer the player fights *in*, not watches).
  *(Round — the TIMED set-piece (chase against the clock): a quest with a
  `time_limit` starts a countdown (`turns_left`) on acceptance;
  `on_turn_advanced` runs it down each turn (beside the SURVIVE tick), and
  one that expires unfinished FAILS through P21.1's `fail_quest` — beat the
  clock and the countdown clears. A `time_left(id)` query feeds a HUD
  timer. Authored: "Before the Trail Goes Cold", a 60-turn bounty on a
  marauder. `quest_templates` carries `time_limit`. 6 tests (the clock
  starts on accept, ticks down, expires to FAILED, clears on completion,
  leaves untimed quests alone; the content). Remainder P21.4b: escort /
  protect (an NPC that must reach a place alive), stealth / heist, and a
  player-JOINABLE P17 battle rather than an off-screen one.)*
- [x] **P21.5 Landmarks off-origin.** Streamed regions seed named
  locations, dungeons, and mini-quests instead of procedural noise;
  richer, real biomes.
  *(Round: `world/chunked_world._seed_landmarks`, called from `_generate`
  for every non-home region, over `data/landmarks.json` — the Old Ruins,
  a Wayside Shrine, a Dark Hollow, a Hermit's Rest, the Standing Stones, a
  Sunken Barrow. It places one or two on terrain that SUITS each
  (`terrain` list matched against the tile's value), as named `Location`s
  flagged `landmark`, and a `tile: "cave"` landmark stamps a real CAVE
  entrance — so a Dark Hollow off-origin actually leads into a procedural
  dungeon. Deterministic per region (seeded from the region's own seed via
  the chunk store), so the wider map is stable, and the landmarks ride the
  region cache (`cached_locations`) when you leave and return. The home
  region is untouched (it keeps its authored places). 4 tests (home has
  none; a streamed region gets named landmarks; they're deterministic per
  region; a cave-mouth landmark is a real dungeon entrance). Remainder
  P21.5b: mini-quests and small NPC casts at the landmarks, and the
  biome enum made real rather than aspirational.)*
- [ ] **P21.6 Treasure & legend.** Legendary hoards and unique named
  artifacts tied to discoverable lore and the legendarium; a treasure-map
  loop that pays exploration.

## Phase 22 — Graphics & Game-Feel  (Ultraplan, 2026-07-12)

- [ ] **P22.1 Tweened movement.** Smooth interpolated tile-to-tile motion
  for player, NPCs and monsters (headless-safe math in `ui/animation.py`).
  The single biggest perceived-quality win.
- [ ] **P22.2 Action animation.** Attack lunges, cast flares, hurt recoil,
  death throes — frame states on the body renderer.
- [ ] **P22.3 NPC portraits.** Procedural face art in the dialog box,
  driven by race / class / mood.
- [ ] **P22.4 Living tiles.** Animated water and foliage, seasonal terrain
  tints, richer weather.
- [ ] **P22.5 UI theming.** A cohesive, art-styled HUD and panels with
  iconography.
- [ ] **P22.6 Non-blocking spellcasting (George, 2026-07-12).** The X-key
  spellbook overlay blocks the whole view — fatal when you're casting mid-
  combat and need to see the field. Design a spell system that stays out
  of the way: a quick-cast hotbar / number-key slots for favourited spells,
  or a compact radial/side rail that leaves the battlefield visible, with a
  target already picked (P8.7 targeting). Research how action-RPGs surface
  spells in combat (Diablo/Path of Exile hotbars, Tyranny/Pillars quick-
  cast, Caves of Qud ability slots). Important for combat feel.
- [ ] **P22.7 Buildings you can read at a glance (George, 2026-07-12).**
  Every building looks alike, so you can't tell a smithy from a home or
  find the vendor. Give them IDENTITY: per-kind building styles/roof
  colours (the `renderer_buildings` height/colour data already keys off
  kind — extend it), hanging SIGNS over shops/inns/temples (an anvil, a
  mug, a sun), and a genuinely better 2.5D pass for multi-storey builds
  (the castle, towers, the inn's loft). Research town-rendering in other
  games + Autonomous World. "Important to making the game enticing to
  play."

## Phase 23 — Law, Witness & the Society of Estates  (George, 2026-07-12) — the "affected by the player" arc

The world should SEE the player and answer for it, and it should be a
society of interlocking estates the player can shake. Foundations exist
(`law.py` bounties + stolen flags + witness-outfit memory, `trespass.py`,
`discovery.can_witness` fresh-LOS gate, P16 professions) — this phase
turns them into a living justice-and-society loop.

- [x] **P23.0 Walls are solid (bug-fix).** NPCs and monsters phased
  through building walls — on the overworld (`move_character` blocked
  only WATER/MOUNTAIN, never BUILDING) and inside a zone (zone-native
  monsters were stepped on the OVERWORLD grid at their zone-local coords,
  ignoring the zone's own walls). *(Round: a new `engine/movement.py`
  wall guard, installed on the active `WorldMap` and consulted by the one
  movement chokepoint `move_character`. It validates each move against the
  grid the mover ACTUALLY occupies: a zone-native creature — dungeon
  monster / interior visitor / tutorial cast — against the active zone's
  terrain (a BUILDING tile is a wall, fliers included); everyone else
  against the overworld, where a BUILDING footprint is solid except its
  south door tile, so nothing enters or leaves a building through a wall
  (a breach is RUBBLE, not BUILDING, so it still admits). The player is
  untouched — it never reaches `move_character` on a building tile and
  moves in zones via `_move_in_zone`. Installed idempotently at
  `start_game` and re-asserted each NPC turn; streaming mutates the map in
  place so the guard survives. 7 tests. Suite 1867, green.)*
- [ ] **P23.1 Witness & consequence.** NPCs and guards that see the
  player (fresh LOS via `can_witness`, plus overheard/reported) react to
  what they witness — theft, assault, a break-in, a drawn blade in town —
  with alarm, memory, relationship and reputation hits, and a guard
  response. Extends the P12.9 law ledger and the P9A.4 trespass alarm
  into a general witnessed-crime system.
- [ ] **P23.2 Arrest, jail & trial.** A caught criminal can be seized by
  guards, disarmed, and locked in a cell (the player as prisoner — a real
  jail zone), then face a trial whose verdict turns on evidence,
  witnesses, reputation and social checks (persuade/bribe/confess/resist),
  with outcomes from fine to sentence to escape. Builds on the law
  confrontation menu (`law.py`, jail option).
- [ ] **P23.3 The society of estates.** A structured society whose roles
  interlock and answer to each other — Crown & court, sergeant-at-arms &
  garrison/army, magistrates & courts, guildmasters & tradesmen,
  farmers/miners/craftsmen feeding the P16 economy — each an estate with
  standing, duties, and a stake the player can raise, ruin, or overturn.
  The P16 professions become a social order, not just a supply chain.
- [ ] **P23.4 Standing & office.** The player earns (or loses) standing
  within an estate — a commission in the guard, a guild rank, a title at
  court, a seat at a magistrate's table — that unlocks powers and duties
  and makes the player a mover in the society, not only its guest.

## Phase 24 — A World of Places  (George, 2026-07-12) — cities, towns, villages, ruins & the teleport network

The origin region is rich; everything past it is procedural noise
(`chunked_world` light-touch fill). This phase makes the wider world a
map of real places worth travelling between.

- [ ] **P24.1 Settlement tiers.** A generator for CITIES, towns and
  villages at distinct scales — a walled city with districts, quarters and
  a market; towns; hamlets — each with its own cast, trades, and P16
  economy, seeded into streamed regions instead of noise. (Autonomous
  World / Kenshi / Mount & Blade town models.)
- [ ] **P24.2 Ruins & lost places.** Ruined cities, abandoned keeps,
  overgrown temples and battlefields as explorable set-pieces with lore,
  hazards, and hoards — the emergent history (`history_sim`) written onto
  the map as places, not just log lines.
- [ ] **P24.3 The teleport network.** Public teleportation platforms
  (waystones / gate-pylons) that link major settlements for fast travel —
  a networked map the player unlocks and pays or attunes to, extending the
  P11 diary-teleport into a visible, shared transit system.
- [ ] **P24.4 Roads, trade & travellers.** The places are stitched by
  roads the P16.2b caravans and NPC travellers actually use, so the world
  between towns is alive with traffic, not empty.

## Phase 25 — Inventory, Items & the Skill Web  (George's Ultraplan 2, 2026-07-12)

Two live bugs in how the world holds its stuff, then a real inventory
experience and a much wider skill/item web. Bugs first (they're cheap and
they bite every session).

- [x] **P25.0 (BUG) Region-change ground items.** Dropped treasure and
  KO'd bodies reappear in a NEW region at the same coordinates: the
  streamer (`world/chunked_world.py`) caches terrain, locations and NPCs
  per region but never caches or clears `world.ground_items`, so the flat
  (x,y) dict bleeds across the boundary. Fix: cache & restore `ground_items`
  per region alongside the rest (and clear for a freshly-generated region).
  *(Round: a `cached_ground_items` map on the `ChunkedWorld` store, keyed
  by region. `_cache_current` stows the leaving region's `world.ground_items`
  then clears the live dict; `_restore` brings a visited region's loot back;
  `_generate` starts a fresh region empty. So dropped treasure and bodies
  now travel with their region — gone when you cross the border, waiting
  where you left them when you return. 4 tests. Suite green.)*
- [x] **P25.0b (BUG) Multi-level building ground items.** Items dropped
  inside a building appeared on EVERY floor: `world.ground_items` was one
  flat (x,y) dict and building levels reuse coordinates, so the renderer's
  zone pass drew all of them on whatever floor you stood on. *(Round: the
  same swap that fixed regions, applied to zones — each zone (interior /
  dungeon floor) owns its `ground_items`, and `engine._sync_ground_items`
  points `world.ground_items` at the active grid on every transition
  (enter/exit building, stairs, enter/exit dungeon), parking the overworld
  store on `world._overworld_ground_items` while you're inside. Every
  ground-item caller (drops, bodies, loot) keeps using `world.ground_items`
  and now hits the current floor's store; the renderer's zone pass draws
  only that floor. Save writes the parked overworld store, so saving in a
  dungeon can't clobber the overworld's loot. 5 tests. Suite green.
  Remainder: persisting ZONE-dropped items across a save.)*
- [ ] **P25.1 (BUG) Stackable items don't group.** Arrows and other
  stackables take one inventory slot EACH instead of stacking, filling the
  pack. `Item` already carries `stackable`/`quantity` and renders "name
  xN" — the miss is on the add path (`inventory.append` everywhere). Fix:
  a single `give_item`/`add_to_inventory` helper that merges a stackable
  into an existing stack (by id) and is used by pickup, buy, trade, loot.
- [ ] **P25.2 Magical bags & rucksacks.** Containers that raise carry —
  a plain rucksack, a quiver (ammo only), a magical bottomless bag — as
  `data/items` gear that `engine/carry.py` reads for its slot budget; some
  slot-typed (a quiver holds arrows, not armour).
- [ ] **P25.3 The character & items window.** A dedicated drag-and-drop
  screen: the paperdoll with equipment slots, the bag grid, the quiver —
  drag an item onto the character to equip, between bags to move, with
  item graphics. The GUI face of the inventory the game has always had in
  data.
- [ ] **P25.4 The skill web — vastly expanded.** Many more skills beyond
  the current 12 (thievery/lockpicking, herbalism, enchanting, arcana &
  the magic schools, taming/beastcraft, tailoring, runecrafting,
  scavenging…), each with its XP curve, a pet, and a teacher — the
  `data/skills.json` lattice widened.
- [ ] **P25.5 Skill-gated items & features.** New content that REQUIRES a
  skill and its tools, so the skills matter: an enchanting table (Enchanting
  + reagents), lockpicking real locks (Thievery + picks), taming a beast
  companion (Beastcraft + bait), brewing (Alchemy II), runes (Runecrafting)
  — each a feature + the items it needs, content-as-data.

## Phase 26 — Balance & the Weight of Mastery  (George's play notes, 2026-07-12)

Advancement is too cheap and too fast. Levels, skills and spellcasting all
come easily, so nothing feels earned and casters run away with the game.
This phase re-paces mastery so time and training are the real cost —
investigate the current curves first, then deepen.

- [ ] **P26.1 Character advancement re-paced (George).** Characters gain
  XP, levels and skills too quickly. Investigate `engine/leveling.py`
  (the XP curve) and `engine/skill_progression.py` (the 12-skill lattice),
  then build a more advanced, slower, training-gated system across ALL
  character aspects — level XP that respects the difficulty of what you
  fought, skills that need real practice/time (and maybe a trainer) rather
  than a few actions, and diminishing returns on grinding. "More balanced
  with time and training needed to learn skills."
- [ ] **P26.2 Magic overhauled (George).** Spellcasters are too powerful:
  mana replenishes far too fast, so there's no cost to casting. Overhaul
  the magic system (`engine/spells.py`) — a slower, more advanced mana /
  spell-power recovery (rest-gated regen, a spend that actually bites,
  perhaps spell slots or a fatigue cost), and a real system for LEARNING
  spells (study, tomes, a teacher, prerequisites) instead of simply knowing
  them. Research how CRPGs pace casters (Vancian slots, cooldowns, spell
  points with slow regen).
