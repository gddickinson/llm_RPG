"""Generic JSON data-file loading for game content.

Content lives in `data/<subdir>/*.json`. Each file holds a dict keyed by
content id. `load_data_dir("items")` merges every file in `data/items/`
into one dict, erroring on duplicate ids across files.

This is the foundation of the data-driven content layer (Phase 1):
adding content means editing JSON, not Python.
"""

import json
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger("llm_rpg.data_loader")

# File-sync services (iCloud / Dropbox / OneDrive) drop conflict COPIES beside
# the real file — "monsters 2.json", "quests copy.json". They carry the same
# content ids, so globbing them in used to crash the loader (duplicate id).
# Skip them defensively so a stray sync copy never breaks the game.
_SYNC_DUP = re.compile(r" (?:\d+|[Cc]opy(?: \d+)?)$")

# Repo root is one level above this package
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data")


class DataError(Exception):
    """A content data file is malformed."""


def load_data_dir(subdir: str, root: str = None) -> Dict[str, Any]:
    """Merge all *.json dicts under data/<subdir>/ into one dict."""
    path = os.path.join(root or DATA_ROOT, subdir)
    merged: Dict[str, Any] = {}
    if not os.path.isdir(path):
        raise DataError(f"Missing data directory: {path}")
    for fname in sorted(os.listdir(path)):
        if not fname.endswith(".json"):
            continue
        if _SYNC_DUP.search(fname[:-5]):     # a sync-conflict copy — ignore it
            logger.warning("Skipping likely sync-conflict duplicate: %s/%s",
                           subdir, fname)
            continue
        fpath = os.path.join(path, fname)
        try:
            with open(fpath, "r") as fp:
                data = json.load(fp)
        except json.JSONDecodeError as e:
            raise DataError(f"Invalid JSON in {fpath}: {e}") from e
        if not isinstance(data, dict):
            raise DataError(f"{fpath} must contain a JSON object "
                            f"keyed by content id")
        for key, entry in data.items():
            if key in merged:
                raise DataError(
                    f"Duplicate content id '{key}' (again in {fname})")
            merged[key] = entry
    return merged


def load_data_file(relpath: str, root: str = None) -> Any:
    """Load a single data/<relpath> JSON file."""
    fpath = os.path.join(root or DATA_ROOT, relpath)
    try:
        with open(fpath, "r") as fp:
            return json.load(fp)
    except FileNotFoundError:
        raise DataError(f"Missing data file: {fpath}")
    except json.JSONDecodeError as e:
        raise DataError(f"Invalid JSON in {fpath}: {e}") from e
