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
        self.c432 = cg.from_lib("c432")

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

    def test_sequential_unroll(self):
        u = sequential_unroll(self.s27bb, 4, "D", "Q", ["clk"])
        ug = cg.from_lib("s27_unrolled_4")
        m = miter(u, ug)
        live = sat(m)
        self.assertTrue(live)
        self.assertFalse(sat(m, assumptions={"sat": True}))

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

    def test_subcircuit(self):
        c17 = cg.from_lib("c17")
        sc = subcircuit(c17, c17.transitive_fanin("N22") | {"N22"})
        self.assertSetEqual(
            sc.nodes(),
            {"N22", "N22_driver", "N10", "N16", "N1", "N3", "N2", "N11", "N6"},
        )
        self.assertSetEqual(
            sc.edges(),
            {
                ("N22_driver", "N22"),
                ("N10", "N22_driver"),
                ("N16", "N22_driver"),
                ("N1", "N10"),
                ("N3", "N10"),
                ("N2", "N16"),
                ("N11", "N16"),
                ("N3", "N11"),
                ("N6", "N11"),
            },
        )
        for node in sc:
            self.assertEqual(c17.type(node), sc.type(node))

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys(self):
        s = syn(self.s27, "yosys", suppress_output=True)
        m = miter(self.s27, s)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys_io(self):
        s = syn(
            self.s27,
            "yosys",
            suppress_output=True,
            pre_syn_file="pre_syn.v",
            post_syn_file="post_syn.v",
            working_dir="syn",
        )
        c0 = cg.from_file("pre_syn.v")
        c1 = cg.from_file("post_syn.v")
        m = miter(c0, c1)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        os.remove("pre_syn.v")
        os.remove("post_syn.v")
        shutil.rmtree("syn")

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys_exists(self):
        with NamedTemporaryFile(
            prefix="circuitgraph_synthesis_test", suffix=".v", mode="w"
        ) as tmp_in:
            tmp_in.write("module test(a, b, c);\n")
            tmp_in.write("input a, b;\n")
            tmp_in.write("output c;\n")
            tmp_in.write("nand g_n(c, a, b);\n")
            tmp_in.write("endmodule\n")
            tmp_in.flush()

            c = syn(
                cg.Circuit(name="test"),
                "yosys",
                suppress_output=True,
                pre_syn_file=tmp_in.name,
                verilog_exists=True,
            )
            c2 = cg.Circuit()
            c2.add("a", "input")
            c2.add("b", "input")
            c2.add("c", "output")
            c2.add("c_driver", "nand", fanin=["a", "b"], fanout=["c"])
            m = miter(c, c2)
            live = sat(m)
            self.assertTrue(live)
            different_output = sat(m, assumptions={"sat": True})
            self.assertFalse(different_output)

    @unittest.skipUnless(
        "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ, "Genus synthesis not setup"
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

    @unittest.skipUnless(
        "CIRCUITGRAPH_DC_LIBRARY_PATH" in os.environ, "DC synthesis not setup"
    )
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

    @unittest.skipUnless(
        "CIRCUITGRAPH_DC_LIBRARY_PATH" in os.environ, "DC synthesis not setup"
    )
    def test_syn_dc_io(self):
        s = syn(
            self.s27,
            "dc",
            suppress_output=True,
            pre_syn_file="pre_syn.v",
            post_syn_file="post_syn.v",
            working_dir="syn",
        )
        c0 = cg.from_file("pre_syn.v")
        c1 = cg.from_file("post_syn.v")
        m = miter(c0, c1)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        os.remove("pre_syn.v")
        os.remove("post_syn.v")
        shutil.rmtree("syn")

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

    def test_limit_fanin(self):
        k = 2
        c = self.c432
        ck = limit_fanin(c, k)

        # check conversion
        m = cg.miter(c, ck)
        self.assertFalse(cg.sat(m, assumptions={"sat": True}))

        for n in ck:
            self.assertTrue(len(ck.fanin(n)) <= k)
