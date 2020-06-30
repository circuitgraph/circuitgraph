import unittest
import os

import circuitgraph as cg


class TestCircuitGraph(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c17 = cg.from_verilog(os.path.dirname(__file__) +
                                  '/../rtl/c17_gates.v', top='c17')

    def test_fanin(self):
        self.assertSetEqual(set(self.c17.fanin('G9')), set(['G3', 'G4']))
        self.assertSetEqual(set(self.c17.fanin('G9')), set(['G3', 'G4']))
        self.assertSetEqual(set(self.c17.fanin('G17')), set(['G12', 'G15']))
        self.assertFalse(set(self.c17.fanin('G1')))

    def test_fanout(self):
        self.assertSetEqual(set(self.c17.fanout('G1')), set(['G8']))
        self.assertSetEqual(set(self.c17.fanout('G12')), set(['G16', 'G17']))
        self.assertSetEqual(set(self.c17.fanout('G17')), set(['G17_out']))
        self.assertFalse(set(self.c17.fanout('G17_out')))
