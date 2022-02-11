import unittest
from random import randint

import circuitgraph as cg


class TestLogic(unittest.TestCase):
    def test_adder(self):
        w = randint(1, 66)
        add = cg.logic.adder(w)

        a = randint(0, 2 ** w - 1)
        b = randint(0, 2 ** w - 1)

        enc_a = {
            f"a_{i}": v for i, v in enumerate(cg.utils.int_to_bin(a, w, lend=True))
        }
        enc_b = {
            f"b_{i}": v for i, v in enumerate(cg.utils.int_to_bin(b, w, lend=True))
        }

        result = cg.sat.solve(add, {**enc_a, **enc_b})
        self.assertTrue(result)

        enc_out = [result[f"out_{i}"] for i in range(w + 1)]
        out = cg.utils.bin_to_int(enc_out, lend=True)
        self.assertEqual(a + b, out)

    def test_xor_hash(self):
        n = 5
        m = 3
        h = cg.logic.xor_hash(n, m)

        inp = {f"in_{i}": randint(0, 1) for i in range(n)}
        result = cg.sat.solve(h, inp)

    def test_banyan(self):
        bw = 32
        b = cg.logic.banyan(bw)

        inp = {n: randint(0, 1) for n in b.inputs()}
        result = cg.sat.solve(b, inp)

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
