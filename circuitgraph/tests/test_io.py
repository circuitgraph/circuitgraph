import unittest
import os

import circuitgraph as cg
from circuitgraph.transform import miter
from circuitgraph.sat import sat


class TestIO(unittest.TestCase):
    @unittest.skip("bench parsing is not working")
    def test_bench(self):
        g = cg.from_file(f"{os.path.dirname(__file__)}/../netlists/b17_C.bench")
        print(g.nodes())

    def test_verilog_comb(self):
        for g in [
            cg.from_lib("test_correct_io", name="test_correct_io"),
            cg.from_lib("test_correct_io", name="test_module_1"),
            cg.from_file(f"{os.path.dirname(__file__)}/../netlists/test_correct_io.v"),
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
                        "tie_1",
                        "\\and_G8[0]_G5[0]",
                        "or_not_G2_tie_1",
                    ]
                ),
            )
            self.assertSetEqual(g.fanin("\\G8[0]"), set(["G1", "G3"]))
            self.assertSetEqual(g.fanin("G17"), set(["\\G8[1]", "tie_1"]))
            self.assertSetEqual(g.fanin("G18"), set(["G2", "\\G5[0]"]))
            self.assertSetEqual(g.fanin("\\G22[0]"), set(["\\G5[1]", "G4"]))

            self.assertEqual(g.type("\\G8[0]"), "nand")
            self.assertEqual(g.type("G17"), "nor")
            self.assertEqual(g.type("G18"), "and")
            self.assertEqual(g.type("\\G22[0]"), "xor")
            self.assertEqual(g.type("tie_1"), "1")

            self.assertSetEqual(g.fanin("G19"), set(["and_G1_G2", "xor_G3_G4"]))
            self.assertSetEqual(g.fanin("and_G1_G2"), set(["G1", "G2"]))
            self.assertSetEqual(g.fanin("xor_G3_G4"), set(["G3", "G4"]))
            self.assertSetEqual(g.fanin("G20"), set(["G17", "\\and_G8[0]_G5[0]"]))
            self.assertSetEqual(
                g.fanin("\\and_G8[0]_G5[0]"), set(["\\G8[0]", "\\G5[0]"])
            )
            self.assertSetEqual(g.fanin("\\G22[1]"), set(["G1", "or_not_G2_tie_1"]))
            self.assertSetEqual(g.fanin("or_not_G2_tie_1"), set(["not_G2", "tie_1"]))
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

    def test_verilog_custom_seq(self):
        c = cg.from_file(
            f"{os.path.dirname(__file__)}/../netlists/test_correct_io.v",
            name="test_module_4",
            seq_types=[
                cg.SequentialElement(
                    "custom_flop",
                    "ff",
                    {
                        "d": "data_in",
                        "q": "data_out",
                        "clk": "clock",
                        "r": "reset",
                        "s": "set",
                    },
                    "",
                )
            ],
        )
        self.assertEqual(c.d("b"), "a")
        self.assertEqual(c.r("b"), "rst")
        self.assertEqual(c.s("b"), "set")
        self.assertEqual(c.clk("b"), "clk")

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
        with open(f"{os.path.dirname(__file__)}/../netlists/test_incorrect_io.v") as f:
            verilog = f.read()
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
                "test_always",
                "test_logical_operator",
                "incorrect_module_name",
            ]:
                self.assertRaises(ValueError, cg.verilog_to_circuit, verilog, module)

    def test_incorrect_file_type(self):
        self.assertRaises(ValueError, cg.from_file, "setup.py")

    def test_verilog_output(self):
        for g in [
            cg.from_lib("test_correct_io", name="test_module_1"),
            cg.from_lib("test_correct_io", name="test_module_2"),
            cg.from_lib("test_correct_io", name="test_module_3"),
        ]:
            g2 = cg.verilog_to_circuit(cg.circuit_to_verilog(g), g.name)
            m = miter(g, g2)
            # live = sat(m)
            try:
                live = sat(m)
            except:
                import code

                code.interact(local=dict(globals(), **locals()))
            self.assertTrue(live)
            different_output = sat(m, assumptions={"sat": True})
            self.assertFalse(different_output)

        seq_types = [
            cg.SequentialElement(
                "custom_flop",
                "ff",
                {
                    "d": "data_in",
                    "q": "data_out",
                    "clk": "clock",
                    "r": "reset",
                    "s": "set",
                },
                "",
            )
        ]
        g = cg.from_file(
            f"{os.path.dirname(__file__)}/../netlists/test_correct_io.v",
            name="test_module_4",
            seq_types=seq_types,
        )
        g2 = cg.verilog_to_circuit(
            cg.circuit_to_verilog(g, seq_types=seq_types), g.name, seq_types=seq_types
        )
        live = sat(m)
        self.assertTrue(live)
        different_output = sat(m, assumptions={"sat": True})
        self.assertFalse(different_output)

    def test_verilog_incorrect_output(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "fake_gate", fanin=["a", "b"], output=True)
        self.assertRaises(ValueError, cg.circuit_to_verilog, c)
