import unittest
import os
import shutil
import glob

import circuitgraph as cg
from circuitgraph.transform import miter, syn, sensitivity
from circuitgraph.sat import sat
from random import sample, randint
import code


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.s27 = cg.from_lib("s27")

        # incorrect copy of s27
        self.s27m = self.s27.copy()
        self.s27m.graph.nodes["n_11"]["type"] = "buf"

    def test_miter(self):
        # check self equivalence
        m = miter(self.s27)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)

        # check equivalence with incorrect copy
        m = miter(self.s27, self.s27m)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertTrue(different_output)

        # check equivalence with free inputs
        startpoints = self.s27.startpoints() - set(["clk"])
        startpoints.pop()
        m = miter(self.s27, startpoints=startpoints)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertTrue(different_output)

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys(self):
        # synthesize and check equiv
        s = syn(self.s27, "Yosys", print_output=False)
        m = miter(self.s27, s)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    @unittest.skipUnless(
        "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ, "Genus not installed"
    )
    def test_syn_genus(self):
        if "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ:
            s = syn(self.s27, "Genus", print_output=False)
            m = miter(self.s27, s)
            live = sat(m)
            self.assertTrue(live)
            different_output = sat(m, assumptions={"sat": True})
            self.assertFalse(different_output)
            for f in glob.glob(f"{os.getcwd()}/genus.cmd*"):
                os.remove(f)
            for f in glob.glob(f"{os.getcwd()}/genus.log*"):
                os.remove(f)
            shutil.rmtree(f"{os.getcwd()}/fv")

    @unittest.skip("Failing on Travis")
    def test_sensitivity(self):
        # pick random node and input value
        n = sample(self.s27.nodes() - self.s27.startpoints(), 1)[0]
        nstartpoints = self.s27.startpoints(n)
        input_val = {i: randint(0, 1) for i in nstartpoints}

        # build sensitivity circuit
        s = sensitivity(self.s27, n)

        # find sensitivity at an input
        model = sat(s, input_val)
        sen_s = sum(model[o] for o in s.outputs() if "difference" in o)

        # try inputs Hamming distance 1 away
        output_val = sat(self.s27, input_val)[n]
        sen_sim = 0
        for i in nstartpoints:
            neighbor_input_val = {
                g: v if g != i else not v for g, v in input_val.items()
            }
            neighbor_output_val = sat(self.s27, neighbor_input_val)[n]
            if neighbor_output_val != output_val:
                sen_sim += 1

        if sen_s != sen_sim:
            code.interact(local=dict(globals(), **locals()))

        # check answer
        self.assertEqual(sen_s, sen_sim)

        # find input with sensitivity
        vs = cg.int_to_bin(sen_s, cg.clog2(len(nstartpoints)), True)
        model = sat(s, {f"out_{i}": v for i, v in enumerate(vs)})

        input_val = {i: model[i] for i in nstartpoints}

        # try inputs Hamming distance 1 away
        output_val = sat(self.s27, input_val)[n]
        sen_sim = 0
        for i in nstartpoints:
            neighbor_input_val = {
                g: v if g != i else not v for g, v in input_val.items()
            }
            neighbor_output_val = sat(self.s27, neighbor_input_val)[n]
            if neighbor_output_val != output_val:
                sen_sim += 1

        # check answer
        self.assertEqual(sen_s, sen_sim)
