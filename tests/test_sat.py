import unittest
import os

import circuitgraph as cg
from circuitgraph.sat import *
from circuitgraph.transform import mphf


class TestSat(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.c17 = cg.from_lib('c17_gates','c17')
		cls.s27 = cg.from_file('s27')

	def test_sat(self):
		self.assertTrue(sat(self.c17))
		self.assertTrue(sat(self.s27))
		self.assertFalse(sat(self.s27,assumptions={'n_10':True,'n_7':True}))
		self.assertFalse(sat(self.s27,assumptions={'n_12':True,'G0':False}))
		self.assertFalse(sat(self.s27,assumptions={'n_12':True,'n_12':False}))
		self.assertFalse(sat(self.c17,assumptions={'G16':True,'G17':True,'G1':False,'G2':False,'G3':False,'G4':False,'G5':False}))
		self.assertFalse(sat(self.c17,assumptions={'G16':True,'G1':False,'G2':False,'G3':False,'G4':False,'G5':False}))
		self.assertFalse(sat(self.c17,assumptions={'G17':True,'G1':False,'G2':False,'G3':False,'G4':False,'G5':False}))
		self.assertTrue(sat(self.c17,assumptions={'G16':False,'G17':False,'G1':False,'G2':False,'G3':False,'G4':False,'G5':False}))

		# timeout test
		c = mphf()
		with self.assertRaises(TimeoutError):
			print(sat(c,assumptions={'sat':True},timeout=1))

	def test_modelCount(self):
		# allow 3 inputs free
		startpoints = self.s27.startpoints()
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,assumptions={s:True for s in startpoints}),2)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,assumptions={s:True for s in startpoints}),4)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,assumptions={s:True for s in startpoints}),8)
		startpoints.pop()
		self.assertEqual(modelCount(self.s27,assumptions={s:True for s in startpoints}),16)


	def test_approxModelCount(self):
		# approxmc seems to be accurate in this range
		startpoints = self.s27.startpoints()
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,assumptions={s:True for s in startpoints}),2)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,assumptions={s:True for s in startpoints}),4)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,assumptions={s:True for s in startpoints}),8)
		startpoints.pop()
		self.assertEqual(approxModelCount(self.s27,assumptions={s:True for s in startpoints}),16)

