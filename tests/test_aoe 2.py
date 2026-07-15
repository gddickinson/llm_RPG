"""P10.0 infra + P10.1 AoE damage tests."""

import unittest

from engine.game_engine import GameEngine
from world.world_map import TerrainType
from world.monsters import build_monster


class TestTileInfra(unittest.TestCase):
    def test_set_terrain_fires_callbacks(self):
        from world.world_map import WorldMap
        wmap = WorldMap(10, 10)
        seen = []
        wmap.register_tile_callback(
            lambda x, y, old, new: seen.append((x, y, old, new)))
        changed = wmap.set_terrain(3, 4, TerrainType.RUBBLE)
        self.assertTrue(changed)
        self.assertEqual(seen, [(3, 4, TerrainType.GRASS,
                                 TerrainType.RUBBLE)])
        # setting the same terrain again is a no-op
        self.assertFalse(wmap.set_terrain(3, 4, TerrainType.RUBBLE))
        self.assertEqual(len(seen), 1)

    def test_new_terrains_render(self):
        from ui.renderer import _TERRAIN_TO_SPRITE
        self.assertIn(TerrainType.RUBBLE, _TERRAIN_TO_SPRITE)
        self.assertIn(TerrainType.SCORCHED, _TERRAIN_TO_SPRITE)

    def test_rubble_is_walkable_for_now(self):
        from world.world_map import WorldMap
        from characters.character import Character
        from characters.character_types import (CharacterClass,
                                                CharacterRace)
        wmap = WorldMap(10, 10)
        wmap.set_terrain(5, 5, TerrainType.RUBBLE)
        ch = Character(
            id="t", name="T", character_class=CharacterClass.VILLAGER,
            race=CharacterRace.HUMAN, level=1, strength=10,
            dexterity=10, constitution=10, intelligence=10, wisdom=10,
            charisma=10, hp=5, max_hp=5, position=(4, 5),
            description="", personality={}, goals=[], inventory=[])
        wmap.place_character(ch, 4, 5)
        self.assertTrue(wmap.move_character(ch, 5, 5))


class TestAoE(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(
            llm_provider="heuristic", enable_npc_processes=False)
        self.engine.start_game()
        self.player = self.engine.player
        wmap = self.engine.world.map
        self.ox, self.oy = wmap.width - 12, wmap.height - 10
        for y in range(self.oy - 2, self.oy + 5):
            for x in range(self.ox - 2, self.ox + 8):
                wmap.terrain[y][x] = TerrainType.GRASS
                ch = wmap.get_character_at(x, y)
                if ch is not None:
                    wmap.remove_character(ch)
        wmap.remove_character(self.player)
        self.player.position = (self.ox, self.oy)
        wmap.place_character(self.player, *self.player.position)
        self.player.metadata["spells_known"] = ["fireball",
                                                "magic_missile"]
        self.player.metadata["mana"] = 60
        self.player.metadata["max_mana"] = 60

    def tearDown(self):
        try:
            self.engine.end_game()
        except Exception:
            pass

    def _spawn(self, dx, dy, hp=30, template="wolf"):
        wmap = self.engine.world.map
        m = build_monster(template, (self.ox + dx, self.oy + dy))
        m.hp = m.max_hp = hp
        self.engine.npc_manager.add_npc(m)
        wmap.place_character(m, *m.position)
        return m

    def test_fireball_engulfs_the_cluster(self):
        a = self._spawn(4, 0)
        b = self._spawn(5, 0)
        c = self._spawn(4, 1)
        far = self._spawn(4, -4)          # outside the blast
        msg = self.engine.cast_spell("fireball", a.name)
        self.assertIn("engulfs", msg)
        for v in (a, b, c):
            self.assertLess(v.hp, 30, f"{v.name} must burn")
        self.assertEqual(far.hp, 30, "out of radius is safe")

    def test_caster_never_burns_themselves(self):
        a = self._spawn(1, 0)             # right beside the player
        hp0 = self.player.hp
        self.engine.cast_spell("fireball", a.name)
        self.assertEqual(self.player.hp, hp0,
                         "the caster shapes the flame around "
                         "themselves")

    def test_friendly_fire_is_real(self):
        mel = self.engine.npc_manager.get_npc("minstrel_01")
        wmap = self.engine.world.map
        wmap.remove_character(mel)
        mel.position = (self.ox + 4, self.oy + 1)
        wmap.place_character(mel, *mel.position)
        mel.hp = mel.max_hp = 30
        a = self._spawn(4, 0)
        self.engine.cast_spell("fireball", a.name)
        self.assertLess(mel.hp, 30,
                        "standing beside the target is a mistake")

    def test_blast_kills_are_real_deaths(self):
        a = self._spawn(4, 0, hp=5)
        b = self._spawn(5, 0, hp=5)
        msg = self.engine.cast_spell("fireball", a.name)
        self.assertIn("Slain in the blast", msg)
        self.assertFalse(a.is_active())
        self.assertFalse(b.is_active())

    def test_single_target_spells_unchanged(self):
        a = self._spawn(3, 0)
        b = self._spawn(4, 0)
        self.engine.cast_spell("magic_missile", a.name)
        self.assertLess(a.hp, 30)
        self.assertEqual(b.hp, 30, "magic missile hits ONE target")

    def test_walls_shield_the_indoors(self):
        # an NPC inside a building near the blast takes nothing
        loc = next(l for l in self.engine.world.locations
                   if l.name in self.engine.interiors)
        npc = self.engine.npc_manager.get_npc("tavernkeeper_01")
        wmap = self.engine.world.map
        wmap.remove_character(npc)
        npc.position = (loc.x, loc.y)
        wmap.place_character(npc, *npc.position)
        npc.hp = npc.max_hp = 30
        wmap.remove_character(self.player)
        self.player.position = (loc.x - 3, loc.y)
        wmap.place_character(self.player, *self.player.position)
        victim = build_monster("wolf", (loc.x - 1, loc.y))
        victim.hp = victim.max_hp = 30
        self.engine.npc_manager.add_npc(victim)
        wmap.place_character(victim, *victim.position)
        self.engine.cast_spell("fireball", victim.name)
        self.assertEqual(npc.hp, 30, "walls shield the indoors")


if __name__ == "__main__":
    unittest.main()
