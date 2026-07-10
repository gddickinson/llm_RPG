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
- [ ] **P1.4** (Stretch) A "module pack" folder convention — the ROADMAP's campaign
  packs fall out of this nearly for free.

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
- [ ] **P6.3 Session-DM bridge** (`--dm-bridge`): file-based —
  the game exports `saves/dm/digest.json` (each game-day + on demand) and
  polls `saves/dm/inbox/*.json` for command bundles. Claude Code (a session
  like this one) acts as the live DM: read digest → reason → write commands.
  Human-supervised godhood; also the perfect test harness for P6.4.
- [ ] **P6.4 Autonomous DM**: one planning call per game-day through the
  existing provider abstraction — reads digest + notebook, maintains a
  campaign arc in `dm_notes` (persisted in saves), emits a validated command
  bundle (the director's JSON-list pattern, bigger toolset). Cost: same
  order as reflection+director (~1 call/day). No provider → the director
  keeps running unchanged; the game never depends on the DM existing.
- [ ] **P6.5 Adventure modules**: the DM composes atomic bundles — a
  location + NPCs + quest chain + secrets + topics + a finale beat —
  validated as a unit and rolled back wholesale if any piece fails.
  Modules are named in the notebook and announced diegetically (a rumor,
  a stranger arriving, a new notice on the board).
- [ ] **P6.6 Charter enforcement + safety tests**: unit tests that the API
  refuses charter violations (player-touching, over-cap monsters, quest
  vandalism), budget accounting via `llm_interface.call_counts`, injection
  separation, and a save/load round-trip of DM-created content.

- [ ] **P6.7 The Legendarium — persistent generative library** (George,
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

**Verdict:** feasible and the natural capstone — P6.1–P6.3 are buildable in
loop rounds immediately after Phase 5; P6.4 rides infrastructure that exists.
P6.7 turns the DM from a session feature into a compounding one: the game
gets permanently richer every time it's played.

## What NOT to build (explicitly deferred)

- Continuous LLM agent simulation (Generative Agents-style) — cost-prohibitive; the
  director + salient-interaction pattern captures 80% of the value.
- Networked multiplayer, 3D mode, web UI — ROADMAP long-term, irrelevant to the
  quality/richness goals.
- LLM-generated main plot (AI Dungeon's trap) and voice I/O.
- Punishing survival mechanics for the player (needs stay light).
