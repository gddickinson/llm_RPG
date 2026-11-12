"""Start the LLM-RPG web app on http://127.0.0.1:8200 (local only).

Run: python run_web.py   (needs: pip install -r requirements-web.txt)
NPC talk is offline by default; LLM_RPG_WEB_PROVIDER=ollama (etc.) opts in to an LLM, as `main.py --provider` does.
"""
import os
import tempfile

import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("LLM_RPG_DM_LIBRARY", tempfile.mkdtemp(prefix="llmrpg_lib_"))
    uvicorn.run("web.app:app", host="127.0.0.1", port=8200)
