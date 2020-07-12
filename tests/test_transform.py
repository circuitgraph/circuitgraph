import unittest
import os

import circuitgraph as cg
from circuitgraph.transform import *
import code


class TestTransform(unittest.TestCase):

	def setUp(self):
		cls.s27 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/s27.v', name='s27')

		# incorrect copy of s27
		cls.s27m = cls.s27.copy()
		cls.s27m.graph.nodes['n_11']['type'] = 'buf'

	def test_miter(self):
		# check self equivalence
		m = miter(self.s27)
		live = m.sat()
		self.assertTrue(live)
		different_output = m.sat(true=['sat'])
		self.assertFalse(different_output)

		# check equivalence with incorrect copy
		m = miter(self.s27,self.s27m)
		live = m.sat()
		self.assertTrue(live)
		different_output = m.sat(true=['sat'])
		self.assertTrue(different_output)

		# check equivalence with free inputs
		startpoints = self.s27.startpoints()
		startpoints.pop()
		m = miter(self.s27,startpoints=startpoints)
		live = m.sat()
		self.assertTrue(live)
		different_output = m.sat(true=['sat'])
		self.assertTrue(different_output)

	def test_syn(self):
		# synthesize and check equiv
		s = syn(self.s27)
		m = miter(self.s27,s)
		live = m.sat()
		self.assertTrue(live)
		different_output = m.sat(true=['sat'])
		self.assertFalse(different_output)

