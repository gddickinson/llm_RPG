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
- [ ] **P3.7 Nightly world director.** One LLM call per game-night reads the day's
  event log + faction state and emits 1–3 structured events (rumor, shortage, feud,
  caravan, monster sighting) that heuristics act out and gossip spreads. LLM-as-director
  is dramatically cheaper than LLM-per-NPC and feeds Phase 4's radiant quests.
- [ ] **P3.8 NPCs notice the player.** Inject a "recent player deeds" digest (kills,
  quests done, gear worn, levels) into every dialog prompt. Single cheapest
  living-world win in the research; substitutes for RuneScape's social status displays.
- [ ] **P3.9 Cost/latency discipline.** Heuristics keep running schedules/pathing/barks
  (never per-tick LLM); LLM fires only on player conversation, nightly reflection for
  ~10 named NPCs, and the director. Cache greetings; stream responses; per-NPC
  anti-sycophancy rules in prompts ("you will NOT lower your price below X").

**Exit criteria:** playing with `--provider anthropic/ollama` is *mechanically*
different from heuristic mode: you can talk your way into secrets, discounts, quests,
and out of fights — and NPCs remember you across sessions.

---

## Phase 4 — Quests, world, onboarding  (~2–3 weeks)

- [ ] **P4.1 Radiant quest generation.** Procedural task quests (kill/fetch/deliver/
  escort) generated from world state — director events (P3.7), shortages, faction
  tension — posted to quest boards with level-scaled rewards. Fixes the permanently
  questless world after the 6 templates are done.
- [ ] **P4.2 8–12 handcrafted quests, one bespoke mechanic each.** OSRS lesson: 10
  great quests beat 50 generated ones; use humor; skeleton authored, dialog
  LLM-rendered. **Rewards are capability unlocks, not XP**: a teleport node, a map
  shortcut, tool upgrades, area access, auto-pickup ammo, a companion.
- [ ] **P4.3 Quest points + guild.** Each quest grants 1–3 QP; an Adventurers' Guild
  building unlocks at N QP with its own board, bank, shop, trainers.
- [ ] **P4.4 Tutorial Island.** Small separate starter zone; one instructor NPC per
  system (fish→cook→mine→smith→fight→cast→bank), each teaching by one repetition;
  one-way boat to the mainland. Instructors are the LLM-NPC showcase — narrow-domain
  characters who answer freeform questions, with scripted fallback checklists.
- [ ] **P4.5 Regional identity.** Give each region a theme, unique resources, unique
  monsters, a 2–3 quest mini-arc, and its diary (P2.7). Add one new themed region
  (swamp or highlands) to the 120×80 map. Interleave danger levels — a deadly pocket
  near a safe road creates "I'll come back stronger" goals.
- [ ] **P4.6 History with residue (Caves of Qud pattern).** Extend `history_sim` so
  each generated event leaves physical artifacts: a named relic in a dungeon, a ruin,
  an NPC grudge, a findable book; LLM renders the legend text. Expose a "Legends"
  journal; NPCs cite events by name via gossip.
- [ ] **P4.7 Failure-as-story.** On player defeat outside dungeons: robbed and dumped
  at the nearest temple, or captured by brigands (escape mini-scenario) — death popup
  becomes the fallback, not the only outcome (Kenshi lesson).

---

## Phase 5 — Combat depth & feel  (~1–2 weeks, interleave anytime)

The resolution math (d20 + mods vs AC, crits, flanking, damage types) is genuinely
good; the tactical layer is absent — enemies wander-or-attack, the player bump-attacks
and heal-spams.

- [ ] **P5.1 Enemy AI profiles** (data-driven per monster): pack-hunt flanking
  (wolves), ranged kiting (goblin archers), flee-at-low-HP (bandits), guard-territory
  (trolls), call-for-help. A few behavior flags each — not a new AI system.
- [ ] **P5.2 Spell selection UI + spell growth.** Hotkey opens a spell menu (only 2 of
  7 spells are castable today); learn spells from trainers/quests/scrolls; add ~8 more
  spells via the data layer.
- [ ] **P5.3 Player tactical verbs:** disengage/flee (opportunity-attack risk), shove,
  aimed shot (ranged), drink-potion-as-turn. Small verb set, big texture.
- [ ] **P5.4 Off-screen faction ticker.** One dice-resolved faction event per game-day
  (patrol, raid, trade caravan) that moves stockpiles/rep and feeds gossip + radiant
  quests. The world visibly doesn't wait for the player.
- [ ] **P5.5 Sound.** pygame.mixer: ambient loops per biome/weather + combat/UI SFX.
  (Procedurally generated or CC0 packs; big feel win, low effort.)
- [ ] **P5.6 End-of-session hook.** Sleeping at an inn/home: heals, advances to
  morning, and shows a "day summary" (skills gained, gold delta, director event
  teaser) — Stardew's "tomorrow I'll…" engine, adapted lightly.

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

## What NOT to build (explicitly deferred)

- Continuous LLM agent simulation (Generative Agents-style) — cost-prohibitive; the
  director + salient-interaction pattern captures 80% of the value.
- Networked multiplayer, 3D mode, web UI — ROADMAP long-term, irrelevant to the
  quality/richness goals.
- LLM-generated main plot (AI Dungeon's trap) and voice I/O.
- Punishing survival mechanics for the player (needs stay light).
