import unittest
import os

import circuitgraph as cg
from circuitgraph.transform import miter
from circuitgraph.sat import sat


class TestIO(unittest.TestCase):
    def setUp(self):
        self.test_path = f"{os.path.dirname(__file__)}/../netlists/tests/"
        self.bbs = [cg.BlackBox("ff", ["CK", "D"], ["Q"])]

    def test_bench(self):
        g = cg.from_lib(f"b17_C")
        self.assertEqual(len(g), 2943)
        self.assertSetEqual(g.fanin("n2905"), set(["n2516", "n2904"]))
        self.assertSetEqual(g.fanin("out789"), set(["out789_driver"]))
        self.assertSetEqual(g.fanin("out789_driver"), set(["n2942"]))
        self.assertSetEqual(g.fanout("in382"), set(["n2484"]))

        self.assertEqual(g.type("n2905"), "and")
        self.assertEqual(g.type("out789"), "output")
        self.assertEqual(g.type("out789_driver"), "not")
        self.assertEqual(g.type("in382"), "input")

    def test_bench_output(self):
        g = cg.from_lib(f"b17_C")
        g2 = cg.bench_to_circuit(cg.circuit_to_bench(g), g.name)

        m = miter(g, g2)
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        if different_output:
            import code

            code.interact(local=dict(**globals(), **locals()))
        self.assertFalse(different_output)

    def test_verilog(self):
        g = cg.from_file(f"{self.test_path}/test_correct_io.v")

        self.assertSetEqual(
            g.nodes(),
            set(
                [
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
                    "G19_driver",
                    "G18_driver",
                    "G20_driver",
                    "G21_driver",
                    "G17_driver",
                    "and_G1_G2",
                    "tie0",
                    "tie1",
                    "not_G2",
                    "xor_G3_G4",
                    "and_G8_0_G5_0",
                    "xor_G17_and_G8_0_G5_0",
                    "and_and_G1_G2_xor_G3_G4",
                    "and_G1_or_not_G2_tie1",
                    "or_not_G2_tie1",
                    "G22_0_driver",
                    "G22_1_driver",
                ]
            ),
        )
        self.assertSetEqual(g.fanin("G8_0"), set(["G1", "G3"]))
        self.assertSetEqual(g.fanin("G17"), set(["G17_driver"]))
        self.assertSetEqual(g.fanin("G18"), set(["G18_driver"]))
        self.assertSetEqual(g.fanin("G17_driver"), set(["G8_1", "tie1"]))
        self.assertEqual(g.type("G8_1"), "buf")
        self.assertEqual(g.fanin("G8_1"), set(["tie1"]))

        self.assertEqual(g.type("G8_0"), "nand")
        self.assertEqual(g.type("G17_driver"), "nor")
        self.assertEqual(g.type("G18_driver"), "and")
        self.assertEqual(g.type("G18"), "output")
        self.assertEqual(g.type("G22_0"), "output")
        self.assertEqual(g.type("G22_0_driver"), "xor")
        self.assertEqual(g.type("tie1"), "1")
        self.assertEqual(g.type("tie0"), "0")

        self.assertSetEqual(g.fanin("G19_driver"), set(["and_and_G1_G2_xor_G3_G4"]))
        self.assertSetEqual(
            g.fanin("and_and_G1_G2_xor_G3_G4"), set(["and_G1_G2", "xor_G3_G4"])
        )
        self.assertSetEqual(g.fanin("and_G1_G2"), set(["G1", "G2"]))
        self.assertSetEqual(g.fanin("xor_G3_G4"), set(["G3", "G4"]))
        self.assertSetEqual(g.fanin("G20_driver"), set(["xor_G17_and_G8_0_G5_0"]))
        self.assertSetEqual(
            g.fanin("xor_G17_and_G8_0_G5_0"), set(["G17_driver", "and_G8_0_G5_0"]),
        )
        self.assertSetEqual(g.fanin("and_G8_0_G5_0"), set(["G8_0", "G5_0"]))
        self.assertSetEqual(g.fanin("G22_1_driver"), set(["and_G1_or_not_G2_tie1"]))
        self.assertSetEqual(
            g.fanin("and_G1_or_not_G2_tie1"), set(["G1", "or_not_G2_tie1"])
        )
        self.assertSetEqual(g.fanin("or_not_G2_tie1"), set(["not_G2", "tie1"]))
        self.assertSetEqual(g.fanin("not_G2"), set(["G2"]))

        self.assertSetEqual(g.inputs(), set(["G1", "G2", "G3", "G4", "G5_0", "G5_1"]))
        self.assertSetEqual(
            g.outputs(), set(["G17", "G18", "G19", "G20", "G21", "G22_0", "G22_1"]),
        )

    def test_incorrect_file_type(self):
        self.assertRaises(ValueError, cg.from_file, "setup.py")

    def test_verilog_output(self):
        for g in [
            cg.from_file(
                f"{self.test_path}/test_correct_io.v",
                name="test_module_bb",
                blackboxes=self.bbs,
            ),
            cg.from_file(f"{self.test_path}/test_correct_io.v", name="test_correct_io"),
        ]:
            g2 = cg.verilog_to_circuit(
                cg.circuit_to_verilog(g), g.name, blackboxes=self.bbs
            )
            m = miter(cg.strip_blackboxes(g), cg.strip_blackboxes(g2))
            live = sat(m)
            self.assertTrue(live)
            different_output = sat(m, assumptions={"sat": True})
            if different_output:
                import code

                code.interact(local=dict(**globals(), **locals()))
            self.assertFalse(different_output)

    def test_verilog_incorrect_output(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "fake_gate", fanin=["a", "b"])
        self.assertRaises(ValueError, cg.circuit_to_verilog, c)
