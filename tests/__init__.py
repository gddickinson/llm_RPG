"""Test package — force SDL dummy drivers and an isolated DM library
before any game import (the Legendarium persists across engines by
design; tests must not write to the real data/dm_library)."""
import atexit
import os
import shutil
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_dm_lib = tempfile.mkdtemp(prefix="llm_rpg_test_dm_lib_")
os.environ["LLM_RPG_DM_LIBRARY"] = _dm_lib
atexit.register(shutil.rmtree, _dm_lib, ignore_errors=True)

# Empty module-pack folder by default so the ~650 engine boots across the
# suite don't each install the shipped packs; pack tests point the env at
# their own fixtures (restore it afterwards, never pop).
_packs = tempfile.mkdtemp(prefix="llm_rpg_test_packs_")
os.environ["LLM_RPG_MODULE_PACKS"] = _packs
atexit.register(shutil.rmtree, _packs, ignore_errors=True)


def clean_dm_library():
    """Wipe the per-run DM library (tests that define ids call this in
    setUp — the Legendarium intentionally persists across engines)."""
    import glob
    for path in glob.glob(os.path.join(_dm_lib, "*.json")):
        try:
            os.remove(path)
        except OSError:
            pass
