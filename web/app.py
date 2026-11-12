"""FastAPI web app for LLM-RPG: serves the front end in static/ and the JSON API under /api.

Run with `python run_web.py` (http://127.0.0.1:8200, local only). `scripts/build_static.py` exports every path in
STATIC_ENDPOINTS to JSON for the GitHub Pages site, so keep that list in step with the GET routes below.

NPC talk uses the game's offline heuristic provider by default (no network, no keys). Like the game's own
`--provider` flag, setting LLM_RPG_WEB_PROVIDER=ollama|anthropic|openai (and LLM_RPG_WEB_MODEL) before starting the
local server lets that provider speak the NPC's line instead; any keys stay in the server's environment. Tests and the
static build never set it.
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web import catalog
from web.talk import take_turn, talk_data
from web.world_export import DEFAULT_SEED, world_snapshot

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="LLM-RPG")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    """Project summary and real content counts for the home page."""
    return catalog.info()


@app.get("/api/monsters")
def monsters():
    return catalog.monsters()


@app.get("/api/spells")
def spells():
    return catalog.spells()


@app.get("/api/items")
def items():
    return catalog.items()


@app.get("/api/recipes")
def recipes():
    return catalog.recipes()


@app.get("/api/adventures")
def adventures():
    return catalog.adventures()


@app.get("/api/talk/data")
def talk_static_data():
    """NPCs, topics, secrets and the heuristic provider's lines (what talk_engine.js needs)."""
    return talk_data()


def _provider_name() -> str:
    return os.environ.get("LLM_RPG_WEB_PROVIDER", "heuristic").strip().lower() or "heuristic"


@app.get("/api/talk/mode")
def talk_mode():
    return {"provider": _provider_name()}


class TalkIn(BaseModel):
    npc: str
    message: str = ""
    state: dict = {}


@app.post("/api/talk")
def talk(body: TalkIn):
    """One conversation turn (stateless: the state comes in and goes back out)."""
    provider = None
    name = _provider_name()
    if name != "heuristic":
        from llm.providers import get_provider
        model = os.environ.get("LLM_RPG_WEB_MODEL")
        provider = get_provider(name, **({"model": model} if model else {}))
    try:
        out = take_turn(body.npc, body.message[:500], body.state, provider=provider)
    except KeyError:
        raise HTTPException(404, f"No NPC {body.npc}")
    out["provider"] = getattr(provider, "name", "heuristic")
    return out


@app.get("/api/world")
def world():
    """The default world snapshot (seed 7), exported to the static site."""
    return world_snapshot(DEFAULT_SEED)


@app.get("/api/world/{seed}")
def world_seed(seed: int):
    """A freshly generated world for another seed (local app only; ~10 s the first time)."""
    if not 0 <= seed < 1_000_000:
        raise HTTPException(400, "seed must be 0..999999")
    return world_snapshot(seed)


# GET paths (without the /api prefix) written to the static site as api/<path>.json.
STATIC_ENDPOINTS = ["/info", "/monsters", "/spells", "/items", "/recipes", "/adventures", "/talk/data", "/world"]
