import unittest
import random
import tempfile
import os
import shutil
from random import choice, randint

import circuitgraph as cg


class TestTx(unittest.TestCase):
    def setUp(self):
        self.s27 = cg.tx.strip_blackboxes(cg.from_lib("s27"))
        self.s27m = self.s27.copy()
        self.s27m.graph.nodes["n_11"]["type"] = "and"
        self.c432 = cg.from_lib("c432")

    def test_strip_io(self):
        # check self equivalence
        c = cg.tx.strip_io(self.s27)
        self.assertTrue("input" not in c.type(c.nodes()))
        self.assertFalse([i for i in c if c.is_output(i)])

    def test_strip_inputs(self):
        # check self equivalence
        c = cg.tx.strip_inputs(self.s27)
        self.assertTrue("input" not in c.type(c.nodes()))
        self.assertTrue([i for i in c if c.is_output(i)])

    def test_strip_outputs(self):
        # check self equivalence
        c = cg.tx.strip_outputs(self.s27)
        self.assertFalse("input" not in c.type(c.nodes()))
        self.assertTrue("output" not in c.type(c.nodes()))

    def test_sequential_unroll(self):
        c = cg.from_lib("s27")
        num_unroll = 4
        cu, io_map = cg.tx.sequential_unroll(c, num_unroll, "D", "Q", ["clk"])
        self.assertEqual(
            len(cu.inputs()), (len(c.inputs()) - 1) * num_unroll + len(c.blackboxes)
        )
        self.assertEqual(len(cu.outputs()), len(c.outputs()) * num_unroll)

    def test_sequential_unroll_initial_values(self):
        c = cg.from_lib("s27")
        num_unroll = 4
        initial_values = {f: str(random.getrandbits(1)) for f in c.blackboxes}
        cu, io_map = cg.tx.sequential_unroll(
            c, num_unroll, "D", "Q", ["CK"], initial_values=initial_values,
        )
        self.assertEqual(len(cu.inputs()), (len(c.inputs()) - 1) * num_unroll)
        self.assertEqual(len(cu.outputs()), len(c.outputs()) * num_unroll)
        for k, v in initial_values.items():
            self.assertEqual(cu.type(io_map[f"{k}_Q"][0]), v)

    def test_sequential_unroll_add_flop_outputs(self):
        c = cg.from_lib("s27")
        num_unroll = 4
        cu, io_map = cg.tx.sequential_unroll(
            c, num_unroll, "D", "Q", ["CK"], add_flop_outputs=True,
        )
        self.assertEqual(
            len(cu.inputs()), (len(c.inputs()) - 1) * num_unroll + len(c.blackboxes)
        )
        self.assertEqual(
            len(cu.outputs()), (len(c.outputs()) + len(c.blackboxes)) * num_unroll
        )

    def test_unroll(self):
        c = cg.Circuit()
        c.add("i0", "input")
        c.add("i1", "input")
        c.add("ff0_Q", "input")

        c.add("g0", "xor", fanin=["i0", "i1", "ff0_Q"])
        c.add("ff0_D", "xnor", fanin=["g0", "i1"], output=True)
        c.add("o0", "and", fanin=["g0", "i0"], output=True)

        prefix = "unrolled"
        uc = cg.Circuit()

        num_copies = 2
        for idx in range(num_copies):
            uc.add(f"i0_{prefix}_{idx}", "input")
            uc.add(f"i1_{prefix}_{idx}", "input")
            if idx == 0:
                uc.add(f"ff0_Q_{prefix}_{idx}", "input")
            else:
                uc.add(f"ff0_Q_{prefix}_{idx}", "buf")

            uc.add(
                f"g0_{prefix}_{idx}",
                "xor",
                fanin=[
                    f"i0_{prefix}_{idx}",
                    f"i1_{prefix}_{idx}",
                    f"ff0_Q_{prefix}_{idx}",
                ],
            )
            uc.add(
                f"ff0_D_{prefix}_{idx}",
                "xnor",
                fanin=[f"g0_{prefix}_{idx}", f"i1_{prefix}_{idx}"],
                output=True,
            )
            uc.add(
                f"o0_{prefix}_{idx}",
                "and",
                fanin=[f"g0_{prefix}_{idx}", f"i0_{prefix}_{idx}"],
                output=True,
            )

            if idx > 0:
                uc.connect(f"ff0_D_{prefix}_{idx-1}", f"ff0_Q_{prefix}_{idx}")

        unroll_uc, io_map = cg.tx.unroll(
            c, num_copies, {"ff0_D": "ff0_Q"}, prefix=prefix
        )
        self.assertSetEqual(uc.inputs(), unroll_uc.inputs())
        self.assertSetEqual(uc.outputs(), unroll_uc.outputs())
        m = cg.tx.miter(uc, unroll_uc)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_miter(self):
        # check self equivalence
        m = cg.tx.miter(self.s27)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

        # check equivalence with incorrect copy
        m = cg.tx.miter(self.s27, self.s27m)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertTrue(different_output)

        # check equivalence with free inputs
        startpoints = self.s27.startpoints() - set(["clk"])
        startpoints.pop()
        m = cg.tx.miter(self.s27, startpoints=startpoints)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertTrue(different_output)

    def test_subcircuit(self):
        c17 = cg.from_lib("c17")
        sc = cg.tx.subcircuit(c17, c17.transitive_fanin("N22") | {"N22"})
        self.assertSetEqual(
            sc.nodes(), {"N22", "N10", "N16", "N1", "N3", "N2", "N11", "N6"},
        )
        self.assertSetEqual(
            sc.edges(),
            {
                ("N10", "N22"),
                ("N16", "N22"),
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
        s = cg.tx.syn(self.s27, "yosys", suppress_output=True)
        m = cg.tx.miter(self.s27, s)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys_io(self):
        tmpdir = tempfile.mkdtemp(prefix=f"circuitgraph_test_syn_yosys_io")
        s = cg.tx.syn(
            self.s27,
            "yosys",
            suppress_output=True,
            pre_syn_file=f"{tmpdir}/pre_syn.v",
            post_syn_file=f"{tmpdir}/post_syn.v",
            working_dir=tmpdir,
        )
        c0 = cg.from_file(f"{tmpdir}/pre_syn.v")
        c1 = cg.from_file(f"{tmpdir}/post_syn.v")
        m = cg.tx.miter(c0, c1)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        shutil.rmtree(tmpdir)

    @unittest.skipIf(shutil.which("yosys") == None, "Yosys is not installed")
    def test_syn_yosys_exists(self):
        with tempfile.NamedTemporaryFile(
            prefix="circuitgraph_synthesis_test", suffix=".v", mode="w"
        ) as tmp_in:
            tmp_in.write("module test(a, b, c);\n")
            tmp_in.write("input a, b;\n")
            tmp_in.write("output c;\n")
            tmp_in.write("nand g_n(c, a, b);\n")
            tmp_in.write("endmodule\n")
            tmp_in.flush()

            c = cg.tx.syn(
                cg.Circuit(name="test"),
                "yosys",
                suppress_output=True,
                pre_syn_file=tmp_in.name,
                verilog_exists=True,
            )
            c2 = cg.Circuit()
            c2.add("a", "input")
            c2.add("b", "input")
            c2.add("c", "nand", fanin=["a", "b"], fanout=["c"], output=True)
            m = cg.tx.miter(c, c2)
            live = cg.sat.solve(m)
            self.assertTrue(live)
            different_output = cg.sat.solve(m, assumptions={"sat": True})
            self.assertFalse(different_output)

    @unittest.skipUnless(
        "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ, "Genus synthesis not setup"
    )
    def test_syn_genus(self):
        tmpdir = tempfile.mkdtemp(prefix=f"circuitgraph_test_syn_genus")
        s = cg.tx.syn(self.s27, "genus", suppress_output=True, working_dir=tmpdir)
        m = cg.tx.miter(self.s27, s)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        shutil.rmtree(tmpdir)

    @unittest.skipUnless(
        "CIRCUITGRAPH_GENUS_LIBRARY_PATH" in os.environ, "Genus synthesis not setup"
    )
    def test_syn_genus_io(self):
        tmpdir = tempfile.mkdtemp(prefix=f"circuitgraph_test_syn_genus_io")
        s = cg.tx.syn(
            self.s27,
            "genus",
            suppress_output=True,
            pre_syn_file=f"{tmpdir}/pre_syn.v",
            post_syn_file=f"{tmpdir}/post_syn.v",
            working_dir=tmpdir,
        )
        c0 = cg.from_file(f"{tmpdir}/pre_syn.v")
        c1 = cg.from_file(f"{tmpdir}/post_syn.v")
        m = cg.tx.miter(c0, c1)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        shutil.rmtree(tmpdir)

    @unittest.skipUnless(
        "CIRCUITGRAPH_DC_LIBRARY_PATH" in os.environ, "DC synthesis not setup"
    )
    def test_syn_dc(self):
        tmpdir = tempfile.mkdtemp(prefix=f"circuitgraph_test_syn_dc")
        s = cg.tx.syn(self.s27, "dc", suppress_output=True, working_dir=tmpdir)
        m = cg.tx.miter(self.s27, s)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        shutil.rmtree(tmpdir)

    def test_ternary(self):
        # Test AND gate behavior
        c = cg.Circuit()
        c.add("i0", "input")
        c.add("i1", "input")
        c.add("g0", "and", fanin=["i0", "i1"], output=True)

        ct, mapping = cg.tx.ternary(c)

        assumptions = {
            "i0": True,
            mapping["i0"]: False,
            "i1": True,
            mapping["i1"]: False,
        }
        result = cg.sat.solve(ct, assumptions)
        self.assertTrue(result["g0"])
        self.assertFalse(result[mapping["g0"]])

        assumptions[mapping["i1"]] = True
        result = cg.sat.solve(ct, assumptions)
        self.assertTrue(result[mapping["g0"]])

        assumptions["i0"] = False
        result = cg.sat.solve(ct, assumptions)
        self.assertFalse(result["g0"])
        self.assertFalse(result[mapping["g0"]])

        # Test original circuit equivalence
        c = cg.from_lib("c880")
        ct, mapping = cg.tx.ternary(c)
        for i in c.inputs():
            ct.set_type(mapping[i], "0")
        m = cg.tx.miter(c, ct)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(
            m,
            assumptions={
                **{"sat": True},
                **{f"c1_{mapping[i]}": False for i in c.outputs()},
            },
        )
        self.assertFalse(different_output)

        # Sensitize inputs, set to X, make sure output is X
        for output in c.outputs():
            subc = cg.tx.subcircuit(c, {output} | c.transitive_fanin(output))
            # Make sure we're sensitizing to this output
            for n in subc:
                if n != output:
                    subc.set_output(n, False)
            subc_t, mapping = cg.tx.ternary(subc)
            for inp in subc.inputs():
                pattern = cg.props.sensitize(subc, inp)
                result = cg.sat.solve(
                    subc_t, {**pattern, **{mapping[inp]: True, inp: True}}
                )
                self.assertTrue(result[mapping[output]])

    def test_sensitivity_transform(self):
        # pick random node and input value
        n = choice(tuple(self.s27.nodes() - self.s27.startpoints()))
        nstartpoints = self.s27.startpoints(n)
        while len(nstartpoints) < 1:
            n = choice(tuple(self.s27.nodes() - self.s27.startpoints()))
            nstartpoints = self.s27.startpoints(n)
        input_val = {i: randint(0, 1) for i in nstartpoints}

        # build sensitivity circuit
        s = cg.tx.sensitivity_transform(self.s27, n)

        # find sensitivity at an input
        model = cg.sat.solve(s, input_val)
        sen_s = sum(model[o] for o in s.outputs() if "dif_out" in o)

        # try inputs Hamming distance 1 away
        output_val = cg.sat.solve(self.s27, input_val)[n]
        sen_sim = 0
        for i in nstartpoints:
            neighbor_input_val = {
                g: v if g != i else not v for g, v in input_val.items()
            }
            neighbor_output_val = cg.sat.solve(self.s27, neighbor_input_val)[n]
            if neighbor_output_val != output_val:
                sen_sim += 1

        # check answer
        self.assertEqual(sen_s, sen_sim)

        # find input with sensitivity
        vs = cg.utils.int_to_bin(sen_s, cg.utils.clog2(len(nstartpoints) + 1), True)
        model = cg.sat.solve(s, {f"sen_out_{i}": v for i, v in enumerate(vs)})

        input_val = {i: model[i] for i in nstartpoints}

        # try inputs Hamming distance 1 away
        output_val = cg.sat.solve(self.s27, input_val)[n]
        sen_sim = 0
        for i in nstartpoints:
            neighbor_input_val = {
                g: v if g != i else not v for g, v in input_val.items()
            }
            neighbor_output_val = cg.sat.solve(self.s27, neighbor_input_val)[n]
            if neighbor_output_val != output_val:
                sen_sim += 1

        # check answer
        self.assertEqual(sen_s, sen_sim)

    def test_limit_fanin(self):
        k = 2
        c = self.c432
        ck = cg.tx.limit_fanin(c, k)

        # check conversion
        m = cg.tx.miter(c, ck)
        self.assertFalse(cg.sat.solve(m, assumptions={"sat": True}))

        for n in ck:
            self.assertTrue(len(ck.fanin(n)) <= k)

    def test_acyclic_unroll(self):
        c = cg.Circuit()
        c.add("a", "input")

        c.add("g1", "and", fanin=["a"], output=True)
        c.add("g2", "buf", fanin=["g1"])
        # Add feedback edge
        c.connect("g2", "g1")

        self.assertTrue(c.is_cyclic())

        acyc = cg.tx.acyclic_unroll(c)
        self.assertFalse(acyc.is_cyclic())

        self.assertSetEqual(c.outputs(), acyc.outputs())
        self.assertEqual(len(acyc.inputs()), 2)
        self.assertTrue("a" in acyc.inputs())

    def test_supergates(self):
        c = cg.Circuit()
        for i in range(1, 7):
            c.add(f"i{i}", "input")

        c.add("g7", "nand", fanin=["i1", "i2"])
        c.add("g8", "nand", fanin=["i3", "i4"])
        c.add("g9", "nand", fanin=["i5", "i6"])
        c.add("g10", "not", fanin=["i6"])
        c.add("g11", "nand", fanin=["g7", "g8"])
        c.add("g12", "nand", fanin=["g9", "g10"])
        c.add("g13", "nand", fanin=["g11", "g12"])
        c.add("i14", "input")
        c.add("g15", "nand", fanin=["g13", "i14"])
        c.add("g16", "nand", fanin=["g12", "g13"])
        c.add("i17", "input")
        c.add("g18", "nand", fanin=["g15", "i17"])
        c.add("g19", "nand", fanin=["g16", "g18"], output=True)

        scs_per_output, g_per_output = cg.tx.supergates(c)
        for o, g in g_per_output.items():
            for node in g:
                self.assertTrue(len(list(g.successors(node))) <= 1)
