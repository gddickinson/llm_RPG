# GAME_REVIEW.md — how to further improve llm_RPG (2026-07-18)

An extensive codebase review (5 parallel review passes: gameplay depth, UX/onboarding,
content/balance, world-simulation, incomplete-systems/tech-debt). This is the
synthesized, prioritized roadmap.

## The one-paragraph diagnosis

llm_RPG is an **extraordinarily deep engine starved of tuned content and
disconnected at three seams**. The systems breadth is world-class (combat depth,
wounds/infection, factions/agendas/diplomacy, ambitions, romance, wildlife ecology,
tribes, nemesis, production/market, an away-hero AI). But three gaps hold the
*experience* well below the *engine*:
1. **Progression is mathematically broken** — the XP curve was over-corrected and no
   longer connects to any reward source.
2. **The rich simulation is invisible and siloed** — it churns as grey log text; NPCs
   don't know about it, the player can't see or act on it, and several systems
   compute state that is consumed by nothing.
3. **The front door is weak** — a new player gets no default onboarding and faces
   ~60 keys and dozens of undiscoverable systems.

The highest-leverage fixes are **connective and tuning**, not more systems.

## TIER 0 — Broken / hard-rule violations (do first; small effort)

- **T0.1 · Fix the XP curve. [verified]** `engine/leveling.py` `XP_CURVE_COEFF=1500` →
  L2=3,000 · L5=30,000 · L20=570,000. The ENTIRE 35-quest authored questbook awards
  **10,025 XP total = barely level 2**; a kill pays `25+15·level` (~40 XP). The
  campaign finale is a **190-HP L12/L16 dragon** — unreachable without thousands of
  kills. The P37.6 "10× steeper" change (meant to slow leveling) severed the curve
  from every reward. Re-tune `XP_CURVE_COEFF` to ~150–300 (or raise the three award
  sites 3–5×) so the authored questline lands the hero near the finale level.
  Sites: `engine/leveling.py:32`, `engine/combat_system._award_xp`, `quests/radiant.py`.
  *Effort S (tune) / M (re-balance + playtest the whole economy).*
- **T0.2 · Green the tree.** `test_tactics.test_shove_pushes_enemy_back` is a
  procedural-worldgen flake (an obstruction lands behind the shove target → the
  "blocked" branch, no stagger). Same class as the cleave/workers flakes — pin the
  target's landing tile. *Effort S.*
- **T0.3 · 500-line violations.** `ui/body_renderer.py` 587, `engine/combat_system.py`
  553, `engine/game_engine.py` 506, `ui/input_handler.py` 502 exceed the project's
  hard limit; `renderer.py`/`gui.py`/`action_router.py`/`iso_render.py` are at the
  edge. Split (the codebase already does this heavily). *Effort S–M.*

## TIER 1 — Make progression FEEL good (the power fantasy)

- **T1.1 · Gear depth.** The "power from gear not levels" bargain was never built:
  **6 armor pieces (leather+2 → chain+4 → plate+6), 0 epic items, 3 legendaries (all
  quest-locked)**, 18 weapons (top dmg 8). Add an epic/legendary ceiling + more armor
  rungs (`data/items/weapons.json`/`armor.json`), procedural affixes + **level-scaled
  loot** keyed on foe level/depth (`items/loot_tables.py`), boss `loot_table` blocks.
  *Effort M–L.*
- **T1.2 · Build agency — level-up perks/feats.** Level-ups are a deterministic
  `+5 HP` + 2 fixed stats; two warriors are identical, no feats/talents/respec. Add a
  `data/perks.json` + `engine/perks.py`, a level-up choice overlay, perks that
  gate/upgrade the existing combat verbs. Fewer, meaningful levels each with a choice.
  `engine/leveling.py`. *Effort M.*
- **T1.3 · Fill the monster roster.** Wilderness pool = **7 monsters**; water/desert
  tables empty; an L7–11 dead zone then a jump to the dragons. Add ~15–20 templates
  (mid-tier L5–14, biome-tagged) in `data/monsters.json`; elites only *rescale* the
  same 7 silhouettes today. Pure data. *Effort M.*

## TIER 2 — Make the world VISIBLE & consequential (the living-world payoff)

- **T2.1 · NPCs ingest world events. [biggest sim lever]** The only observers on the
  event log are the topic-journal + chronicle; NPC memories come *only* from direct
  events, so the villager beside you has no idea a war broke out or a shortage hit.
  Add a memory-manager observer feeding relevant `[Realm]`/`[Town]`/`[Legend]` beats
  into nearby/relevant NPCs' memory → dialog + `gossip.py` + nightly reflection surface
  them. Near-zero content, turns a silent town reactive. *Effort M.*
- **T2.2 · Factions matter on the ground.** `faction_agendas.at_war/agenda_of/relation`
  is computed, persisted, announced — and **consumed by nothing**. Wars → visible
  mixed-faction skirmishes (reuse `npc_conflict`), tense/guarded roads; alliances →
  warmer greetings/cheaper trade; expand/dominate → a new patrol/camp. *Effort M–L.*
