import unittest

import circuitgraph as cg
from circuitgraph.io import verilog_to_circuit, circuit_to_verilog
from circuitgraph.transform import miter
from circuitgraph.sat import sat


class TestIO(unittest.TestCase):
    # def test_bench(self):
    #     c17 = cg.from_lib("b22_C")

    def test_incorrect_module(self):
        self.assertRaises(
            ValueError, cg.from_lib, "test_correct_io", name="incorrect_name"
        )

    def test_verilog_comb(self):
        for g in [
            cg.from_lib("test_correct_io", name="test_module_0"),
            cg.from_lib("test_correct_io", name="test_module_1"),
        ]:
            self.assertSetEqual(
                g.nodes(),
                set(
                    [
                        "G1",
                        "G2",
                        "G3",
                        "G4",
                        "\\G5[0]",
                        "\\G5[1]",
                        "G17",
                        "G18",
                        "G19",
                        "G20",
                        "G21",
                        "\\G22[0]",
                        "\\G22[1]",
                        "\\G8[0]",
                        "\\G8[1]",
                        "not_G2",
                        "xor_G3_G4",
                        "and_G1_G2",
                        "1",
                        "0",
                        "\\and_G8[0]_G5[0]",
                        "or_not_G2_1",
                    ]
                ),
            )
            self.assertSetEqual(g.fanin("\\G8[0]"), set(["G1", "G3"]))
            self.assertSetEqual(g.fanin("G17"), set(["\\G8[1]", "1"]))
            self.assertSetEqual(g.fanin("G18"), set(["G2", "\\G5[0]"]))
            self.assertSetEqual(g.fanin("\\G22[0]"), set(["\\G5[1]", "G4"]))

            self.assertEqual(g.type("\\G8[0]"), "nand")
            self.assertEqual(g.type("G17"), "nor")
            self.assertEqual(g.type("G18"), "and")
            self.assertEqual(g.type("\\G22[0]"), "xor")
            self.assertEqual(g.type("0"), "0")
            self.assertEqual(g.type("1"), "1")

            self.assertSetEqual(g.fanin("G19"), set(["and_G1_G2", "xor_G3_G4"]))
            self.assertSetEqual(g.fanin("and_G1_G2"), set(["G1", "G2"]))
            self.assertSetEqual(g.fanin("xor_G3_G4"), set(["G3", "G4"]))
            self.assertSetEqual(g.fanin("G20"), set(["G17", "\\and_G8[0]_G5[0]"]))
            self.assertSetEqual(
                g.fanin("\\and_G8[0]_G5[0]"), set(["\\G8[0]", "\\G5[0]"])
            )
            self.assertSetEqual(g.fanin("\\G22[1]"), set(["G1", "or_not_G2_1"]))
            self.assertSetEqual(g.fanin("or_not_G2_1"), set(["not_G2", "1"]))
            self.assertSetEqual(g.fanin("not_G2"), set(["G2"]))

            self.assertSetEqual(
                g.inputs(), set(["G1", "G2", "G3", "G4", "\\G5[0]", "\\G5[1]"])
            )
            self.assertSetEqual(
                g.outputs(),
                set(["G17", "G18", "G19", "G20", "G21", "\\G22[0]", "\\G22[1]"]),
            )

    def test_verilog_seq(self):
        g = cg.from_lib("test_correct_io", name="test_module_2")
        self.assertSetEqual(
            g.nodes(),
            set(
                [
                    "clk",
                    "G0",
                    "G1",
                    "\\G2[0]",
                    "\\G2[1]",
                    "\\G18[0]",
                    "\\G18[1]",
                    "G3",
                    "G4",
                    "G5",
                ]
            ),
        )
        self.assertSetEqual(g.fanin("G4"), set(["G3"]))
        self.assertSetEqual(g.fanin("G5"), set(["\\G2[0]"]))
        self.assertSetEqual(g.fanin("\\G18[0]"), set(["G5"]))
        self.assertSetEqual(set(g.clk(["G4", "G5", "\\G18[0]"])), set(["clk"]))
        self.assertEqual(g.d("G4"), "G3")
        self.assertSetEqual(set(g.type(["G4", "G5", "\\G18[0]"])), set(["ff"]))

    def test_verilog_escaped_names(self):
        g = cg.from_lib("test_correct_io", name="test_module_3")
        self.assertSetEqual(
            g.nodes(),
            set(
                [
                    "clk",
                    "\\G0[0]",
                    "\\I0[0]",
                    "\\I0[1]",
                    "\\G1[1][0]",
                    "\\G1[1][1]",
                    "\\G2[0]",
                    "\\G3[0][0]",
                    "\\G3[0][1]",
                    "\\G3[0][2]",
                    "\\I1[0]",
                    "\\not_G1[1][1]",
                    "\\and_G0[0]_not_G1[1][1]",
                ]
            ),
        )
        self.assertSetEqual(
            g.fanin("\\G2[0]"), set(["\\G0[0]", "\\G1[1][1]", "\\I0[1]"])
        )
        self.assertSetEqual(g.fanin("\\G3[0][0]"), set(["\\G0[0]", "\\G1[1][0]"]))

    def test_incorrect_verilog(self):
        for module in [
            "test_part_select_inst_0",
            "test_part_select_inst_1",
            "test_part_select_assign_0",
            "test_part_select_assign_1",
            "test_parameter_0",
            "test_parameter_1",
            "test_concat_0",
            "test_concat_1",
            "test_instance",
            "test_seq",
        ]:
            self.assertRaises(ValueError, cg.from_lib, "test_incorrect_io", name=module)

    def test_verilog_output(self):
        for g in [
            cg.from_lib("test_correct_io", name="test_module_0"),
            cg.from_lib("test_correct_io", name="test_module_1"),
            cg.from_lib("test_correct_io", name="test_module_2"),
            cg.from_lib("test_correct_io", name="test_module_3"),
        ]:
            g2 = verilog_to_circuit(circuit_to_verilog(g), g.name)
            m = miter(g, g2)
            live = sat(m)
            self.assertTrue(live)
            different_output = sat(m, assumptions={"sat": True})
            self.assertFalse(different_output)
