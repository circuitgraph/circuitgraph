import os
import unittest

import circuitgraph as cg


class TestIO(unittest.TestCase):
    def setUp(self):
        self.test_path = f"{os.path.dirname(__file__)}/../circuitgraph/netlists/tests/"
        self.bbs = [cg.BlackBox("ff", ["CK", "D"], ["Q"])]

    def test_bench(self):
        g = cg.from_lib("b17_C")
        self.assertEqual(len(g), 2942)
        self.assertSetEqual(g.fanin("n2905"), {"n2516", "n2904"})
        self.assertSetEqual(g.fanin("out789"), {"n2942"})
        self.assertSetEqual(g.fanout("in382"), {"n2484"})

        self.assertEqual(g.type("n2905"), "and")
        self.assertEqual(g.type("out789"), "not")
        self.assertTrue(g.is_output("out789"))
        self.assertEqual(g.type("in382"), "input")

    def test_bench_output(self):
        g = cg.from_lib("b17_C")
        g2 = cg.io.bench_to_circuit(cg.io.circuit_to_bench(g), g.name)
        self.assertSetEqual(g.inputs(), g2.inputs())
        self.assertSetEqual(g.outputs(), g2.outputs())

        m = cg.tx.miter(g, g2)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_verilog(self):
        g = cg.from_file(f"{self.test_path}/test_correct_io.v")

        self.assertSetEqual(
            g.nodes(),
            {
                "G1",
                "G2",
                "G3",
                "G4",
                "G5_0",
                "G5_1",
                "G17",
                "G18",
                "G19",
                "G20",
                "G21",
                "G22_0",
                "G22_1",
                "G8_0",
                "G8_1",
                "and_G1_G2",
                "tie_0",
                "tie_1",
                "not_G2",
                "xor_G3_G4",
                "and_G8_0_G5_0",
                "xor_G17_and_G8_0_G5_0",
                "and_and_G1_G2_xor_G3_G4",
                "and_G1_or_not_G2_tie_1",
                "or_not_G2_tie_1",
            },
        )
        self.assertSetEqual(g.fanin("G8_0"), {"G1", "G3"})
        self.assertSetEqual(g.fanin("G17"), {"G8_1", "tie_1"})
        self.assertEqual(g.type("G8_1"), "buf")
        self.assertEqual(g.fanin("G8_1"), {"tie_1"})

        self.assertEqual(g.type("G8_0"), "nand")
        self.assertEqual(g.type("G17"), "nor")
        self.assertEqual(g.type("G18"), "and")
        self.assertTrue(g.is_output("G18"))
        self.assertEqual(g.type("G22_0"), "xor")
        self.assertTrue(g.is_output("G22_0"))
        self.assertEqual(g.type("tie_1"), "1")
        self.assertEqual(g.type("tie_0"), "0")

        self.assertSetEqual(g.fanin("G19"), {"and_and_G1_G2_xor_G3_G4"})
        self.assertSetEqual(
            g.fanin("and_and_G1_G2_xor_G3_G4"), {"and_G1_G2", "xor_G3_G4"}
        )
        self.assertSetEqual(g.fanin("and_G1_G2"), {"G1", "G2"})
        self.assertSetEqual(g.fanin("xor_G3_G4"), {"G3", "G4"})
        self.assertSetEqual(g.fanin("G20"), {"xor_G17_and_G8_0_G5_0"})
        self.assertSetEqual(
            g.fanin("xor_G17_and_G8_0_G5_0"), {"G17", "and_G8_0_G5_0"},
        )
        self.assertSetEqual(g.fanin("and_G8_0_G5_0"), {"G8_0", "G5_0"})
        self.assertSetEqual(g.fanin("G22_1"), {"and_G1_or_not_G2_tie_1"})
        self.assertSetEqual(
            g.fanin("and_G1_or_not_G2_tie_1"), {"G1", "or_not_G2_tie_1"}
        )
        self.assertSetEqual(g.fanin("or_not_G2_tie_1"), {"not_G2", "tie_1"})
        self.assertSetEqual(g.fanin("not_G2"), {"G2"})

        self.assertSetEqual(g.inputs(), {"G1", "G2", "G3", "G4", "G5_0", "G5_1"})
        self.assertSetEqual(
            g.outputs(), {"G17", "G18", "G19", "G20", "G21", "G22_0", "G22_1"},
        )

    def test_fast_verilog(self):
        g = cg.from_file(f"{self.test_path}/../c432.v")
        gf = cg.from_file(f"{self.test_path}/../c432.v", fast=True)
        self.assertSetEqual(g.inputs(), gf.inputs())
        self.assertSetEqual(g.outputs(), gf.outputs())
        self.assertSetEqual(g.nodes(), gf.nodes())
        self.assertSetEqual(g.edges(), gf.edges())
        m = cg.tx.miter(g, gf)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_incorrect_file_type(self):
        self.assertRaises(ValueError, cg.from_file, "setup.py")

    def test_blackbox_io(self):
        c = cg.from_file(f"{self.test_path}/test_blackbox_io_0.v", blackboxes=self.bbs)
        self.assertSetEqual(c.inputs(), {"clk", "i0", "i1"})
        self.assertSetEqual(c.outputs(), {"o0"})
        self.assertSetEqual(
            c.nodes(),
            c.inputs() | c.outputs() | {"w0", "w1", "ff0.D", "ff0.CK", "ff0.Q"},
        )
        self.assertDictEqual(c.blackboxes, {"ff0": self.bbs[0]})

        v = cg.io.circuit_to_verilog(c)
        c2 = cg.io.verilog_to_circuit(v, c.name, blackboxes=self.bbs)
        m = cg.tx.miter(cg.tx.strip_blackboxes(c), cg.tx.strip_blackboxes(c2))
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

        c = cg.from_file(f"{self.test_path}/test_blackbox_io_1.v", blackboxes=self.bbs)
        self.assertSetEqual(c.inputs(), {"clk", "i0"})
        self.assertSetEqual(c.outputs(), {"o0"})
        self.assertSetEqual(
            c.nodes(), c.inputs() | c.outputs() | {"ff0.D", "ff0.CK", "ff0.Q"}
        )
        self.assertDictEqual(c.blackboxes, {"ff0": self.bbs[0]})

        v = cg.io.circuit_to_verilog(c)
        c2 = cg.io.verilog_to_circuit(v, c.name, blackboxes=self.bbs)
        m = cg.tx.miter(cg.tx.strip_blackboxes(c), cg.tx.strip_blackboxes(c2))
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_blackbox_io_fast(self):
        c = cg.from_file(
            f"{self.test_path}/test_blackbox_io_0.v", blackboxes=self.bbs, fast=True
        )
        self.assertSetEqual(c.inputs(), {"clk", "i0", "i1"})
        self.assertSetEqual(c.outputs(), {"o0"})
        self.assertSetEqual(
            c.nodes(),
            c.inputs() | c.outputs() | {"w0", "w1", "ff0.D", "ff0.CK", "ff0.Q"},
        )
        self.assertDictEqual(c.blackboxes, {"ff0": self.bbs[0]})

        v = cg.io.circuit_to_verilog(c)
        c2 = cg.io.verilog_to_circuit(v, c.name, blackboxes=self.bbs, fast=True)
        m = cg.tx.miter(cg.tx.strip_blackboxes(c), cg.tx.strip_blackboxes(c2))
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

        c = cg.from_file(
            f"{self.test_path}/test_blackbox_io_1.v", blackboxes=self.bbs, fast=True
        )
        self.assertSetEqual(c.inputs(), {"clk", "i0"})
        self.assertSetEqual(c.outputs(), {"o0"})
        self.assertSetEqual(
            c.nodes(), c.inputs() | c.outputs() | {"ff0.D", "ff0.CK", "ff0.Q"}
        )
        self.assertDictEqual(c.blackboxes, {"ff0": self.bbs[0]})

        v = cg.io.circuit_to_verilog(c)
        c2 = cg.io.verilog_to_circuit(v, c.name, blackboxes=self.bbs, fast=True)
        m = cg.tx.miter(cg.tx.strip_blackboxes(c), cg.tx.strip_blackboxes(c2))
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_verilog_output(self):
        for g in [
            cg.from_file(
                f"{self.test_path}/test_correct_io.v",
                name="test_module_bb",
                blackboxes=self.bbs,
            ),
            cg.from_file(f"{self.test_path}/test_correct_io.v", name="test_correct_io"),
        ]:
            g2 = cg.io.verilog_to_circuit(
                cg.io.circuit_to_verilog(g), g.name, blackboxes=self.bbs
            )
            m = cg.tx.miter(cg.tx.strip_blackboxes(g), cg.tx.strip_blackboxes(g2))
            live = cg.sat.solve(m)
            self.assertTrue(live)
            different_output = cg.sat.solve(m, assumptions={"sat": True})
            self.assertFalse(different_output)
