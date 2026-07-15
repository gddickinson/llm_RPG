"""Destructible tile tests (P10.2)."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.monsters import build_monster


class TestTileDamage(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.td = self.engine.tile_damage
        self.wmap = self.engine.world.map

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _tile_of(self, terrain):
        for y in range(self.wmap.height):
            for x in range(self.wmap.width):
                if self.wmap.terrain[y][x] == terrain:
                    return (x, y)
        return None

    def test_stone_resists_fire_wood_burns(self):
        wall = self._tile_of(TerrainType.BUILDING)
        tree = self._tile_of(TerrainType.FOREST)
        self.td.damage_tile(*wall, 12, "fire")
        self.assertEqual(self.wmap.terrain[wall[1]][wall[0]],
                         TerrainType.BUILDING,
                         "12 fire barely scratches stone")
        msg = self.td.damage_tile(*tree, 12, "fire")
        self.assertIsNotNone(msg, "12 fire fells a tree")
        self.assertEqual(self.wmap.terrain[tree[1]][tree[0]],
                         TerrainType.SCORCHED,
                         "fire leaves scorched earth")

    def test_physical_felling_leaves_grass(self):
        tree = self._tile_of(TerrainType.FOREST)
        self.td.damage_tile(*tree, 25, "physical")
        self.assertEqual(self.wmap.terrain[tree[1]][tree[0]],
                         TerrainType.GRASS)

    def test_walls_crack_then_collapse(self):
        wall = self._tile_of(TerrainType.BUILDING)
        cracked = False
        for _ in range(30):
            msg = self.td.damage_tile(*wall, 10, "siege")
            if msg and "Cracks" in msg:
                cracked = True
            if self.wmap.terrain[wall[1]][wall[0]] == \
                    TerrainType.RUBBLE:
                break
        self.assertTrue(cracked, "the wall must warn before falling")
        self.assertEqual(self.wmap.terrain[wall[1]][wall[0]],
                         TerrainType.RUBBLE)

    def test_destruction_fires_tile_callbacks(self):
        seen = []
        self.wmap.register_tile_callback(
            lambda x, y, old, new: seen.append((old, new)))
        tree = self._tile_of(TerrainType.FOREST)
        self.td.damage_tile(*tree, 50, "physical")
        self.assertIn((TerrainType.FOREST, TerrainType.GRASS), seen)

    def test_indestructible_tiles_ignore_damage(self):
        road = self._tile_of(TerrainType.ROAD)
        self.assertIsNone(self.td.damage_tile(*road, 999, "siege"))
        self.assertEqual(self.wmap.terrain[road[1]][road[0]],
                         TerrainType.ROAD)

    def test_fireball_razes_the_grove(self):
        # a wolf standing in forest: the blast fells trees around it
        tree = None
        for y in range(2, self.wmap.height - 2):
            for x in range(2, self.wmap.width - 2):
                if all(self.wmap.terrain[y + dy][x + dx] ==
                       TerrainType.FOREST
                       for dx in (-1, 0, 1) for dy in (0,)):
                    tree = (x, y)
                    break
            if tree:
                break
        if tree is None:
            self.skipTest("no grove this worldgen")
        p = self.engine.player
        self.wmap.remove_character(p)
        p.position = (tree[0] - 3, tree[1])
        self.wmap.place_character(p, *p.position)
        wolf = build_monster("wolf", tree)
        wolf.hp = wolf.max_hp = 99
        self.engine.npc_manager.add_npc(wolf)
        self.wmap.place_character(wolf, *tree)
        p.metadata["spells_known"] = ["fireball"]
        p.metadata["mana"] = 40
        p.metadata["max_mana"] = 40
        msg = self.engine.cast_spell("fireball", wolf.name)
        self.assertIn("razes", msg)
        self.assertEqual(self.wmap.terrain[tree[1]][tree[0] - 1],
                         TerrainType.SCORCHED)

    def test_breach_is_a_second_door(self):
        loc = next(l for l in self.engine.world.locations
                   if "farmhouse" in l.name.lower()
                   and l.name in self.engine.interiors)
        # smash the west wall
        bx, by = loc.x, loc.y
        while self.wmap.terrain[by][bx] != TerrainType.RUBBLE:
            self.td.damage_tile(bx, by, 40, "siege")
        p = self.engine.player
        self.wmap.remove_character(p)
        p.position = (bx - 1, by)
        self.wmap.place_character(p, *p.position)
        moved = self.engine.player_actions.move(1, 0)
        self.assertTrue(moved, "the breach must admit you")
        self.assertIsNotNone(self.engine.current_interior)
        log = " ".join(str(e) for e in
                       self.engine.memory_manager.game_history[-4:])
        self.assertIn("breach", log.lower())
        self.engine.exit_building()

    def test_tile_hp_survives_save_load(self):
        import shutil
        import tempfile
        from engine.save_load import SaveManager
        wall = self._tile_of(TerrainType.BUILDING)
        self.td.damage_tile(*wall, 10, "siege")
        hp = self.td.tile_hp.get(wall)
        self.assertIsNotNone(hp)
        tmp = tempfile.mkdtemp()
        try:
            sm = SaveManager(save_dir=tmp)
            sm.save(self.engine, name="dmg")
            self.td.tile_hp = {}
            self.assertTrue(sm.load(self.engine, name="dmg"))
            self.assertEqual(
                self.engine.tile_damage.tile_hp.get(wall), hp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
