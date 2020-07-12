import unittest
import os

import circuitgraph as cg

class TestCircuit(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.c17 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/c17_gates.v', name='c17')
		cls.s27 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/s27.v', name='s27')

	def test_fanin(self):
		self.assertSetEqual(self.c17.fanin('G9'), set(['G3', 'G4']))
		self.assertSetEqual(self.c17.fanin('G9'), set(['G3', 'G4']))
		self.assertSetEqual(self.c17.fanin('G17'), set(['G12', 'G15']))
		self.assertFalse(self.c17.fanin('G1'))
		self.assertSetEqual(self.c17.fanin(['G9','G17']), self.c17.fanin('G9')|self.c17.fanin('G17'))

	def test_fanout(self):
		self.assertSetEqual(self.c17.fanout('G1'), set(['G8']))
		self.assertSetEqual(self.c17.fanout('G12'), set(['G16', 'G17']))
		self.assertSetEqual(self.c17.fanout('G17'), set(['output[G17]']))
		self.assertFalse(self.c17.fanout('output[G17]'))
		self.assertSetEqual(self.c17.fanout(['G1','G8']), self.c17.fanout('G1')|self.c17.fanout('G8'))

	def test_node(self):
		self.assertFalse(self.s27.nodes('nand')&self.c17.nodes('lat'))
		self.assertSetEqual(self.s27.nodes('ff'),set(['G7','G6','G5']))
		self.assertSetEqual(self.s27.nodes('input'),set(['clk','G0','G1','G2','G3']))
		self.assertSetEqual(self.s27.nodes('output'),set(['output[G17]']))

	def test_contains(self):
		self.assertFalse('adsf' in self.s27)
		self.assertTrue('G7' in self.s27)

	def test_type(self):
		self.assertTrue(self.s27.type('G7')=='ff')
		self.assertTrue(self.s27.type('clk[G7]')=='clk')
		self.assertTrue(self.s27.type('n_4')=='nand')

	def test_endpoints(self):
		self.assertSetEqual(self.s27.endpoints(),set(['d[G5]','d[G6]','d[G7]','output[G17]']))
		self.assertSetEqual(self.s27.endpoints('n_20'),set(['output[G17]']))
		self.assertSetEqual(self.s27.endpoints(['n_20','n_11']),set(['output[G17]','d[G5]']))

	def test_startpoints(self):
		self.assertSetEqual(self.s27.startpoints(),set(['G5','G6','G7','clk','G0','G1','G2','G3']))
		self.assertSetEqual(self.s27.startpoints('n_5'),set(['G6','G0']))
		self.assertSetEqual(self.s27.startpoints(['n_1','n_2']),set(['G5','G0']))

	def test_transitiveFanout(self):
		self.assertSetEqual(self.s27.transitiveFanout('G5'),set(['n_1','G17','output[G17]','d[G5]','n_12','n_11','n_9','n_20','d[G6]','n_21']))
		self.assertSetEqual(self.s27.transitiveFanout('G5',stopatTypes=['not','nor']),set(['n_1','n_20','n_21']))
		self.assertSetEqual(self.s27.transitiveFanout('G5',stopatNodes=['n_21','n_20','n_1']),set(['n_1','n_20','n_21']))
		self.assertSetEqual(self.s27.transitiveFanout('G5',stopatTypes=['not'],stopatNodes=['n_21','n_20']),set(['n_1','n_20','n_21']))
		self.assertSetEqual(self.s27.transitiveFanout(['G5','n_3']),set(['n_6','d[G7]','n_1','G17','output[G17]','d[G5]','n_12','n_11','n_9','n_20','d[G6]','n_21']))

	def test_transitiveFanin(self):
		self.assertSetEqual(self.s27.transitiveFanin('n_4'),set(['G3','n_0','G1']))
		self.assertSetEqual(self.s27.transitiveFanin('n_4',stopatTypes=['not']),set(['G3','n_0']))
		self.assertSetEqual(self.s27.transitiveFanin('n_4',stopatNodes=['n_0']),set(['G3','n_0']))
		self.assertSetEqual(self.s27.transitiveFanin('n_4',stopatTypes=['not'],stopatNodes=['n_0']),set(['n_0','G3']))
		self.assertSetEqual(self.s27.transitiveFanin(['n_4','n_3']),set(['G3','n_0','G7','G1']))


class TestCircuitEdit(unittest.TestCase):

	def setUp(self):
		self.c17 = cg.from_file(os.path.dirname(__file__) +
								  '/../rtl/c17_gates.v', name='c17')

	def test_add(self):
		pass

	def test_extend(self):
		pass

	def test_connect(self):
		pass

