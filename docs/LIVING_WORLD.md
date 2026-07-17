# LIVING_WORLD.md — purposeful behaviour for NPCs, animals & monsters

A design + phased build plan to make the world's actors *do things* — visibly,
per-turn — instead of milling about. Grounded in an audit of the current systems
(2026-07-17). Companion to `DEVELOPMENT_PLAN.md`; build in tested rounds on
`v2-development`, commit + push each green round.

---

## 1. The problem (from the audit)

The game already has a **rich goal-directed simulation** — but it runs almost
entirely **nightly and abstractly** (as numbers + throttled `[Realm]` log lines),
while the **per-turn behaviour you watch is thin**. So a town reads as aimless
milling even though an economy, ambitions, and a social graph are turning over
between days.

| Domain | What exists | Where it runs | What you SEE |
|---|---|---|---|
| **NPCs / professions** | 6-class daily schedules; a full profession economy (miner/smith/cook/farmer/…); ambitions; social graph | **Nightly, abstract** (`production_loop`, `ambitions`, `social_graph`) | `schedules.activity_to_action` **flattens** work/patrol/pray/play → `("move", location)` → walk there → **loiter**. A smith "at work" looks identical to an idle villager. |
| **Animals** | Fox→rabbit predator/prey, flee-player, breed/starve | **Per-turn (≤10 tiles)** + nightly | Real hunts & flees, but **no sleep, no day/night, fake grazing** (random wander — diet is metadata only), **no herding**, 1 predator. |
| **Monsters / tribes** | Tribe = a `strength` int that raids nightly; pack combat roles; lairs | **Nightly** (tribes) + **combat-only** (packs) | Idle hostile = **random cardinal wander**. Lair occupants **scatter** (goblins lack a leash) and idle until you arrive. **No tribe roles, no camp, no lair life.** |

Root causes to fix:
- **Activity flattening** — `schedules.activity_to_action` (`characters/schedules.py:98-113`) collapses every activity to `move`/`wait`; profession identity is erased before it reaches the renderer.
- **Dead work handler** — `action_router._handle_work` (`engine/action_router.py:378-396`) is unreachable on the heuristic backend and mis-gated to `klass == "merchant"`.
- **Scheduleless classes** — only 6 classes have schedules; wizard/rogue/noble/etc. fall to a literal `rng.choice(["north","south","east","west"])` (`llm/providers/heuristic.py:208-210`).
- **Data never drives motion** — `building_types` (building→profession) and `production` (profession→workstation/recipe) feed only the nightly store math.
- **No day/night for creatures** — `WildlifeSystem` never reads `get_time_of_day()`; monsters have no schedules at all.
- **Lairs/tribes have no home** — occupants get `home_pos` but not the `territorial` leash; tribes never appear as a camp.

## 2. The principle

> **Perform the role you already have — on screen — while the abstract nightly
> sim stays the off-screen model, and make the two agree.**

We do NOT path every villager every tick (forbidden — `production_loop.py:4-8`).
We only ever tick the **handful of actors near the player** (already gated to
`effective_visibility()*2`, `game_engine.py:314`). For *those*, we replace the
generic "move + loiter" with a **legible micro-activity**: go to a worksite,
play a fitting animation, drop an occasional beat, and (optionally) nudge the
existing economy so what you watch matches what the sim records.

**Reuse, don't rebuild:** schedules say *what* + *where*; `building_types` says
*building → profession*; `production` says *profession → workstation + recipe*;
`wildlife.json` says *diet + predator*; `tribes.json` says *the roster*. The new
layer connects them into visible action. New content is **data** (`data/*.json`).

## 3. Architecture — a shared per-turn Activity layer

New module **`engine/activities.py`** (`ActivitySystem`) + **`data/activities.json`**.

- **Activity spec (data):** `activity` or `profession` → `{worksite, anim, emote,
  beat, tick_effect}`. e.g. `smith → {worksite:"anvil", anim:"work", emote:"hammer",
  beat:"works the forge", tick_effect:{store:"+good"}}`; `pray → {worksite:"altar",
  anim:"kneel", emote:"pray"}`; `patrol → {route}`.
- **Worksite resolution:** given an NPC at its scheduled location, find the nearest
  matching furniture/terrain tile (anvil/hearth/altar/forge/farm plot — already
  placed by the furnishing pass) via a cheap local scan. Cache the assignment on
  `npc.metadata["worksite"]`.
