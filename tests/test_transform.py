import unittest
import os

import circuitgraph as cg
from circuitgraph.transform import *
from circuitgraph.sat import sat
import code


class TestTransform(unittest.TestCase):

	def setUp(self):
		self.s27 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/s27.v', name='s27')

		# incorrect copy of s27
		self.s27m = self.s27.copy()
		self.s27m.graph.nodes['n_11']['type'] = 'buf'

	def test_miter(self):
		# check self equivalence
		m = miter(self.s27)
		live = sat(m)
		self.assertTrue(live)
		different_output = sat(m,true=['sat'])
		self.assertFalse(different_output)

		# check equivalence with incorrect copy
		m = miter(self.s27,self.s27m)
		live = sat(m)
		self.assertTrue(live)
		different_output = sat(m,true=['sat'])
		self.assertTrue(different_output)

		# check equivalence with free inputs
		startpoints = self.s27.startpoints()
		startpoints.pop()
		m = miter(self.s27,startpoints=startpoints)
		live = sat(m)
		self.assertTrue(live)
		different_output = sat(m,true=['sat'])
		self.assertTrue(different_output)

	def test_syn(self):
		# synthesize and check equiv
		s = syn(self.s27)
		m = miter(self.s27,s)
		live = sat(m)
		self.assertTrue(live)
		different_output = sat(m,true=['sat'])
		self.assertFalse(different_output)

