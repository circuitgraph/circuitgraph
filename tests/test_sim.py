import unittest
import shutil

import circuitgraph as cg
from circuitgraph.sim import *
from circuitgraph.sat import sat
from random import choice


class TestSim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c17 = cg.from_lib("c17_gates", "c17")

    @unittest.skipIf(shutil.which("verilator") == None, "Verilator is not installed")
    def test_sim(self):
        sp = self.c17.startpoints()

        # create random vectors
        vectors = []
        for i in range(10):
            vectors.append({n: choice([True, False]) for n in sp})

        # run and compare with sat
        sat_results = [sat(self.c17, v) for v in vectors]
        sim_results = sim(self.c17, vectors)
        for sat_result, sim_result in zip(sim_results, sat_results):
            self.assertDictEqual(sat_result, sim_result)
