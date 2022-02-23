import unittest

import networkx as nx

import circuitgraph as cg


class TestCircuit(unittest.TestCase):
    def test_built_ins(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "and", fanin=["a", "b"], output=True)
        self.assertTrue("a" in c)
        self.assertTrue("b" in c)
        self.assertTrue("c" in c)
        self.assertEqual(c.type("a"), "input")
        self.assertEqual(c.type("b"), "input")
        self.assertEqual(c.type("c"), "and")
        self.assertFalse(c.is_output("a"))
        self.assertFalse(c.is_output("b"))
        self.assertTrue(c.is_output("c"))
        self.assertEqual(len(c), 3)
        self.assertSetEqual(c.nodes(), {"a", "b", "c"})

        uid_node = c.add("c", "or", uid=True)
        self.assertNotEqual(uid_node, "c")
        self.assertSetEqual(c.nodes(), {"a", "b", "c", uid_node})

    def test_constructor(self):
        g = nx.DiGraph()
        g.add_node("a", type="input")
        g.add_node("b", type="input")
        g.add_node("c", type="and", output=True)
        g.add_edge("a", "c")
        g.add_edge("b", "c")
        c = cg.Circuit(graph=g, name="and_gate")
        self.assertEqual(c.name, "and_gate")
        self.assertTrue("a" in c and "b" in c and "c" in c)
        self.assertFalse(c.is_output("a"))
        self.assertFalse(c.is_output("b"))
        self.assertTrue(c.is_output("c"))

        c2 = c.copy()
        self.assertTrue("a" in c2 and "b" in c2 and "c" in c2)
        self.assertFalse(c.is_output("a"))
        self.assertFalse(c.is_output("b"))
        self.assertTrue(c.is_output("c"))

    def test_copy(self):
        c = cg.Circuit(name="test_circuit")
        c.add("i0", "input")
        c.add("i1", "input")
        c.add("g0", "xor", fanin=["i0", "i1"])
        c.add("o0", "not", fanin=["g0"], output=True)

        c2 = c.copy()
        self.assertSetEqual(c.inputs(), c2.inputs())
        self.assertSetEqual(c.outputs(), c2.outputs())
        self.assertSetEqual(c.nodes(), c2.nodes())
        self.assertSetEqual(c.edges(), c2.edges())
        self.assertEqual(c.name, c2.name)

    def test_type(self):
        c = cg.Circuit()
        c.graph.add_node("a")
        self.assertRaises(KeyError, c.type, "a")
        self.assertRaises(KeyError, c.type, "b")

        c.set_type("a", "and")
        self.assertEqual(c.type("a"), "and")
        self.assertRaises(ValueError, c.set_type, "a", "bad")
        self.assertRaises(KeyError, c.set_type, "b", "and")

        c.add("b", "or")
        self.assertListEqual(c.type(["a", "b"]), ["and", "or"])
        c.set_type(["a", "b"], "xor")
        self.assertListEqual(c.type(["a", "b"]), ["xor", "xor"])

        c.add("c", "input")
        self.assertSetEqual(c.filter_type("xor"), {"a", "b"})
        self.assertSetEqual(c.filter_type(["xor", "input"]), {"a", "b", "c"})
        self.assertRaises(ValueError, c.filter_type, ["ad", "input"])

    def test_nodes(self):
        c = cg.Circuit()
        c.add("a", "xor")
        c.add("b", "or")
        c.add("c", "and")
        c.add("d", "xor")
        self.assertSetEqual(c.nodes(), {"a", "b", "c", "d"})

    def test_edges(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.edges(), {("a", "c"), ("b", "c")})

    def test_add(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "not", fanin="a")
        c.add("c", "xor")
        c.add("d", "nor")
        c.add("e", "input", fanout=["c", "d"])
        c.add("f", "input", fanout="c")
        self.assertSetEqual(c.edges(), {("a", "b"), ("e", "c"), ("e", "d"), ("f", "c")})
        self.assertRaises(ValueError, c.add, "g", "input", fanin="a")
        self.assertRaises(ValueError, c.add, "0g", "input")

    def test_remove(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.nodes(), {"a", "b", "c"})
        c.remove("a")
        self.assertSetEqual(c.nodes(), {"b", "c"})
        c.remove(["b", "c"])
        self.assertSetEqual(c.nodes(), set())

    def test_connect(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor")
        c.add("d", "or")
        c.add("e", "buf")
        self.assertSetEqual(c.edges(), set())
        c.connect("a", "c")
        c.connect("b", "c")
        self.assertSetEqual(c.edges(), {("a", "c"), ("b", "c")})
        c.connect(["a", "b"], ["d", "d"])
        self.assertSetEqual(c.edges(), {("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")})

        self.assertRaises(ValueError, c.connect, "q", "a")
        self.assertRaises(ValueError, c.connect, ["a", "b"], "e")
        c.connect("b", "e")
        self.assertRaises(ValueError, c.connect, "a", "e")
        self.assertRaises(ValueError, c.connect, ["a", "b"], ["a", "b"])

    def test_disconnect(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "not", fanin="a")
        self.assertSetEqual(c.edges(), {("a", "b")})
        c.disconnect("a", "b")
        self.assertSetEqual(c.edges(), set())
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.edges(), {("a", "c"), ("b", "c")})
        c.disconnect(["a", "b"], ["c", "c"])
        self.assertSetEqual(c.edges(), set())

    def test_fanin_fanout(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "not", fanin="c")
        self.assertSetEqual(c.fanin("a"), set())
        self.assertSetEqual(c.fanin("d"), {"a", "b"})
        self.assertSetEqual(c.fanin(["d", "e"]), {"a", "b", "c"})
        self.assertSetEqual(c.fanout("e"), set())
        self.assertSetEqual(c.fanout("a"), {"d"})
        self.assertSetEqual(c.fanout(["b", "c"]), {"d", "e"})

    def test_transitive_fanin_fanout(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "buf", output=True)
        c.add("clk", "input")
        c.add("e", "xor", fanin=["a", "b"])
        c.add("f", "not", fanin="c")
        c.add("g", "or", fanin=["c", "d"])
        c.add("h", "and", fanin=["e", "f"])

        ff = cg.BlackBox("ff", ["CK", "D"], ["Q"])
        c.add_blackbox(ff, "ff0", {"CK": "clk", "D": "a", "Q": "d"})
        c.add_blackbox(ff, "ff1", {"CK": "clk", "D": "g"})

        c.add("ji", "buf", fanin="ff1.Q")
        c.add("j", "nor", fanin=["ji", "h"])
        c.add("k", "not", fanin="ji")
        c.add("l", "buf", fanin="k")

        self.assertSetEqual(c.transitive_fanin("a"), set())
        self.assertSetEqual(
            c.transitive_fanin("j"), {"a", "b", "c", "e", "f", "h", "ji", "ff1.Q"}
        )
        self.assertSetEqual(
            c.transitive_fanin(["j", "l"]),
            {"a", "b", "c", "e", "f", "h", "ji", "ff1.Q", "k"},
        )
        self.assertSetEqual(c.transitive_fanout("l"), set())
        self.assertSetEqual(c.transitive_fanout(["c"]), {"f", "g", "h", "ff1.D", "j"})
        self.assertSetEqual(
            c.transitive_fanout(["a", "c"]),
            {"e", "f", "g", "h", "ff1.D", "j", "ff0.D"},
        )
        self.assertSetEqual(c.transitive_fanin("d"), {"ff0.Q"})

    def test_paths(self):
        c = cg.from_lib("c17")
        self.assertListEqual(list(c.paths("N1", "N22")), [["N1", "N10", "N22"]])

        available_paths = [
            ["N3", "N10", "N22"],
            ["N3", "N11", "N16", "N22"],
        ]
        for path in c.paths("N3", "N22"):
            self.assertTrue(path in available_paths)
            available_paths.remove(path)

    def test_comb_depth(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        c.add("d", "buf", fanin=["a"])
        c.add("e", "not", fanin=["c"])
        c.add("f", "not", fanin=["c"])
        c.add("g", "buf", fanin="d")
        c.add("h", "buf", fanin="d", output=True)
        c.add("i", "buf", fanin="e")
        c.add("j", "input")
        c.add("k", "and", fanin=["i", "j", "f"])
        c.add("l", "and", fanin=["k", "g"], output=True)

        self.assertEqual(c.fanout_depth("e"), 3)
        self.assertEqual(c.fanout_depth(["e", "g"]), 3)
        self.assertEqual(c.fanout_depth("a"), 5)

        self.assertEqual(c.fanin_depth("l"), 5)
        self.assertEqual(c.fanin_depth(["f", "l"]), 5)
        self.assertEqual(c.fanin_depth("g"), 2)

        c.connect("f", "c")
        self.assertRaises(ValueError, c.fanout_depth, "a")

    def test_add_subcircuit(self):
        c = cg.Circuit()

        inputs = ["a", "b", "s"]
        outputs = ["o"]

        for i in inputs:
            c.add(i, "input")

        for o in outputs:
            c.add(o, "buf", output=True)

        mux_inputs = ["i0", "i1", "sel"]
        m = cg.Circuit("mux")
        for i in mux_inputs:
            m.add(i, "input")

        m.add("a0", "and", fanin=["i0", "sel"])
        m.add("sel_b", "not", fanin="sel")
        m.add("a1", "and", fanin=["i1", "sel"])
        m.add("o0", "or", fanin=["a0", "a1"], output=True)

        # Sub-blackbox name clash
        sub_m = m.copy()
        mux = cg.BlackBox("mux", [], [])
        sub_m.add_blackbox(mux, "sub")
        sub_c = c.copy()
        sub_c.add_blackbox(mux, "mux0_sub")
        self.assertRaises(ValueError, sub_c.add_subcircuit, sub_m, "mux0")

        # Node name clash
        c.add("mux0_i0", "buf")
        self.assertRaises(ValueError, c.add_subcircuit, m, "mux0")
        c.remove("mux0_i0")

        # Bad connections
        self.assertRaises(ValueError, c.add_subcircuit, m, "mux0", {"fake_con": "a"})

        pre_mux_nodes = c.nodes()
        c.add_subcircuit(m, "mux0", {"i0": "a", "i1": "b", "sel": "s", "o0": "o"})

        self.assertEqual(c.nodes(), pre_mux_nodes | {f"mux0_{n}" for n in m.nodes()})

    def test_blackbox(self):
        mux_inputs = ["i0", "i1", "sel"]
        mux_outputs = ["o0"]
        mux = cg.BlackBox("mux", mux_inputs, mux_outputs)
        self.assertSetEqual(mux.inputs(), set(mux_inputs))
        self.assertSetEqual(mux.outputs(), set(mux_outputs))
        self.assertSetEqual(mux.io(), set(mux_inputs + mux_outputs))

    def test_add_blackbox(self):
        c = cg.Circuit()

        inputs = ["a", "b", "s"]
        outputs = ["o"]

        for i in inputs:
            c.add(i, "input")

        for o in outputs:
            c.add(o, "buf", output=True)

        # Add mux blackbox
        mux_inputs = ["i0", "i1", "sel"]
        mux_outputs = ["o0"]
        mux = cg.BlackBox("mux", mux_inputs, mux_outputs)
        c.add_blackbox(
            mux, "mux0", dict(zip(mux_inputs + mux_outputs, inputs + outputs))
        )

        # Check types
        self.assertEqual(c.blackboxes, {"mux0": mux})
        self.assertEqual(c.type("mux0.i0"), "bb_input")
        self.assertEqual(c.type("mux0.i1"), "bb_input")
        self.assertEqual(c.type("mux0.sel"), "bb_input")
        self.assertEqual(c.type("mux0.o0"), "bb_output")
        # Check connections
        self.assertSetEqual(c.fanin("o"), {"mux0.o0"})
        self.assertSetEqual(c.fanout("a"), {"mux0.i0"})
        self.assertSetEqual(c.fanout("b"), {"mux0.i1"})
        self.assertSetEqual(c.fanout("s"), {"mux0.sel"})

        # Add blackbox with same name
        self.assertRaises(ValueError, c.add_blackbox, mux, "mux0")

        # Add blackbox with incorrect conections
        self.assertRaises(ValueError, c.add_blackbox, mux, "mux1", {"fake_node": "a"})

        # Connect bb_output to multiple buffers
        self.assertRaises(ValueError, c.add, "temp", "buf", fanin="mux0.o0")

        # Connect bb_output to non-buffer
        c.disconnect("mux0.o0", "o")
        self.assertRaises(ValueError, c.add, "temp", "and", fanin="mux0.o0")

    def test_blackbox_back_to_back(self):
        c = cg.Circuit()

        inputs = ["a", "b", "c", "s"]
        outputs = ["o"]

        for i in inputs:
            c.add(i, "input")

        for o in outputs:
            c.add(o, "buf", output=True)

        mux_inputs = ["i0", "i1", "sel"]
        mux_outputs = ["o0"]
        mux = cg.BlackBox("mux", mux_inputs, mux_outputs)
        c.add_blackbox(mux, "mux0", dict(zip(mux_inputs, inputs)))
        c.add_blackbox(mux, "mux1", {"i1": "c", "sel": "s", "o0": "o"})
        c.add("inter", "buf", fanin="mux0.o0", fanout="mux1.i0")

        self.assertEqual(c.blackboxes, {"mux0": mux, "mux1": mux})
        self.assertSetEqual(c.fanin("mux1.i0"), {"inter"})
        self.assertSetEqual(c.fanout("mux0.o0"), {"inter"})

    def test_fill_blackbox(self):
        c = cg.Circuit()

        inputs = ["a", "b", "c", "s"]
        for i in inputs:
            c.add(i, "input")

        c.add("d", "and", fanin=["b", "c"])
        c.add("e", "buf")
        c.add("o", "and", fanin=["d", "e"], output=True)

        mux_inputs = ["i0", "i1", "sel"]
        mux_outputs = ["o0"]
        mux = cg.BlackBox("mux", mux_inputs, mux_outputs)

        m = cg.Circuit("mux")
        for i in mux_inputs:
            m.add(i, "input")

        m.add("a0", "and", fanin=["i0", "sel"])
        m.add("sel_b", "not", fanin="sel")
        m.add("a1", "and", fanin=["i1", "sel"])
        m.add("o0", "or", fanin=["a0", "a1"], output=True)

        pre_mux_nodes = c.nodes()
        c.add_blackbox(mux, "mux0", {"i0": "a", "i1": "d", "sel": "s", "o0": "e"})

        # Fill unadded blackbox
        self.assertRaises(ValueError, c.fill_blackbox, "mux1", m)

        # Sub-blackbox name clash
        sub_m = m.copy()
        sub_m.add_blackbox(mux, "sub")
        sub_c = c.copy()
        sub_c.add_blackbox(mux, "mux0_sub")
        self.assertRaises(ValueError, sub_c.fill_blackbox, "mux0", sub_m)

        # Non-matching IO
        wrong_m_i = m.copy()
        wrong_m_i.add("fake_input", "input")
        self.assertRaises(ValueError, c.fill_blackbox, "mux0", wrong_m_i)
        wrong_m_o = m.copy()
        wrong_m_o.add("fake_output", "buf", output=True)
        self.assertRaises(ValueError, c.fill_blackbox, "mux0", wrong_m_o)

        # Node name clash
        c.add("mux0_i0", "buf")
        self.assertRaises(ValueError, c.fill_blackbox, "mux0", m)
        c.remove("mux0_i0")

        # Valid fill
        c.fill_blackbox("mux0", m)
        self.assertSetEqual(c.nodes(), pre_mux_nodes | {f"mux0_{n}" for n in m.nodes()})

        self.assertSetEqual(c.fanin("mux0_o0"), {"mux0_a0", "mux0_a1"})
        self.assertSetEqual(c.fanout("mux0_o0"), {"e"})
        self.assertEqual(c.type("mux0_o0"), "or")
        self.assertFalse(c.is_output("mux0_o0"))

    def test_io(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"], output=True)
        self.assertSetEqual(c.inputs(), {"a", "b"})
        self.assertSetEqual(c.outputs(), {"c"})
        self.assertSetEqual(c.io(), {"a", "b", "c"})

    def test_startpoints_endpoints(self):
        c = cg.Circuit()
        c.add("clk", "input")
        c.add("rst", "input")
        c.add("set", "input")
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("dd0", "buf")
        c.add("dd1", "buf")
        c.add("d", "xor", fanin=["a", "b", "dd0", "dd1"])
        c.add("e", "and", fanin=["c", "d"])

        ff = cg.BlackBox("ff", ["CK", "D"], ["Q"])
        c.add_blackbox(ff, "ff0", {"CK": "clk", "D": "d", "Q": "dd0"})
        c.add_blackbox(ff, "ff1", {"CK": "clk", "D": "e", "Q": "dd1"})

        c.add("h", "buf", fanin="dd0", output=True)
        c.add("i", "buf", fanin="dd1", output=True)

        self.assertSetEqual(
            c.startpoints(), {"clk", "rst", "set", "a", "b", "c", "ff0.Q", "ff1.Q"}
        )
        self.assertSetEqual(
            c.endpoints(), {"ff1.D", "ff0.D", "ff0.CK", "ff1.CK", "h", "i"}
        )
        self.assertSetEqual(c.startpoints("h"), {"ff0.Q"})
        self.assertSetEqual(c.endpoints("c"), {"ff1.D"})
        self.assertSetEqual(c.startpoints("c"), {"c"})
        self.assertSetEqual(c.endpoints("e"), {"ff1.D"})

    def test_reconvergent_fanout_nodes(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")

        c.add("g0", "and", fanin=["a", "b"])
        c.add("g1", "and", fanin=["c", "g0"])
        c.add("g2", "not", fanin=["g0"])
        c.add("g3", "and", fanin=["g1", "g2"])
        c.add("g4", "not", fanin=["c"])
        c.add("g5", "and", fanin=["g3", "g4"], output=True)

        self.assertSetEqual(set(c.reconvergent_fanout_nodes()), {"c", "g0"})

    def test_has_reconvergent_fanout(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")

        c.add("g0", "and", fanin=["a", "b"])
        c.add("g1", "and", fanin=["c", "g0"], output=True)
        self.assertFalse(c.has_reconvergent_fanout())
        c.add("g2", "not", fanin=["g0"])
        c.add("g3", "and", fanin=["g1", "g2"])
        c.add("g4", "not", fanin=["c"])
        c.add("g5", "and", fanin=["g3", "g4"], output=True)
        self.assertTrue(c.has_reconvergent_fanout())

    def test_is_cyclic(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "xor", fanin="a")
        self.assertFalse(c.is_cyclic())
        c.connect("b", "b")
        self.assertTrue(c.is_cyclic())

    def test_relabel(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "xor", fanin="a")
        c.relabel({"a": "n"})
        self.assertSetEqual(c.nodes(), {"b", "n"})

    def test_topo_sort(self):
        c = cg.Circuit()
        c.add("i0", "input")
        c.add("n", "not", fanin=["i0"])
        c.add("a", "and", fanin=["i0", "n"])
        c.add("o", "or", fanin=["a", "i0"])
        c.add("o0", "xor", fanin=["o", "a"], output=True)
        l = list(c.topo_sort())
        self.assertListEqual(l, ["i0", "n", "a", "o", "o0"])

    def test_remove_unloaded(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"], output=True)
        c.add("f", "and", fanin=["c", "d"])
        c.add("g", "buf", fanin="f")
        c2 = c.copy()
        c.remove_unloaded()
        self.assertSetEqual(c.nodes(), {"a", "b", "c", "d"})

        c2.remove_unloaded(inputs=True)
        self.assertSetEqual(c2.nodes(), {"a", "b", "d"})
