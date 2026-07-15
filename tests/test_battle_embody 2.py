"""Player role-swap (P17.7): the human drives ONE soldier while its squad
fights on around it — the tick skips the embodied soldier's AI, and
embody_move / embody_attack are its manual controls."""

import unittest

from engine.battle import BattleField, Squad, BattleSession


def _sq(archetype, cells, team="red", sid="s"):
    return Squad.raise_squad(sid, team, archetype, cells)


class TestEmbodyState(unittest.TestCase):
    def setUp(self):
        self.bf = BattleField(20, 10)
        self.sq = _sq("infantry_sword", [(3, 5), (3, 6)], team="red")
        self.bf.add_squad(self.sq)
        self.sess = BattleSession(self.bf, seed=1)

    def test_embody_a_live_soldier(self):
        sid = self.sq.soldiers[0].sid
        self.assertTrue(self.sess.embody(sid))
        self.assertEqual(self.sess.embodied, sid)
        self.assertIs(self.sess.embodied_soldier(), self.sq.soldiers[0])

    def test_cannot_embody_a_stranger(self):
        self.assertFalse(self.sess.embody("no_such_sid"))
        self.assertIsNone(self.sess.embodied)

    def test_embodied_soldier_none_after_death(self):
        sid = self.sq.soldiers[0].sid
        self.sess.embody(sid)
        self.sq.soldiers[0].hurt(999)
        self.assertIsNone(self.sess.embodied_soldier())

    def test_unembody(self):
        self.sess.embody(self.sq.soldiers[0].sid)
        self.sess.unembody()
        self.assertIsNone(self.sess.embodied)


class TestTickSkipsTheDriver(unittest.TestCase):
    def test_squad_fights_on_but_the_driver_holds(self):
        bf = BattleField(30, 10)
        # a two-man line ordered to charge a distant foe
        line = _sq("infantry_sword", [(3, 4), (3, 5)], team="red")
        line.set_order("charge", "foe")
        foe = _sq("infantry_sword", [(20, 4)], team="blue", sid="foe")
        bf.add_squad(line)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=1)
        driver = line.soldiers[0]
        mate = line.soldiers[1]
        sess.embody(driver.sid)
        p_driver0, p_mate0 = driver.pos, mate.pos
        for _ in range(3):
            sess.tick()
        self.assertEqual(driver.pos, p_driver0,
                         "the driver waits for the player, doesn't advance")
        self.assertNotEqual(mate.pos, p_mate0,
                            "its squadmate charges on as normal")


class TestManualControls(unittest.TestCase):
    def test_embody_move_steps_the_soldier(self):
        bf = BattleField(20, 10)
        sq = _sq("infantry_sword", [(5, 5)], team="red")
        bf.add_squad(sq)
        sess = BattleSession(bf, seed=1)
        sess.embody(sq.soldiers[0].sid)
        self.assertTrue(sess.embody_move(1, 0))
        self.assertEqual(sq.soldiers[0].pos, (6, 5))
        self.assertTrue(sq.soldiers[0].moved_last)

    def test_embody_move_blocked_by_a_wall(self):
        bf = BattleField(20, 10)
        bf.add_wall(6, 5, "stone_wall")
        sq = _sq("infantry_sword", [(5, 5)], team="red")
        bf.add_squad(sq)
        sess = BattleSession(bf, seed=1)
        sess.embody(sq.soldiers[0].sid)
        self.assertFalse(sess.embody_move(1, 0))
        self.assertEqual(sq.soldiers[0].pos, (5, 5), "the wall stops him")

    def test_embody_move_needs_a_body(self):
        bf = BattleField(20, 10)
        sess = BattleSession(bf, seed=1)
        self.assertFalse(sess.embody_move(1, 0))     # nobody embodied

    def test_embody_attack_hits_an_adjacent_foe(self):
        bf = BattleField(20, 10)
        me = _sq("infantry_sword", [(5, 5)], team="red", sid="me")
        foe = _sq("infantry_sword", [(6, 5)], team="blue", sid="foe")
        bf.add_squad(me)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=0)
        sess.embody(me.soldiers[0].sid)
        hp0 = foe.soldiers[0].hp
        landed = False
        for _ in range(10):                      # a d20 can miss; keep at it
            if sess.embody_attack() and foe.soldiers[0].hp < hp0:
                landed = True
                break
            if foe.soldiers[0].hp < hp0:
                landed = True
                break
        self.assertTrue(landed, "the driver cut down the man beside him")

    def test_embody_attack_no_foe_in_reach(self):
        bf = BattleField(20, 10)
        me = _sq("infantry_sword", [(5, 5)], team="red", sid="me")
        foe = _sq("infantry_sword", [(18, 5)], team="blue", sid="foe")
        bf.add_squad(me)
        bf.add_squad(foe)
        sess = BattleSession(bf, seed=0)
        sess.embody(me.soldiers[0].sid)
        self.assertFalse(sess.embody_attack(), "nothing in reach")


class TestEmbodyScreenWire(unittest.TestCase):
    """The battle-screen glue (E toggles, ESC releases, camera-lock render)
    drives the session's role-swap API — smoke-tested headless."""

    def test_screen_embody_flow(self):
        import pygame
        pygame.display.init()
        from ui.battle_screen import BattleScreen
        sc = BattleScreen("open_field", width=900, height=640, seed=1)
        lead = sc._selected().alive_soldiers[0]
        sc._toggle_embody()
        self.assertEqual(sc.session.embodied, lead.sid, "E dropped in")
        sc._render()                        # camera-lock + embodied HUD path
        # in-body, ESC releases to command rather than leaving the screen
        self.assertIsNone(sc._key(pygame.K_ESCAPE))
        self.assertIsNone(sc.session.embodied)
        # out of body, ESC now backs out of the screen
        self.assertEqual(sc._key(pygame.K_ESCAPE), "exit")


if __name__ == "__main__":
    unittest.main()
