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

### Coming next (Bundle B + C)

- **Bundle B (World breadth)**: chunked / larger world, second settlement, procedural dungeons under cave tiles, weather, foraging from forest tiles.
- **Bundle C (NPC richness)**: schedule-driven movement that actually walks NPCs to their target locations, NPC families, gossip in dialog, multi-year history sim.

