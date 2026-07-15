"""P39.6 — decoration is applied EVERYWHERE (settlements + the adventure crypt).

Locks in the P39.2/P39.3 theme + furnishing machinery reaching every enterable
interior: each settlement building is furnished in its kind's theme, and the
Sunken Tome's Drowned Vault is a proper dark crypt (sarcophagi, braziers, urns,
cobwebs, bones). Guards against a future change that quietly stops furnishing a
building kind or the structure levels.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import tempfile
os.environ.setdefault("LLM_RPG_DM_LIBRARY",
                      tempfile.mkdtemp(prefix="llmrpg_decor_"))

import unittest

from engine.game_engine import GameEngine
from world import furnishings


# a signature prop that MUST appear for each furnish theme
THEME_SIGNATURE = {
    "tavern": {"Table", "Bench", "Barrel", "Hearth"},
    "smithy": {"Anvil", "Weapon Rack"},
    "temple": {"Altar", "Pillar", "Pew"},
    "tomb": {"Sarcophagus", "Brazier", "Bones"},
}


class TestSettlementDecoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(llm_provider="heuristic",
                                enable_npc_processes=False)
        cls.engine.start_game()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.end_game()
        except Exception:
            pass

    def test_every_interior_is_furnished(self):
        interiors = self.engine.interiors
        self.assertGreater(len(interiors), 0)
        for name, inter in interiors.items():
            fur = getattr(inter, "furniture", []) or []
            self.assertTrue(fur, f"{name} should be furnished, not bare")

    def test_building_kinds_get_their_theme_signature(self):
        # Find one interior per themed kind and check it carries a signature
        # prop of its theme (proves the theme actually drove the furnishing).
        by_theme = {}
        for name, inter in self.engine.interiors.items():
            th = furnishings.theme_of(name)
            by_theme.setdefault(th, []).append(inter)
        for theme, signature in THEME_SIGNATURE.items():
            if theme == "tomb":
                continue                       # the crypt is its own test
            inters = by_theme.get(theme)
            if not inters:
                continue                       # this world may lack the kind
            hit = False
            for inter in inters:
                props = {f["name"] for f in (inter.furniture or [])}
                if props & signature:
                    hit = True
                    break
            self.assertTrue(
                hit, f"a {theme} interior should show one of {signature}")


class TestCryptDecoration(unittest.TestCase):
    def test_the_drowned_vault_is_a_furnished_crypt(self):
        from world.structures import StructureBuilder, STRUCTURES
        eng = GameEngine(llm_provider="heuristic", enable_npc_processes=False)
        eng.start_game()
        try:
            spec = STRUCTURES["drowned_vault"]
            sb = StructureBuilder(eng)
            for lv in spec["levels"]:
                name = lv.get("name", "drowned_vault")
                self.assertEqual(
                    furnishings.theme_of(name), "tomb",
                    f"{name} should read as a crypt")
                inter = sb._build_level(lv, "drowned_vault")
                props = {f["name"] for f in (inter.furniture or [])}
                self.assertTrue(
                    props & THEME_SIGNATURE["tomb"],
                    f"{name} should be furnished with crypt props, got {props}")
        finally:
            eng.end_game()


if __name__ == "__main__":
    unittest.main()
