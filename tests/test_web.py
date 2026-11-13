"""Web interface tests: every exported endpoint answers, the static build is complete, and the JS engine tests pass.

Run: python -m pytest -q tests/test_web.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.app import STATIC, STATIC_ENDPOINTS, app  # noqa: E402

client = TestClient(app)


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "static/main.js" in r.text


@pytest.mark.parametrize("path", STATIC_ENDPOINTS)
def test_endpoint(path):
    r = client.get("/api" + path)
    assert r.status_code == 200, r.text
    assert r.json() is not None


def test_static_build(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_static
    build_static.build(tmp_path / "site")
    assert (tmp_path / "site" / "index.html").read_text().count("APP_STATIC") == 1
    for path in STATIC_ENDPOINTS:
        assert (tmp_path / "site" / "api" / (path.strip("/") + ".json")).exists()


def test_static_assets_referenced_exist():
    html = (STATIC / "index.html").read_text()
    for name in ("style.css", "main.js"):
        assert f"static/{name}" in html and (STATIC / name).exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_engine():
    tests = sorted(STATIC.glob("*.test.mjs"))
    for t in tests:
        r = subprocess.run(["node", str(t)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# --- LLM-RPG specific ----------------------------------------------------------------------------------------------
import json  # noqa: E402
import os  # noqa: E402

from items.data_loader import load_data_dir, load_data_file  # noqa: E402
from web.talk import new_state, take_turn  # noqa: E402


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Tests never reach an LLM: the web app must use the offline heuristic provider."""
    monkeypatch.delenv("LLM_RPG_WEB_PROVIDER", raising=False)


def test_talk_fixture_is_current():
    """tests/fixtures/talk_fixture.json must match what the Python dialog code produces now (pure strings/ints, no
    floats, so exact equality is safe on Linux too)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_talk_fixture
    stored = json.loads(make_talk_fixture.OUT.read_text())
    assert make_talk_fixture.build() == stored, "re-run python scripts/make_talk_fixture.py"


def test_talk_api_matches_python_turns():
    state = new_state(5)
    for msg in ["", "Any news?", "/persuade lower your prices", "Tell me about Gorkash"]:
        r = client.post("/api/talk", json={"npc": "tavernkeeper_01", "message": msg, "state": state})
        assert r.status_code == 200, r.text
        got = r.json()
        want = take_turn("tavernkeeper_01", msg, state)
        assert got["reply"] == want["reply"] and got["state"] == want["state"] and got["provider"] == "heuristic"
        state = got["state"]
    assert state["turn"] == 4


def test_talk_unknown_npc_is_404():
    assert client.post("/api/talk", json={"npc": "nobody", "message": "hi"}).status_code == 404


def test_trust_unlocks_a_secret_once():
    st = new_state(1)
    st["affinity"] = {"tavernkeeper_01": 15}           # data/secrets.json: Goren's first secret needs affinity 15
    r = take_turn("tavernkeeper_01", "Good day", st)
    assert "(leaning close)" in r["reply"] and r["revealed"] == ["goren_troll_silver"]
    assert "Gorkash" in r["learned"]                   # hearing the secret teaches its topics
    r2 = take_turn("tavernkeeper_01", "Good day", r["state"])
    assert "goren_troll_silver" not in r2["reply"] and "(leaning close)" not in r2["reply"]


def test_persuasion_failure_locks_the_verb():
    st = new_state(1)
    for _ in range(30):                                # play until a /persuade fails, then it must stay locked
        r = take_turn("guard_01", "/persuade let me pass", st)
        st = r["state"]
        if "FAILED" in r["reply"]:
            break
    assert "guard_01:persuade" in st["locks"]
    assert "no mood" in take_turn("guard_01", "/persuade please", st)["reply"]


def test_catalog_counts_match_data():
    counts = client.get("/api/info").json()["counts"]
    assert counts["monsters"] == len(load_data_file("monsters.json"))
    assert counts["spells"] == len(load_data_file("spells.json"))
    assert counts["items"] == len(load_data_dir("items"))
    assert counts["adventures"] == 5


def test_adventures_have_quest_chains_and_finales():
    for adv in client.get("/api/adventures").json():
        assert adv["title"] and adv["areas"] and adv["cast"], adv["id"]
        assert len(adv["quests"]) >= 3 and adv["quests"][-1]["finale"], adv["id"]
        assert len(adv["quests"][-1]["choices"]) == 3, adv["id"]   # the branching three-way finale


def test_world_snapshot_shape():
    w = client.get("/api/world").json()
    assert len(w["terrain"]) == w["width"] * w["height"] == 240 * 170
    assert set(w["terrain"]) <= set(w["codes"].values())
    x, y = w["spawn"]
    assert 0 <= x < w["width"] and 0 <= y < w["height"]
    kinds = {p["kind"] for p in w["places"]}
    assert {"castle", "adventure", "waystone"} <= kinds
    assert w["counts"]["people"] > 100


def test_dm_library_untouched():
    """Building worlds for the web must not write the DM Legendarium into the repo."""
    assert os.environ.get("LLM_RPG_DM_LIBRARY")
    assert not (ROOT / "data" / "dm_library").exists() or not any((ROOT / "data" / "dm_library").iterdir())
