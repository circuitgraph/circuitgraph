import unittest
import os

from circuitgraph.circuitgraph import CircuitGraph

class TestCircuitGraph(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.c17 = CircuitGraph(os.path.dirname(__file__) + '/../rtl/c17.v')
    
    def test_fanin(self):
        self.assertSetEqual(set(self.c17.fanin('G9')), set(['G3', 'G4']))
        self.assertSetEqual(set(self.c17.fanin('G9')), set(['G3', 'G4']))
        self.assertSetEqual(set(self.c17.fanin('G17')), set(['G12', 'G15']))
        self.assertFalse(set(self.c17.fanin('G1')))

    def test_fanout(self):
        self.assertSetEqual(set(self.c17.fanout('G1')), set(['G8']))
        self.assertSetEqual(set(self.c17.fanout('G12')), set(['G16', 'G17']))
        self.assertFalse(set(self.c17.fanout('G17')))