- **Perform:** stand at (or step to) the worksite; set the emote/stance
  (`engine/anim.py` already drives `body_renderer`); every N turns emit the beat
  and apply the tick effect. Falls back to the P-round **loiter** only when no
  worksite exists (so nothing regresses).
- **Verbs:** stop flattening in `activity_to_action`; carry the activity through so
  `action_router` can dispatch `work`/`pray`/`patrol`/`perform` to the new handler.
- **Cost:** heuristic-only, nearby-only, no per-tick LLM. State on metadata (rides
  the save); the system is transient/re-derived.

This layer is reused by **Area A** (NPC professions) and **Area C** (monster/tribe
roles) — a monster "forager" is just an activity with a different worksite + anim.

---

## 4. Area A — Professions Alive (NPCs work their jobs)

Goal: a watched town shows a smith hammering, a farmer harvesting, a guard walking
a beat, a cleric praying, a bard playing — each tied to its profession + building.

- **A1 — Activity framework + data. ✅ DONE.** `engine/activities.py` +
  `data/activities.json`; perform-at-location (clip + expression + sparse `[Town]`
  beat) replacing loiter for scheduled workers; `work` refined by profession/class.
  Un-flattened `schedules.activity_to_action`; the activity rides through
  `action_data["activity"]`; `action_router._handle_move` performs on arrival.
- **A2 — Patrol routes. ✅ DONE.** `activities.patrol_step` — a guard walks the
  settlement's GATES (else a ring) via BFS `squad_tactics.path_step`, sticky.
