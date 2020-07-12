import unittest
import os

import circuitgraph as cg
from circuitgraph.sat import *
from circuitgraph.transform import mphf


class TestSat(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.c17 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/c17_gates.v', name='c17')
		cls.s27 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/s27.v', name='s27')

	def test_sat(self):
		self.assertTrue(sat(self.c17))
		self.assertTrue(sat(self.s27))
		self.assertFalse(sat(self.s27,true=['n_10','n_7']))
		self.assertFalse(sat(self.s27,true=['n_12'],false=['G0']))
		self.assertFalse(sat(self.s27,true=['n_12'],false=['n_12']))
		self.assertFalse(sat(self.c17,true=['G16','G17'],false=['G1','G2','G3','G4','G5']))
		self.assertFalse(sat(self.c17,true=['G16'],false=['G1','G2','G3','G4','G5']))
		self.assertFalse(sat(self.c17,true=['G17'],false=['G1','G2','G3','G4','G5']))
		self.assertTrue(sat(self.c17,false=['G16','G17','G1','G2','G3','G4','G5']))

		# timeout test
		c = mphf()
		with self.assertRaises(TimeoutError):
			print(sat(c,true=['sat'],timeout=1))

	def test_modelCount(self):
		# allow 3 inputs free
		startpoints = self.s27.startpoints()
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,true=startpoints),2)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,true=startpoints),4)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,true=startpoints),8)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,true=startpoints),16)


	def test_approxModelCount(self):
		# approxmc seems to be accurate in this range
		startpoints = self.s27.startpoints()
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,true=startpoints),2)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,true=startpoints),4)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,true=startpoints),8)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,true=startpoints),16)

