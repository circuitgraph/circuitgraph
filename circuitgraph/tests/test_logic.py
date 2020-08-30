import unittest

import circuitgraph as cg
from circuitgraph.logic import *
from circuitgraph.sat import sat
from random import randint


class TestLogic(unittest.TestCase):
    def test_adder(self):
        w = randint(1, 66)
        add = adder(w)

        a = randint(0, 2 ** w - 1)
        b = randint(0, 2 ** w - 1)

        enc_a = {f"a_{i}": v for i, v in enumerate(cg.int_to_bin(a, w, lend=True))}
        enc_b = {f"b_{i}": v for i, v in enumerate(cg.int_to_bin(b, w, lend=True))}

        result = sat(add, {**enc_a, **enc_b})
        self.assertTrue(result)

        enc_out = [result[f"out_{i}"] for i in range(w + 1)]
        out = cg.bin_to_int(enc_out, lend=True)
        self.assertEqual(a + b, out)

    def test_popcount(self):
        w = randint(1, 66)
        p = popcount(w)

        ins = [randint(0, 1) for i in range(w)]
        enc_ins = {f"in_{i}": n for i, n in enumerate(ins)}

        result = sat(p, enc_ins)
        self.assertTrue(result)

        enc_out = [result[f"out_{i}"] for i in range(clog2(w + 1))]
        c = cg.bin_to_int(enc_out, lend=True)
        self.assertEqual(c, sum(ins))

    def test_mux(self):
        p = mux(5)
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
        result = sat(p, assumptions)
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
        result = sat(p, assumptions)
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
        result = sat(p, assumptions)
        self.assertTrue(result["out"])
