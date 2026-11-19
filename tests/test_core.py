"""Behaviour that must survive every refactor."""
import unittest

from helpers import Game, make_scene, obj, new_project  # noqa: F401
from pawnlang import parse, PawnError


class Language(unittest.TestCase):
    def test_arithmetic_and_print(self):
        g = Game('on start\n    print(1 + 2 * 3, 7 % 4, 10 / 4)\n')
        self.assertEqual(g.out, ["7 3 2.5"])

    def test_if_elif_else_and_loops(self):
        g = Game('''on start
    t = 0
    repeat 3 times
        t += 2
    i = 0
    while i < 4
        i += 1
        if i == 2
            continue
        if i == 4
            break
        t += 10
    each c in [1, 2, 3]
        t += c
    if t > 100
        print("big")
    elif t == 32
        print("ok", t)
    else
        print("other", t)
''')
        self.assertEqual(g.out, ["ok 32"])

    def test_functions_and_recursion(self):
        g = Game('''def fact(n)
    if n <= 1
        return 1
    return n * fact(n - 1)
on start
    print(fact(5))
''')
        self.assertEqual(g.out, ["120"])

    def test_string_interpolation(self):
        g = Game('on start\n    n = 3\n    print("n is {n + 1}!")\n')
        self.assertEqual(g.out, ["n is 4!"])

    def test_errors_are_friendly(self):
        g = Game('on start\n    print(speeed)\nspeed = 3\n')
        self.assertIn("isn't defined", g.error.pretty())
        g = Game('on start\n    x = 1 / 0\n')
        self.assertIn("divide by zero", g.error.pretty())
        with self.assertRaises(PawnError):
            parse("if x\nprint(1)\n")

    def test_runaway_loop_is_stopped(self):
        g = Game('on start\n    while true\n        pass\n')
        self.assertIsNotNone(g.error)


class Runtime(unittest.TestCase):
    def test_when_every_after(self):
        g = Game('''n = 0
t = 0
a = 0
when true
    n += 1
every 0.5 seconds
    t += 1
after 1 second
    a += 1
''')
        g.run(125)
        fields = g.rt.instances[0].fields
        self.assertEqual(fields["n"], 125)
        self.assertEqual(fields["t"], 4)
        self.assertEqual(fields["a"], 1)

    def test_inspector_values_override_defaults(self):
        g = Game('speed = 5\non start\n    print(speed)\n', values={"speed": 99})
        self.assertEqual(g.out, ["99"])

    def test_gravity_lands_on_solid(self):
        ground = obj("Ground", y=100, w=400, h=20, solid=True)
        g = Game("pass\n", extra=[ground], body=True, y=0)
        g.run(120)
        p = g.find("P")
        self.assertTrue(p.on_ground)
        self.assertAlmostEqual(p.y, 100 - 10 - 5, delta=1)

    def test_touching_and_destroy(self):
        coin = obj("Coin", "c.pawn", x=3, y=0)
        proj = new_project()
        proj.write_script("c.pawn", 'when touching("P")\n    destroy()\n')
        g = Game("pass\n", extra=[coin], proj=proj)
        g.run(2)
        self.assertIsNone(g.find("Coin"))

    def test_spawn_copies_template(self):
        tpl = obj("B", active=False)
        g = Game('on start\n    spawn("B", 40, 50)\n    print(len(all("B")))\n', extra=[tpl])
        self.assertEqual(g.out, ["1"])

    def test_game_namespace_defaults_to_zero(self):
        g = Game('on start\n    game.score += 1\n    print(game.score)\n')
        self.assertEqual(g.out, ["1"])

    def test_object_properties(self):
        g = Game('on start\n    self.x = 42\n    self.color = "#ff0000"\n    print(self.x, self.color)\n')
        self.assertEqual(g.out, ["42 #ff0000"])

    def test_hot_reload_swaps_code(self):
        g = Game('when true\n    game.v = 1\n')
        g.run(1)
        g.proj.write_script("a.pawn", 'when true\n    game.v = 2\n')
        self.assertEqual(g.rt.reload_script("a.pawn"), 1)
        g.run(1)
        self.assertEqual(g.rt.game.d["v"], 2)


if __name__ == "__main__":
    unittest.main()
