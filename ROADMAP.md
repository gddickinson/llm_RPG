# LLM-RPG — Roadmap

**The active development plan lives in [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md).**
It was produced on 2026-07-09 from a full code audit plus game-design research
(Old School RuneScape, Stardew Valley, Caves of Qud, Kenshi, and shipped
LLM-NPC games), and is being executed in small tested rounds on the
`v2-development` branch. See `SESSION_LOG.md` for the round-by-round record.

## Phase summary (details + checkboxes in DEVELOPMENT_PLAN.md)

| Phase | Theme | Status |
|---|---|---|
| P0 | Repair — make what exists real (save/load, shop, crafting, companions, weather, hunger, hints) | ~done |
| P1 | Data-driven content layer (items/quests/monsters/spells as JSON) | next |
| P2 | Progression lattice — skills, gathering, production chains, collection log, diaries | planned |
| P3 | LLM as gameplay pillar — structured dialog actions, secrets, persuasion, memory, director | planned |
| P4 | Quests & world — radiant generation, handcrafted quests, Tutorial Island, regions | planned |
| P5 | Combat & feel — enemy AI profiles, spell UI, tactical verbs, sound, day loop | planned |

## Long-term ideas (beyond the current plan)

- Module system: load campaigns from external JSON/YAML packs (P1 makes this nearly free).
- Networked multiplayer / co-op hotseat.
- Web UI: headless engine + static HTML frontend.
- 3D mode (OpenGL viewer).

## Resolved technical debt

- ~~`engine/dialog_trees.py` orphaned~~ — removed 2026-07-09 (P3 rebuilds dialog around LLM protocol).
- ~~`ui/threaded_llm_interface.py` legacy~~ — removed 2026-07-09 (no importers).
- ~~`_archive/` in the tree~~ — removed 2026-07-09 (history preserves it).
- ~~Save/load losing state~~ — fixed in save v3 (rounds 1–2).
- Remaining: `ui/terminal_ui.py` predates the new engine API; `npc_process_manager.py` lacks integration tests.
