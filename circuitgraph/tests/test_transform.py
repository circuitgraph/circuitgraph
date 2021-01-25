import unittest
import os
import shutil
import glob

import circuitgraph as cg
from circuitgraph.transform import *
from circuitgraph.sat import sat
from random import choice, randint


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.s27 = cg.strip_blackboxes(cg.from_lib("s27"))
        self.s27bb = cg.from_lib("s27")

        # incorrect copy of s27
        self.s27m = cg.copy(self.s27)
        self.s27m.graph.nodes["n_11"]["type"] = "and"

    def test_strip_io(self):
        # check self equivalence
        c = cg.strip_io(self.s27)
        self.assertTrue("input" not in c.type(c.nodes()))
        self.assertTrue("output" not in c.type(c.nodes()))

    def test_strip_inputs(self):
        # check self equivalence
        c = cg.strip_inputs(self.s27)
        self.assertTrue("input" not in c.type(c.nodes()))
        self.assertFalse("output" not in c.type(c.nodes()))

    def test_strip_outputs(self):
        # check self equivalence
        c = cg.strip_outputs(self.s27)
        self.assertFalse("input" not in c.type(c.nodes()))
        self.assertTrue("output" not in c.type(c.nodes()))

    # def test_seq_graph(self):
    #    g = seq_graph(self.s27)
    #    self.assertSetEqual(
    #        set(g.nodes()), set(["G1", "G3", "clk", "G5", "G6", "G0", "G2", "G7"]),
    #    )
    #    for n in ["G1", "G3", "G5", "G6", "G0", "G7"]:
    #        self.assertTrue(g.output(n))
    #    for n in ["G2", "clk"]:
    #        self.assertFalse(g.output(n))

    # def test_unroll(self):
    #    u = unroll(self.s27, 3)

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
        s = syn(self.s27, "yosys", suppress_output=True)
        m = miter(self.s27, s)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    @unittest.skipUnless(
        "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ, "Genus not installed"
    )
    def test_syn_genus(self):
        s = syn(self.s27, "genus", suppress_output=True)
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

    @unittest.skipIf(shutil.which("dc_shell-t") == None, "DesignCompiler not installed")
    def test_syn_dc(self):
        s = syn(self.s27, "dc", suppress_output=True)
        m = miter(self.s27, s)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        for f in glob.glob(f"{os.getcwd()}/command.log*"):
            os.remove(f)
        for f in glob.glob(f"{os.getcwd()}/default.svf*"):
            os.remove(f)

    # def test_ternary(self):
    #    # encode circuit
    #    t = ternary(self.s27)

    #    # check that x propagates
    #    result = cg.sat(t, {"n_11_x": True})
    #    self.assertTrue(result)
    #    self.assertTrue(result["n_12_x"])

    #    result = cg.sat(t, {"n_11_x": False})
    #    self.assertTrue(result)
    #    self.assertFalse(result["n_12_x"])

    #    result = cg.sat(t, {"n_2_x": True, "n_5_x": False})
    #    self.assertTrue(result)
    #    self.assertFalse(result["G6_x"])

    #    # if no x in startpoint, no x
    #    ass = {f"{s}_x": False for s in self.s27.startpoints()}
    #    result = cg.sat(t, ass)
    #    self.assertTrue(result)
    #    self.assertFalse(any(result[f"{n}_x"] for n in self.s27))

    #    # if all x in startpoint, all x
    #    ass = {f"{s}_x": True for s in self.s27.startpoints()}
    #    result = cg.sat(t, ass)
    #    self.assertTrue(result)
    #    self.assertTrue(all(result[f"{n}_x"] for n in self.s27))

    def test_sensitivity_transform(self):
        # pick random node and input value
        n = choice(tuple(self.s27.nodes() - self.s27.startpoints()))
        nstartpoints = self.s27.startpoints(n)
        while len(nstartpoints) < 1:
            n = choice(tuple(self.s27.nodes() - self.s27.startpoints()))
            nstartpoints = self.s27.startpoints(n)
        input_val = {i: randint(0, 1) for i in nstartpoints}

        # build sensitivity circuit
        s = sensitivity_transform(self.s27, n)

        # find sensitivity at an input
        model = sat(s, input_val)
        sen_s = sum(model[o] for o in s.outputs() if "dif_out" in o)

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

        # find input with sensitivity
        vs = cg.int_to_bin(sen_s, cg.clog2(len(nstartpoints) + 1), True)
        model = sat(s, {f"sen_out_{i}": v for i, v in enumerate(vs)})

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
