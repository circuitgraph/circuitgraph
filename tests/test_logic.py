import unittest

from circuitgraph import logic
from circuitgraph.sat import sat


class TestLogic(unittest.TestCase):

    def test_adder(self):
        a = logic.adder(5)

        assumptions = {'a_0': True, 'a_1': False, 'a_2': False, 'a_3': False,
                       'a_4': False, 'b_0': True, 'b_1': True, 'b_2': False,
                       'b_3': False, 'b_4': False}

        result = sat(a, assumptions)
        self.assertFalse(result['out_0'])
        self.assertFalse(result['out_1'])
        self.assertTrue(result['out_2'])
        self.assertFalse(result['out_3'])
        self.assertFalse(result['out_4'])
        self.assertFalse(result['out_5'])

    def test_popcount(self):
        p = logic.popcount(5)

        assumptions = {'in_0': True, 'in_1': False,
                       'in_2': False, 'in_3': True, 'in_4': False}

        result = sat(p, assumptions)
        self.assertFalse(result['out_0'])
        self.assertTrue(result['out_1'])
        self.assertFalse(result['out_2'])
        self.assertFalse(result['out_3'])

    def test_mux(self):
        p = logic.mux(5)
        assumptions = {'in_0': True, 'in_1': False, 'in_2': False,
                       'in_3': True, 'in_4': False, 'sel_0': False,
                       'sel_1': False, 'sel_2': False}
        result = sat(p, assumptions)
        self.assertTrue(result['out'])

        assumptions = {'in_0': True, 'in_1': False, 'in_2': False,
                       'in_3': True, 'in_4': False, 'sel_0': True,
                       'sel_1': False, 'sel_2': False}
        result = sat(p, assumptions)
        self.assertFalse(result['out'])

        assumptions = {'in_0': True, 'in_1': True, 'in_2': False,
                       'in_3': True, 'in_4': False, 'sel_0': True,
                       'sel_1': False, 'sel_2': False}
        result = sat(p, assumptions)
        self.assertTrue(result['out'])
