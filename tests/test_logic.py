import unittest
from itertools import product
from random import randint

import circuitgraph as cg


class TestLogic(unittest.TestCase):
    def test_half_adder(self):
        ha = cg.logic.half_adder()

        res = cg.sat.solve(ha, {"x": False, "y": False})
        self.assertFalse(res["c"])
        self.assertFalse(res["s"])

        res = cg.sat.solve(ha, {"x": False, "y": True})
        self.assertFalse(res["c"])
        self.assertTrue(res["s"])

        res = cg.sat.solve(ha, {"x": True, "y": False})
        self.assertFalse(res["c"])
        self.assertTrue(res["s"])

        res = cg.sat.solve(ha, {"x": True, "y": True})
        self.assertTrue(res["c"])
        self.assertFalse(res["s"])

    def test_full_adder(self):
        fa = cg.logic.full_adder()
        inputs = list(fa.inputs())
        for values in product([False, True], repeat=3):
            res = cg.sat.solve(fa, dict(zip(inputs, values)))
            oup = sum(int(i) for i in values)
            oup = cg.utils.int_to_bin(oup, 2)
            self.assertEqual(bool(oup[0]), res["cout"])
            self.assertEqual(bool(oup[1]), res["s"])

    def test_adder(self):
        for width in [2, 4, 6, 8]:
            add = cg.logic.adder(width, carry_out=True)

            a = randint(0, 2 ** width - 1)
            b = randint(0, 2 ** width - 1)

            enc_a = {
                f"a_{i}": v
                for i, v in enumerate(cg.utils.int_to_bin(a, width, lend=True))
            }
            enc_b = {
                f"b_{i}": v
                for i, v in enumerate(cg.utils.int_to_bin(b, width, lend=True))
            }

            result = cg.sat.solve(add, {**enc_a, **enc_b})
            self.assertTrue(result)

            enc_out = [result[f"out_{i}"] for i in range(width)]
            enc_out.append(result["cout"])
            out = cg.utils.bin_to_int(enc_out, lend=True)
            self.assertEqual(a + b, out)

    def test_mux(self):
        p = cg.logic.mux(5)
        assumptions = {
            "in_0": True,
            "in_1": False,
            "in_2": False,
            "in_3": True,
            "in_4": False,
            "sel_0": False,
            "sel_1": False,
            "sel_2": False,
        }
        result = cg.sat.solve(p, assumptions)
        self.assertTrue(result["out"])

        assumptions = {
            "in_0": True,
            "in_1": False,
            "in_2": False,
            "in_3": True,
            "in_4": False,
            "sel_0": True,
            "sel_1": False,
            "sel_2": False,
        }
        result = cg.sat.solve(p, assumptions)
        self.assertFalse(result["out"])

        assumptions = {
            "in_0": True,
            "in_1": True,
            "in_2": False,
            "in_3": True,
            "in_4": False,
            "sel_0": True,
            "sel_1": False,
            "sel_2": False,
        }
        result = cg.sat.solve(p, assumptions)
        self.assertTrue(result["out"])

    def test_popcount(self):
        w = randint(1, 66)
        p = cg.logic.popcount(w)

        ins = [randint(0, 1) for i in range(w)]
        enc_ins = {f"in_{i}": n for i, n in enumerate(ins)}

        result = cg.sat.solve(p, enc_ins)
        self.assertTrue(result)

        enc_out = [result[f"out_{i}"] for i in range(cg.utils.clog2(w + 1))]
        c = cg.utils.bin_to_int(enc_out, lend=True)
        self.assertEqual(c, sum(ins))
