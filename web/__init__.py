"""Web interface for LLM-RPG (FastAPI app + plain ES-module front end; also exported as a static GitHub Pages site).

Contents:
- app.py           FastAPI routes under /api and STATIC_ENDPOINTS (exported by scripts/build_static.py)
- catalog.py       read-only content views: bestiary, spellbook, items + recipes, the five authored adventures
- talk.py          one NPC conversation turn through the game's heuristic dialog, topics, secrets and persuasion code
- world_export.py  a snapshot of a generated game world (terrain, places, people) from a headless GameEngine
- static/          the front end (talk_engine.js is the JS port of talk.py, checked by talk_engine.test.mjs)
"""
