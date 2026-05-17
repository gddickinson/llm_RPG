# LLM-RPG — Roadmap

## Current state (2026-05-17)

The codebase was overhauled in a single session to be a fully-functional,
locally-runnable game with optional LLM backends. Key additions:

- LLM provider abstraction (`llm/providers/`) with heuristic fallback
- Real items system (`items/`) and loot tables
- Quest system (`quests/`) — kill / fetch / talk / explore / deliver / survive
- Save / load (`engine/save_load.py`) — JSON
- Skills (`engine/skills.py`) — D&D-style checks
- Refactored 1566-LOC `game_engine.py` into 8 focused modules
- Refactored 1104-LOC `gui.py` into renderer + sprite loader + HUD + input
- Procedural world generation with biomes and named locations
- Procedural sprite rendering (no PNG assets)
- 44-test suite covering items, quests, save/load, combat, world gen, skills, engine

All source files now under 500 lines. INTERFACE.md and SESSION_LOG.md created.

## Short-term Improvements

- [ ] **Quest UI**: Click-to-accept available quests at NPCs that offer them.
- [ ] **Inventory equipping**: Currently weapons/armor are auto-summed; add equip slots.
- [ ] **Level-up**: Convert XP to level/HP/stat increases.
- [ ] **More NPC variety**: Random NPC spawns in towns + wandering monsters.
- [ ] **Skill-gated dialog**: PERSUASION / INTIMIDATION checks in conversations.
- [ ] **Crafting**: Use INGREDIENT items at the forge to produce weapons.
- [ ] **Mouse input**: Click to move / click on NPC to interact.
- [ ] **Sound**: pygame.mixer-based ambient + combat SFX.
- [ ] **Tiled minimap**: Show explored vs unexplored.

## Feature Enhancements

- [ ] **Larger world**: Multiple regions (forest, desert, mountains) connected by roads.
- [ ] **Dungeons**: BSP / cellular-automata dungeons (concepts from autonomous_world).
- [ ] **Day/night gameplay**: Monster spawns at night, NPCs return home.
- [ ] **Faction system**: NPCs grouped by allegiance affecting combat AI.
- [ ] **Persistent NPC schedules**: Each NPC has a daily routine.
- [ ] **Animated sprites**: Per-frame animation in `sprite_loader.py`.
- [ ] **Better worldgen**: Perlin/simplex noise via numpy.
- [ ] **Localization**: Strings out of code into a JSON.
- [ ] **Speech-to-text**: Dictate dialog with the player's voice (e.g. via Whisper).

## Long-term Vision

- [ ] **Module system**: Load campaigns from external JSON/YAML packs.
- [ ] **Co-op**: Local hotseat multiplayer.
- [ ] **Networked multiplayer**: Stretch goal — port the FastAPI server from llm_RPG_2.
- [ ] **3D mode**: OpenGL viewer inspired by autonomous_world's renderer_3d.
- [ ] **Web UI**: Headless engine + static HTML frontend.
- [ ] **LLM-driven world events**: Random events generated nightly by the LLM.

## Technical Debt

- [ ] `characters/npc_manager.py` is at 499 LOC — split presets into a data file.
- [ ] `ui/terminal_ui.py` predates the new engine API — rewrite to use modular subsystems.
- [ ] `engine/npc_process_manager.py` is intricate — write integration tests against it.
- [ ] `ui/threaded_llm_interface.py` is legacy — confirm and remove if unused.
- [ ] Properly support pygame_gui (currently imported via legacy code only).
- [ ] `_archive/` should be moved to a separate branch or deleted before release.
