# Adventure Design — "The Sunken Tome of Vael'Zhur" (Phase 38)

A substantial, themed campaign module (George's request, 2026-07-14). Built as a
`data/module_packs/` campaign pack (installed at new-game start via the P1.4 pipeline)
plus any small engine support. This doc is the PLAN; P38.1–P38.4 build it.

## Premise & theme

Centuries ago the archmage **Vael'Zhur** bound his soul into his magnum opus — the
**Sunken Tome** — and sank his tower-library beneath the Mirefen marsh to escape death
and rivals. The binding kept him "alive" as a **lich**, his phylactery the Tome itself.
Now the drowning-wards are failing; the Tome's whisper draws seekers across the marsh.
Rival powers converge. The player is pulled in — and must decide what becomes of the Tome.

Tone: eerie drowned-library dark-fantasy; investigation → exploration → confrontation,
with **many ways to solve it** (seal / destroy / claim / parley).

## Areas (visit-able places)

1. **Mirefen Village** — start hub. Fisherfolk, the scholar **Sage Ondrel** (legend +
   clue 1), the quest board, both patron factions recruiting. (Settlement + NPCs.)
2. **Lanternhall** (in/near Mirefen) — the **Lantern Wardens**, a scholarly order that
   wants the Tome SEALED, not used. The player's lawful patron. (Building + NPCs.)
3. **The Ashen Camp** — the **Cinder Circle**, a fire-cult war-band seeking to unbind the
   Tome's fire-magic. Hostile faction camp (spawn cluster + a captain). Alt dark patron.
4. **Thornwatch Ruins** — a drowned monastery holding **Warding-Key fragment I** behind a
   sigil-ward puzzle; guarded by grave-touched undead. (Structure w/ puzzle.)
5. **The Reedmarsh Warren** — the **Bog Goblin** tribe (P19.4 tribe); holds **fragment II**.
   Fight through, or win passage via Ysolde. (Tribe + lair.)
6. **Ysolde's Hollow** — the neutral **Marsh-Witch** Ysolde: a wild card who trades
   **fragment III** + safe passage for a favor, or becomes an enemy. (NPC + hut.)
7. **The Drowned Vault** — Vael'Zhur's sunken tower-library: a multi-level flooded
   STRUCTURE with ward-puzzles (booby traps), guardian constructs, dark levels needing
   the Drowned Lantern, and the deepest **Sanctum** where the lich and the Tome wait.

## Factions & competing parties

- **Lantern Wardens** (lawful, ally-able) — seal the Tome. Patron path A.
- **Cinder Circle** (fire-cult, hostile/ally-able) — claim its power. Patron path B.
- **Bog Goblin tribe** (Reedmarsh) — territorial; fight or parley.
- **Marsh-Witch Ysolde** (neutral) — favor-for-favor wild card.
- **A rival adventuring company** (P-M.6b `companies`) racing you to the Vault — a
  recurring competing party (Act 3 confrontation).

## The lich — Vael'Zhur (boss, P15.6 boss block)

A drowned-robed lich in the Sanctum. Boss block:
- Telegraphed **necrotic/ice AoE** (mark a tile → blast); a **summon** phase (drowned
  guardians) at 66% HP; a **terror** phase (P19.1 Frighten) at 33% HP.
- His phylactery is the **Tome**. He cannot truly die while it endures — the ending
  branches on what you do with it (see solve-paths).

## Artifacts & magic items

- **The Sunken Tome of Vael'Zhur** (legendary; the objective). Reading it grants a
  powerful spell but risks a corruption curse — a real choice.
- **Warding-Key fragments I/II/III** (collectibles; assembled = the **Warding Key** that
  binds the lich / opens the Sanctum safely). The clue-and-collect spine.
- **The Drowned Lantern** (lights the Vault's dark flooded levels — traversal gate).
- **Tidecaller's Signet** (water-walking + long breath — traverse flooded halls).
- Ancient spell-scrolls (frost, warding), a guardian's **Runed Halberd**, potions.

## Clues (investigation)

Journal/topic/secret fragments from Sage Ondrel, the Thornwatch inscriptions, Ysolde,
and defeated Cinder Circle scouts reveal: the Vault's location, the ward sequence
(the sigil-puzzle order), and the lich's binding weakness. Clues gate/short-circuit
puzzles and open dialogue options.

## Quest chain (acts) — quest metadata drives branching (P21.1)

- **Act 1 — The Whisper**: reach Mirefen, learn the legend from Ondrel (clue 1). CHOOSE a
  patron: Wardens (`sets_flag: patron_warden`, `excludes` the Cinder quest) or Cinder
  Circle (`sets_flag: patron_cinder`). Branch begins.
- **Act 2 — The Scattered Keys**: three sub-quests for the fragments — Thornwatch (undead +
  sigil puzzle), the Warren (tribe fight OR Ysolde-parley `blocked_by_flag`), Ysolde's
  favor. Each solvable multiple ways.
- **Act 3 — The Rival**: the rival company / Cinder Circle races you; a confrontation
  (fight or outpace). `sets_flag` on outcome.
- **Act 4 — The Drowned Vault**: descend the flooded library; the Drowned Lantern + Signet
  gate traversal; solve the ward-puzzles (booby traps) to reach the Sanctum.
- **Act 5 — Vael'Zhur**: the lich fight + the chosen **ending** via `reward_choices`:
  - **Seal** (Wardens): with the assembled Warding Key, re-bind the lich and seal the
    Vault — a `[Legend]` triumphant ending; the Tome is lost but safe.
  - **Destroy**: shatter the Tome/phylactery → the lich crumbles; raw but clean.
  - **Claim**: take the Tome (or hand it to the Cinder Circle) → power + a corruption
    curse / faction fallout — a darker `[Legend]`.

## Win conditions (what the P38.4 test completes)

Reach the Vault, defeat/bind Vael'Zhur, resolve the Tome — via at least the **Seal** and
**Destroy** paths in a scripted heuristic playthrough (drive the player through the acts,
asserting each objective flips and the finale `[Legend]` fires).

## Engine mapping (what's data vs needs support)

| Need | Mechanism | Status |
|---|---|---|
| Areas: villages/camps/ruins | pack `structures` + Location markers + spawn clusters | supported (P14.2b) |
| The Drowned Vault dungeon | pack `structure` (grid levels, dark levels, puzzle wards) | supported (P9.1/P21.3) |
| Booby-trap wards | structure puzzles: `pull_lever`/`touch_sigil`/`offer_at_altar` + hazard surfaces | supported (P21.3/P10.3) |
| The lich | monster `boss` block (telegraph/phases/terror) | supported (P15.6/P19.1) |
| Tribes / factions | `data/tribes.json` (Bog Goblins) + `factions` + `companies` rival party | supported (P19.4/M.6b) |
| Magic items / artifacts | pack `items` with use-effects; legendary Tome | supported |
| Clue investigation | topics / secrets / quest text | supported |
| Branching acts & endings | quest metadata: prereq/sets/excludes/reward_choices | supported (P21.1) |
| Custom NPCs (Ondrel, Ysolde…) | VERIFY pack NPC support; else add via `data/npcs/` + seed | **verify in P38.2** |
| Multi-area coherent placement | pack anchors place in the procedural world; a themed sub-region may need a light seeder | **verify in P38.2** |

## Build order

- **P38.1** — monsters (grave-touched, drowned guardian, Cinder cultist/captain, Bog
  Goblins, the lich boss) + tribe + magic items/artifacts. Validator green.
- **P38.2** — areas: the Drowned Vault structure (grid levels + ward puzzles + dark
  levels) + camp/ruin/hut Location markers + the custom NPCs (Ondrel, Ysolde, Warden,
  Cinder captain). Resolve the NPC/placement questions above.
- **P38.3** — the quest chain + clues + branching solve-paths + assemble the module pack
  JSON; install-at-start + announcement + beats.
- **P38.4** — deep integration tests: pack installs cleanly; each act's objective flips;
  a scripted heuristic playthrough completes the Seal and Destroy endings; the finale
  `[Legend]` fires. Plus a broad "all systems still green" sweep.

## Guardrails

- Content-as-data (JSON) per the hard rules; no re-hardcoding. Validator + charter caps.
- Respect the P37.5 slower-XP / harder-combat balance — tune foe levels so the arc is a
  real challenge but winnable with gear + a companion or two.
- Keep every source file < 500 lines; any new engine helper is small and tested.
