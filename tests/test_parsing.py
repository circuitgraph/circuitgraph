import unittest
import os

from hdlgraph.hdlgraph import HDLGraph

class TestParsing(unittest.TestCase):

    def test_parse(self):
        c17 = HDLGraph(os.path.dirname(__file__) + '/../rtl/c17.v')
        print(c17.graph.nodes['G8'])
