import unittest

import circuitgraph as cg
from circuitgraph.utils import clog2, int_to_bin, lint


class TestUtils(unittest.TestCase):
    def test_clog2(self):
        self.assertEqual(clog2(13), 4)
        self.assertEqual(clog2(16), 4)
        self.assertRaises(ValueError, clog2, 0)

    def test_int_to_bin(self):
        self.assertEqual(int_to_bin(4, 6), (False, False, False, True, False, False))
        self.assertEqual(
            int_to_bin(4, 6, lend=True), (False, False, True, False, False, False)
        )

    def test_lint(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        c.add("co", "output", fanin="c")
        c.add("d", "buf", fanin=["a"])
        c.add("do", "output", fanin=["d"])
        lint(c)
        c.set_type("c", "buf")
        self.assertRaises(ValueError, lint, c)
        c.set_type("c", "input")
        self.assertRaises(ValueError, lint, c)
        c.set_type("c", "xor")
        c.disconnect("a", "c")
        c.disconnect("b", "c")
        self.assertRaises(ValueError, lint, c)
        c.connect("a", "co")
        c.connect("b", "co")
        self.assertRaises(ValueError, lint, c)
