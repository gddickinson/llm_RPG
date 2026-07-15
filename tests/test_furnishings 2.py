"""P39.3 — themed furnishing (decorate an interior with theme props)."""

import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import unittest

from world.furnishings import furnish, theme_of
from world.interiors import Interior
from world.world_map import TerrainType as T


def _room(name, w=11, h=9):
    inter = Interior(name=name, width=w, height=h)
    inter.init_grid()
    return inter


def _names(inter):
    return {f["name"].lower() for f in inter.furniture}


class TestThemeOf(unittest.TestCase):
    def test_matches_the_renderer_keywords(self):
        self.assertEqual(theme_of("Drowned Vault — Sanctum"), "tomb")
        self.assertEqual(theme_of("Temple of Light"), "temple")
        self.assertEqual(theme_of("Durgan's Forge"), "smithy")
        self.assertEqual(theme_of("A Plain Cottage"), "home")


class TestFurnish(unittest.TestCase):
    def test_a_crypt_gets_crypt_props(self):
        inter = _room("The Sunken Crypt")
        added = furnish(inter, inter.name)
        self.assertGreater(added, 0)
        names = _names(inter)
        self.assertTrue({"sarcophagus", "brazier"} & names,
                        "a tomb should have sarcophagi / braziers")
        self.assertTrue({"bones", "cobweb", "urn"} & names)

    def test_a_smithy_gets_a_forge(self):
        inter = _room("Durgan's Forge")
        furnish(inter, inter.name)
        self.assertIn("anvil", _names(inter))

    def test_props_land_on_free_floor_only(self):
        inter = _room("Temple of Light")
        furnish(inter, inter.name)
        for f in inter.furniture:
            x, y = f["x"], f["y"]
            self.assertNotEqual(inter.terrain[y][x], T.BUILDING,
                                f"{f['name']} on a wall")
            self.assertNotEqual((x, y), tuple(inter.door),
                                "prop blocks the door")

    def test_no_two_props_share_a_tile(self):
        inter = _room("Ancient Tomb")
        furnish(inter, inter.name)
        spots = [(f["x"], f["y"]) for f in inter.furniture]
        self.assertEqual(len(spots), len(set(spots)))

    def test_functional_pieces_are_not_doubled(self):
        inter = _room("Temple of Light")
        inter.furniture.append({"name": "Altar", "x": 3, "y": 3})
        furnish(inter, inter.name)
        altars = [f for f in inter.furniture if f["name"].lower() == "altar"]
        self.assertEqual(len(altars), 1, "the existing altar stays single")

    def test_does_not_overcrowd(self):
        inter = _room("Crypt", w=7, h=6)
        furnish(inter, inter.name)
        floor = sum(1 for y in range(1, inter.height - 1)
                    for x in range(1, inter.width - 1)
                    if inter.terrain[y][x] != T.BUILDING)
        props = len(inter.furniture)
        self.assertLessEqual(props, floor)

    def test_deterministic(self):
        a, b = _room("Vault A"), _room("Vault A")
        furnish(a, a.name)
        furnish(b, b.name)
        self.assertEqual([(f["name"], f["x"], f["y"]) for f in a.furniture],
                         [(f["name"], f["x"], f["y"]) for f in b.furniture])


if __name__ == "__main__":
    unittest.main()
