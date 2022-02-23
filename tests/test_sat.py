import re
import shutil
import tempfile
import unittest
from itertools import product

import circuitgraph as cg


class TestSat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c17 = cg.from_lib("c17_gates")
        cls.s27 = cg.from_lib("s27")

    def test_solve(self):
        self.assertTrue(cg.sat.solve(self.c17))
        self.assertTrue(cg.sat.solve(self.s27))
        self.assertFalse(
            cg.sat.solve(self.s27, assumptions={"n_10": True, "n_7": True})
        )
        self.assertFalse(
            cg.sat.solve(self.s27, assumptions={"n_12": True, "G0": False})
        )
        self.assertFalse(
            cg.sat.solve(
                self.c17,
                assumptions={
                    "G16": True,
                    "G17": True,
                    "G1": False,
                    "G2": False,
                    "G3": False,
                    "G4": False,
                    "G5": False,
                },
            )
        )
        self.assertFalse(
            cg.sat.solve(
                self.c17,
                assumptions={
                    "G16": True,
                    "G1": False,
                    "G2": False,
                    "G3": False,
                    "G4": False,
                    "G5": False,
                },
            )
        )
        self.assertFalse(
            cg.sat.solve(
                self.c17,
                assumptions={
                    "G17": True,
                    "G1": False,
                    "G2": False,
                    "G3": False,
                    "G4": False,
                    "G5": False,
                },
            )
        )
        self.assertTrue(
            cg.sat.solve(
                self.c17,
                assumptions={
                    "G16": False,
                    "G17": False,
                    "G1": False,
                    "G2": False,
                    "G3": False,
                    "G4": False,
                    "G5": False,
                },
            )
        )

    def test_model_count(self):
        # allow 3 inputs free
        startpoints = self.s27.startpoints()

        startpoints.pop()
        self.assertEqual(
            cg.sat.model_count(self.s27, assumptions={s: True for s in startpoints}), 2
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.model_count(self.s27, assumptions={s: True for s in startpoints}), 4
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.model_count(self.s27, assumptions={s: True for s in startpoints}), 8
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.model_count(self.s27, assumptions={s: True for s in startpoints}), 16
        )

    @unittest.skipIf(shutil.which("approxmc") is None, "Approxmc is not installed")
    def test_approx_model_count(self):
        # approxmc seems to be accurate in this range
        startpoints = self.s27.startpoints()

        startpoints.pop()
        self.assertEqual(
            cg.sat.approx_model_count(
                self.s27, assumptions={s: True for s in startpoints}
            ),
            2,
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.approx_model_count(
                self.s27, assumptions={s: True for s in startpoints}
            ),
            4,
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.approx_model_count(
                self.s27, assumptions={s: True for s in startpoints}
            ),
            8,
        )

        startpoints.pop()
        self.assertEqual(
            cg.sat.approx_model_count(
                self.s27, assumptions={s: True for s in startpoints}
            ),
            16,
        )

    @unittest.skipIf(shutil.which("approxmc") is None, "Approxmc is not installed")
    def test_approx_model_count_xors(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b", "c"])
        c.add("e", "or", fanin=["c", "d"], output=True)

        m = 0
        sp = list(c.startpoints())
        for vs in product([False, True], repeat=len(sp)):
            asmp = dict(zip(sp, vs))
            m += cg.sat.solve(c, asmp)["e"]

        with tempfile.NamedTemporaryFile(
            prefix="circuitgraph_test_approxmc_model_count_xors", mode="r"
        ) as tmp_in:
            self.assertEqual(
                cg.sat.approx_model_count(
                    c,
                    assumptions={"e": True},
                    use_xor_clauses=True,
                    log_file=tmp_in.name,
                ),
                m,
            )
            match = re.search(r"c -- xor clauses added: (\d+)", tmp_in.read())
            self.assertEqual(int(match[1]), 1)

        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "input")
        c.add("e", "xnor", fanin=["a", "b", "c"])
        c.add("f", "xor", fanin=["d", "e"], output=True)

        m = 0
        sp = list(c.startpoints())
        for vs in product([False, True], repeat=len(sp)):
            asmp = dict(zip(sp, vs))
            m += cg.sat.solve(c, asmp)["f"]

        with tempfile.NamedTemporaryFile(
            prefix="circuitgraph_test_approxmc_model_count_xors", mode="r"
        ) as tmp_in:
            self.assertEqual(
                cg.sat.approx_model_count(
                    c,
                    assumptions={"f": True},
                    use_xor_clauses=True,
                    log_file=tmp_in.name,
                ),
                m,
            )
            match = re.search(r"c -- xor clauses added: (\d+)", tmp_in.read())
            self.assertEqual(int(match[1]), 2)
