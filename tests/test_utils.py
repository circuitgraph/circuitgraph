import tempfile
import unittest
from pathlib import Path

import circuitgraph as cg


class TestUtils(unittest.TestCase):
    def test_visualize(self):
        tmpdir = tempfile.mkdtemp(prefix="circuitgraph_test_visualize")
        c = cg.from_lib("c17")
        cg.visualize(c, f"{tmpdir}/c17.png")
        self.assertTrue(Path(f"{tmpdir}/c17.png").resolve().is_file())
        self.assertFalse(Path(f"{tmpdir}/c17.dot").resolve().is_file())

        cg.visualize(c, f"{tmpdir}/c17.dot")
        self.assertTrue(Path(f"{tmpdir}/c17.dot").resolve().is_file())

    def test_clog2(self):
        self.assertEqual(cg.utils.clog2(13), 4)
        self.assertEqual(cg.utils.clog2(16), 4)
        self.assertRaises(ValueError, cg.utils.clog2, 0)

    def test_int_to_bin(self):
        self.assertEqual(
            cg.utils.int_to_bin(4, 6), (False, False, False, True, False, False)
        )
        self.assertEqual(
            cg.utils.int_to_bin(4, 6, lend=True),
            (False, False, True, False, False, False),
        )

    def test_lint(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"], output=True)
        c.add("d", "buf", fanin=["a"])
        cg.lint(c)
        c.set_type("c", "buf")
        self.assertRaises(ValueError, cg.lint, c)
        c.set_type("c", "input")
        self.assertRaises(ValueError, cg.lint, c)
        c.set_type("c", "xor")
        c.disconnect("a", "c")
        c.disconnect("b", "c")
        self.assertRaises(ValueError, cg.lint, c)
