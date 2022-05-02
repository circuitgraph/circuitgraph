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

        c = cg.Circuit()
        c.add("G1", "input")
        c.add("G2", "input")
        c.add("G3", "input")
        c.add("G4", "input")
        c.add("G5_0", "input")
        c.add("G5_1", "input")

        c.add("tie_1", "1")
        c.add("tie_0", "0")

        c.add("G8_0", "nand", fanin=["G1", "G3"])
        c.add("G8_1", "buf", fanin="tie_1")
        c.add("G17", "nor", fanin=["G8_1", "tie_1"], output=True)
        c.add("G18", "and", fanin=["G2", "G5_0"], output=True)
        c.add("G22_0", "xor", fanin=["G5_1", "G4"], output=True)

        c.add("G3_xor_G4", "xor", fanin=["G3", "G4"])
        c.add("G2_and_G3_xor_G4", "and", fanin=["G2", "G3_xor_G4"])
        c.add("G19", "and", fanin=["G1", "G2_and_G3_xor_G4"], output=True)
        c.add("G8_0_and_G5_0", "and", fanin=["G8_0", "G5_0"])
        c.add("G20", "xor", fanin=["G17", "G8_0_and_G5_0"], output=True)
        c.add("G21", "buf", fanin="tie_0", output=True)
        c.add("G22_1", "buf", fanin=["G1"], output=True)

        m = cg.tx.miter(g, c)
        live = cg.sat.solve(m)
        self.assertTrue(live)
        different_output = cg.sat.solve(m, assumptions={"sat": True})
        self.assertFalse(different_output)

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