- **T2.3 · Surface the sim + turn it into hooks.** No telegraph exists for a nemesis
  return or a tribe massing on your town. Add a pullable "State of the Realm" digest
  (extend the Y-journal / a panel) + hint-bar/map cues for the big beats, and widen
  `quests/radiant.py` to mint bounties/rivalries from `nemesis`/`social_graph`/
  `monster_tribes`/`faction_ticker` state. Make the sim *actionable*. *Effort M.*
- **T2.4 · Close the economy loop.** Stores only fill (crafters + raids drain them),
  so every settlement sits at cap and the elegant shortage→price→radiant-quest chain
  rarely fires from real pressure. Add nightly **consumption** (folk eat, guards use
  arms) → organic scarcity. `engine/production_loop.py` + `market.py`. *Effort M.*
- **T2.5 · Realised ambitions change the world.** `prospered`/`master`/`avenged`/… flags
  are read **nowhere** — a "master crafter" is identical to any villager. Hook 2–3 into
  shop tier / bond-lesson / dialog title. *Effort M.*

## TIER 3 — Fix the front door (approachability)

- **T3.1 · Default onboarding.** "Quick Start" (first, default-highlighted) drops a
  cold player into a 60-key game with an empty quest log; Tutorial Island is opt-in
  and only teaches ~6 things (and drills `[Z] fish`, a special-case). Make a guided
  path the default; expand the tutorial to the real loop — panels, **talk→accept a
  quest**, attack/target, equip, the hint bar. `ui/start_menu.py`, `engine/tutorial.py`.
  *Effort S–M.*
- **T3.2 · Surface & track the main quest. [flagged by 2 lenses]** The 5-act spine
  (`engine/campaign.py`) is completely un-surfaced — you must physically find
  `tower_wizard_01` to learn it exists, and the HUD shows only 3 active quests with no
  giver/waypoint/main-vs-side. Pin the `metadata["main"]` quest in the HUD with a
  direction, an opening nudge, a starting "lead". `ui/hud.py`, `ui/hints.py`,
  `engine/demo_setup.py`. *Effort S–M.*
- **T3.3 · Reveal hidden verbs.** Pull combat verbs (Trip/Feint/Demoralize/Grapple…
  behind SHIFT-chords, starved by the 3-slot hint cap) and the 9 dialog slash-commands
  into visible, context-gated menus (extend `engine/conversation.menu`). Raise the
  hint cap in combat. `ui/hints.py`, `engine/conversation.py`, `ui/dialog_menu.py`.
  *Effort M.*

## TIER 4 — Finish half-built features & deepen replay

- **T4.1 · Away-hero enters buildings.** The plan's own "KEY cross-cutting gap": the
  away/agent hero skirts buildings, so a whole cluster of *shipped* autoplay features
  (inn-rest, indoor merchants, crafting, claim/repair a home) is **dormant**. One nav
  step lights them all. `engine/agent_nav.py`. *Effort M.*
- **T4.2 · Rival companies compete & die.** The "other heroes" roam/fight/loot but
  never take quests, clear dungeons, or lose renown; a wiped company doesn't die. Add
  a real win-ledger + fortune arc. `engine/adventurers.py`, `companies.py`. *Effort L.*
- **T4.3 · Endgame payoff + NG+.** Winning the campaign fires one `[Legend]` line. Add
  a victory screen + a New Game+ (carry gear, tougher world, new apex). `engine/campaign.py`,
  `ui/`, `engine/save_load.py`. *Effort M–L.*
- **T4.4 · Skills feed combat power.** The 12-skill lattice gates only gathering/
  traversal — no path from "L40 smith" to "stronger in a fight". Tie smithing→gear,
  alchemy→potions, cooking→buffs; add a martial skill. *Effort M.*
- **T4.5 · More quests** — repeatable + branching (0 repeatable, 2 branching today;
  the `excludes`/`reward_choices`/`sets_flag` machinery already exists). *Effort M–L.*

## Tech hygiene (ongoing)

- Per-turn error-swallowing logs at DEBUG (invisible) — a broken subsystem fails
  silently all session. Raise to WARNING or add a `--strict` re-raise mode.
- **96 `skipTest` markers** are conditional on random world contents — a skip reads as
  a pass, so regressions hide behind seeds (and T0.2 shows one can flip to a hard
  fail). Seed worldgen deterministically in tests / build fixture worlds.
- Doc drift: `SAVE_VERSION` comment lists 5 additions for ~40 serialized subsystems;
  CLAUDE.md says "650+" tests, INTERFACE.md "290+", actual ~3269.

## What's already healthy (leave alone)

Economy is exploit-free (sell=value//2, buy×index both move, gold-capped, transmute
is a sink). LLM integration is robust (graceful fallback, defensive parsing, budget
discipline, fully playable on `heuristic`). Save/load is complete (43 to_dict/from_dict
registered + metadata-ride). No core stubs / bare excepts. Combat *systems* are
excellent — they're just starved of content, which is why the content/curve fixes
(T0.1, T1.x) are the highest-leverage of all.

## If you do only three things
**T0.1 (fix the XP curve)** → **T1.1/T1.2 (gear + perks make the newly-meaningful
levels rich)** → **T2.1/T2.3 (NPCs know + the player sees the simulation)**. That
converts "impressively deep but inert and invisible" into "deep and *felt*."
