import os
import random
import shutil
import tempfile
import unittest
from functools import reduce
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
        cu, _ = cg.tx.sequential_unroll(c, num_unroll, "D", "Q", ["clk"])
        self.assertEqual(
            len(cu.inputs()), (len(c.inputs()) - 1) * num_unroll + len(c.blackboxes)
        )
        self.assertEqual(len(cu.outputs()), len(c.outputs()) * num_unroll)

    def test_sequential_unroll_initial_values(self):
        c = cg.from_lib("s27")
        num_unroll = 4
        initial_values = {f: str(random.getrandbits(1)) for f in c.blackboxes}
        cu, io_map = cg.tx.sequential_unroll(
            c,
            num_unroll,
            "D",
            "Q",
            ["CK"],
            initial_values=initial_values,
        )
        self.assertEqual(len(cu.inputs()), (len(c.inputs()) - 1) * num_unroll)
        self.assertEqual(len(cu.outputs()), len(c.outputs()) * num_unroll)
        for k, v in initial_values.items():
            self.assertEqual(cu.type(io_map[f"{k}_Q"][0]), v)

    def test_sequential_unroll_add_flop_outputs(self):
        c = cg.from_lib("s27")
        num_unroll = 4
        cu, _ = cg.tx.sequential_unroll(
            c,
            num_unroll,
            "D",
            "Q",
            ["CK"],
            add_flop_outputs=True,
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

        unroll_uc, _ = cg.tx.unroll(c, num_copies, {"ff0_D": "ff0_Q"}, prefix=prefix)
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
        startpoints = self.s27.startpoints() - {"clk"}
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
            sc.nodes(),
            {"N22", "N10", "N16", "N1", "N3", "N2", "N11", "N6"},
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

    @unittest.skipIf(shutil.which("yosys") is None, "Yosys is not installed")
    def test_syn_yosys(self):
        s = cg.tx.syn(self.s27, "yosys", suppress_output=True)
        m = cg.tx.miter(self.s27, s)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    @unittest.skipIf(shutil.which("yosys") is None, "Yosys is not installed")
    def test_syn_yosys_io(self):
        tmpdir = tempfile.mkdtemp(prefix="circuitgraph_test_syn_yosys_io")
        _ = cg.tx.syn(
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

    @unittest.skipIf(shutil.which("yosys") is None, "Yosys is not installed")
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
        tmpdir = tempfile.mkdtemp(prefix="circuitgraph_test_syn_genus")
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
        tmpdir = tempfile.mkdtemp(prefix="circuitgraph_test_syn_genus_io")
        _ = cg.tx.syn(
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
        tmpdir = tempfile.mkdtemp(prefix="circuitgraph_test_syn_dc")
        s = cg.tx.syn(self.s27, "dc", suppress_output=True, working_dir=tmpdir)
        m = cg.tx.miter(self.s27, s)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        shutil.rmtree(tmpdir)

    @unittest.skipIf(shutil.which("yosys") is None, "Yosys is not installed")
    def test_aig(self):
        aig = cg.tx.aig(self.c432)
        m = cg.tx.miter(self.c432, aig)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)
        for node in aig:
            self.assertTrue(aig.type(node) in ["input", "and", "not"])
            if aig.type(node) == "and":
                self.assertTrue(len(aig.fanin(node)) == 2)
            elif aig.type(node) == "not":
                self.assertTrue(len(aig.fanin(node)) == 1)

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

    def test_limit_fanout(self):
        k = 2
        c = cg.from_lib("c1355")

        any_greater = False
        for n in c:
            if len(c.fanout(n)) > k:
                any_greater = True
                break
        self.assertTrue(any_greater)

        ck = cg.tx.limit_fanout(c, k)

        # check conversion
        m = cg.tx.miter(c, ck)
        self.assertFalse(cg.sat.solve(m, assumptions={"sat": True}))

        for n in ck:
            self.assertTrue(len(ck.fanout(n)) <= k)

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

    def test_supergates_example(self):
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

        sg7 = cg.Circuit("sg7")
        sg7.add("i1", "input")
        sg7.add("i2", "input")
        sg7.add("g7", "nand", fanin=["i1", "i2"], output=True)

        sg8 = cg.Circuit("sg8")
        sg8.add("i3", "input")
        sg8.add("i4", "input")
        sg8.add("g8", "nand", fanin=["i3", "i4"], output=True)

        sg11 = cg.Circuit("sg11")
        sg11.add("g7", "input")
        sg11.add("g8", "input")
        sg11.add("g11", "nand", fanin=["g7", "g8"], output=True)

        sg12 = cg.Circuit("sg12")
        sg12.add("i5", "input")
        sg12.add("i6", "input")
        sg12.add("g9", "nand", fanin=["i5", "i6"])
        sg12.add("g10", "not", fanin="i6")
        sg12.add("g12", "nand", fanin=["g9", "g10"], output=True)

        sg19 = cg.Circuit("sg19")
        sg19.add("g11", "input")
        sg19.add("g12", "input")
        sg19.add("g13", "nand", fanin=["g11", "g12"])
        sg19.add("i14", "input")
        sg19.add("g15", "nand", fanin=["g13", "i14"])
        sg19.add("g16", "nand", fanin=["g12", "g13"])
        sg19.add("i17", "input")
        sg19.add("g18", "nand", fanin=["g15", "i17"])
        sg19.add("g19", "nand", fanin=["g16", "g18"], output=True)

        supergates = cg.tx.supergates(c)
        found_supergates = set()
        all_supergates = {sg7, sg8, sg11, sg12, sg19}

        def potential_supergates():
            remaining_supergates = all_supergates - found_supergates
            if {sg7, sg8} & remaining_supergates:
                remaining_supergates -= {sg11}
            if {sg7, sg8, sg12} & remaining_supergates:
                remaining_supergates -= {sg19}
            return remaining_supergates

        def match_circuits(c0, c1):
            if c0.inputs() != c1.inputs():
                return False
            if c0.outputs() != c1.outputs():
                return False
            if c0.nodes() != c1.nodes():
                return False
            if c0.edges() != c1.edges():
                return False
            return True

        for supergate in supergates:
            found = False
            for sg in potential_supergates():
                if match_circuits(supergate, sg):
                    found_supergates.add(sg)
                    found = True
                    break
            self.assertTrue(
                found,
                f"Supergate {supergate.outputs().pop()}\n"
                "cannot find match in potential supergates: "
                f"{[i.name for i in potential_supergates()]}",
            )

    def test_supergates(self):
        c = cg.from_lib("c880")
        c = cg.tx.limit_fanin(c, 2)
        supergates = cg.tx.supergates(c)
        self.assertSetEqual(
            reduce(lambda a, b: a | b, [s.nodes() for s in supergates]), c.nodes()
        )
        for supergate in supergates:
            output = supergate.outputs().pop()
            # Check if all predecessor nodes are in supergate
            self.assertTrue(
                c.fanin(output).issubset(supergate.nodes()),
                f"output: {output}\nfanin: {c.fanin(output)}\n"
                f"nodes: {supergate.nodes()}",
            )
            # Check all node's predecessors are in supergate if one is
            for node in supergate.nodes():
                if any(n in supergate for n in c.fanin(node)):
                    self.assertTrue(c.fanin(node).issubset(supergate.nodes()))
            # Check all inputs are disjoint
            for n0 in supergate.inputs():
                for n1 in supergate.inputs() - {n0}:
                    self.assertFalse(c.transitive_fanin(n0) & c.transitive_fanin(n1))

    def test_insert_registers(self):
        c = cg.from_lib("c880")
        c_reg = cg.tx.insert_registers(c, 2, q_suffix="_cg_insert_reg_q_")
        # FIXME: Simulate to check if c_reg still behaves like c
