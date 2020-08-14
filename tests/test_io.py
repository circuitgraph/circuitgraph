import unittest

import circuitgraph as cg


class TestIO(unittest.TestCase):
    def test_bench(self):
        c17 = cg.from_lib("b22_C")

    def test_verilog_comb(self):
        mix = cg.from_lib("mix")

    def test_verilog_seq(self):
        s27 = cg.from_lib("s27")
