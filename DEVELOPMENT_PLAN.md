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
  6 regression tests in `tests/test_save_full_state.py`. Remainder: dungeon/
  interior state, quest boards, shop stock still not persisted — tracked as P0.1b.)* `character.to_dict()` (`characters/character.py:209`)
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

## What NOT to build (explicitly deferred)

- Continuous LLM agent simulation (Generative Agents-style) — cost-prohibitive; the
  director + salient-interaction pattern captures 80% of the value.
- Networked multiplayer, 3D mode, web UI — ROADMAP long-term, irrelevant to the
  quality/richness goals.
- LLM-generated main plot (AI Dungeon's trap) and voice I/O.
- Punishing survival mechanics for the player (needs stay light).