- **A3 — Distinct verbs. ✅ MOSTLY.** Per-clip performance (A1) + worksite SPREAD
  (`_goto_worksite`/`_worksite_for` — workers fan out to a stable personal tile so
  a crowd doesn't stack on the centre) + a bard's AUDIENCE (`_draw_crowd` — nearby
  folk face the show). Remaining: farmer → harvest a ripe `FarmManager` plot (needs
  farmers routed to the FIELDS, not the village centre — a location-routing change).
- **A4 — Work feeds the economy. ✅ DONE.** A GATHERER's visible work stocks its raw
  into the settlement `store` (`_work_yield`, rate-limited + capped) — so watching a
  miner adds ore; crafters stay cosmetic (their `primary_raw` is None → the nightly
  `production_loop` turns the raws into goods, no minting from nothing).
- **A5 — Scheduleless classes. ✅ DONE.** wizard/rogue/noble/ranger/paladin/monk/
  druid/sorcerer/warlock/artificer/barbarian → archetype day-plans in
  `characters/schedules.py` (scholar/devout/wanderer/gentry/shadow). Random walk gone.
- **A6 — Fix `_handle_work`. ✅ DONE.** Gated on the worker's profession via
  `activities.profession_of`, not `klass=="merchant"`.

Fixes: `schedules.py:98-113`, `heuristic.py:168-215`, `action_router.py:378-396`.

## 5. Area B — Wildlife Ethology (animals)

Goal: animals sleep, graze toward real food/water, and move as herds — building on
the working fox/rabbit loop. Split new logic into `world/wildlife_ethology.py`
(`wildlife.py` is ~430 lines).

- **B1 — Day/night rhythm.** Read `world.get_time_of_day()`: diurnal prey bed down
  (sleep pose) at a "bed" tile at night; nocturnal species (owl/fox) go active at
  night. `data/wildlife.json` gains `active:"day"|"night"`.
- **B2 — Real grazing & thirst.** A `graze/root` animal moves toward its **diet
  terrain** (grass/forest/swamp) and **feeds** (pause + graze anim) on a hunger
  drive; seeks and drinks at **water** tiles. Replaces the 50/50 random wander.
- **B3 — Herding / flocking.** Herd species (deer) move cohesively — boids-lite
  cohesion/alignment/separation within a radius — so a herd drifts together.
- **B4 — Richer predators.** Add **wolf** (pack predator) hunting deer
  cooperatively (reuse `monster_packs`-style focus); hunger meters (not binary
  fed/starve); predators drink too; **boar charge/retaliate** when cornered
  (the data already promises it — `wildlife.json:36`).
- **B5 — Ecosystem coupling.** Predators thin herds visibly; herds seek safer
  terrain when a predator is near; ties into the existing larder/shortage hooks.

Fixes: `world/wildlife.py:199-215` (fake graze), `:195-196` (off-screen freeze),
missing day/night everywhere.

## 6. Area C — Monster & Tribe Life

Goal: a goblin warren reads as an occupied camp with sentries; a tribe appears as a
lived community with roles — reusing Area A's activity layer for monster roles.

- **C1 — Lair home behaviour.** Lair occupants get a `territorial` leash (fix: they
  don't have it) + roles: **sentries** patrol the lair perimeter, others idle/tend
  near the hoard, foragers step out and return — none wander off. `engine/lairs.py`
  (or a thin `engine/lair_life.py`) drives nearby lair occupants.
- **C2 — Monster day/night schedules.** Per-template `active:"day"|"night"` +
  `data/monster_activities.json`: nocturnal monsters sleep in the lair by day and
  hunt/patrol by night. Reuses the ActivitySystem.
- **C3 — Tribe camps (the big one).** A visible **tribe camp** `Location` near the
  player (seeded like a lair), with **role-tagged members** — a **chief** at the
  totem, **warriors** on patrol, **foragers** gathering nearby and hauling back, a
  **shaman** at a fire/totem. Camp size + composition scale with the tribe's
  `strength`; on raid nights the warriors *leave the camp* to form the raid party
  (bridging the abstract `monster_tribes` sim to a lived place). `engine/tribe_camps.py`.
- **C4 — Non-combat pack life.** A wolf / goblin pack roams, rests, and forages
  together when it isn't fighting (not just combat coordination).
- **C5 — Monsters in the ecosystem.** Predatory monsters (wolves, worgs) hunt
  wildlife (a wolf runs down a deer) — ties Areas B and C together.

Fixes: `heuristic.py:317-319` (idle random wander), `lairs.py` (no life),
`monster_tribes.py` (invisible abstract strength), `schedules.py:9` (no monster
schedules).

---

## 7. Cross-cutting

- **Animation/emote:** reuse `engine/anim.py` (`emote`/`stance`/`face`) + the large
  P34 clip library (`ui/char_clips*`, `char_mocap`) — map `work`→a hammer/chop
  clip, `pray`→kneel, `harvest`→stoop, `perform`→a dance/tune, `graze`→stoop,
  `sleep`→the lie/sleep pose. Mostly a mapping table, little new draw code.
- **Event beats:** a new `[Town]` prefix for daily-life beats (chief/forager/
  smith), observed by the topic journal + sound like the other prefixes. Keep them
  sparse (rate-limited) so the log stays readable.
- **Save state:** worksite/route/activity assignments on `metadata` (ride the save);
  tribe camps persist via `to_dict`/`from_dict` (like `lairs`), registered in
  `engine_setup` + `save_load`; add round-trip tests.
- **Validation & tests:** new `data/*.json` pass `data_validate` (add a
  `validate_activities`/`validate_world` check); each phase adds unit tests; keep
  the full suite green.
- **Performance:** nearby-only, heuristic-only, no per-tick LLM. Cache worksite
  scans. The abstract nightly sim stays as-is (it's the cheap off-screen model).

## 8. Recommended build order

1. **A1** — the activity framework (foundation reused by A + C). Biggest single
   win for the town-liveliness George has been polishing.
2. **A2–A6** — round out NPC professions (patrols, distinct verbs, economy bridge,
   scheduleless classes, work handler).
3. **B1–B5** — wildlife (self-contained, quick wins; day/night first).
4. **C1–C5** — monster & tribe life (reuses A's framework + B's ecosystem; tribe
   camps are the marquee feature).

Each letter-number is one (or a few) tested rounds. Start anywhere in this order;
A1 unblocks the most.

## 9. Constraints & non-goals

- **Content is data** — activities/roles/worksites/schedules in `data/*.json`.
- **Every file < 500 lines** — split (`activities.py`, `wildlife_ethology.py`,
  `tribe_camps.py`, `lair_life.py`).
- **No per-tick LLM; heuristic-first** — the whole system works on `--provider
  heuristic`. An LLM (if present) can *enrich* beats, never gate behaviour.
- **Don't regress movement** — the P-round continuous glide + loiter stay as the
  fallback when no activity/worksite applies.
- **Not** a full agent economy or pathfinding-heavy sim — legible *performance* of
  existing roles for nearby actors, not a global citizen simulator.
