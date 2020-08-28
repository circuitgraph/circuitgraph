import unittest
import shutil
from itertools import product

import networkx as nx

import circuitgraph as cg
from circuitgraph import clog2, int_to_bin


class TestCircuit(unittest.TestCase):
    def test_built_ins(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "and", fanin=["a", "b"], output=True)
        self.assertTrue("a" in c)
        self.assertTrue(len(c) == 3)
        self.assertListEqual(list(iter(c)), ["a", "b", "c"])

    def test_constructor(self):
        g = nx.DiGraph()
        g.add_node("a", type="input")
        g.add_node("b", type="input")
        g.add_node("c", type="and")
        g.add_edge("a", "c")
        g.add_edge("b", "c")
        c = cg.Circuit(graph=g, name="and_gate")
        self.assertEqual(c.name, "and_gate")
        self.assertTrue("a" in c and "b" in c and "c" in c)

        c2 = cg.copy(c)
        self.assertTrue("a" in c2 and "b" in c2 and "c" in c2)

    def test_type(self):
        c = cg.Circuit()
        c.graph.add_node("a")
        self.assertRaises(KeyError, c.type, "a")
        c.set_type("a", "and")
        self.assertEqual(c.type("a"), "and")
        c.add("b", "or")
        self.assertListEqual(c.type(["a", "b"]), ["and", "or"])
        c.set_type(["a", "b"], "xor")
        self.assertListEqual(c.type(["a", "b"]), ["xor", "xor"])

    def test_output(self):
        c = cg.Circuit()
        c.add("a", "xor", output=True)
        c.add("b", "xor")
        self.assertListEqual(c.output(["a", "b"]), [True, False])
        c.set_output("a", False)
        self.assertEqual(c.output("a"), False)
        c.set_output(["a", "b"])
        self.assertListEqual(c.output(["a", "b"]), [True, True])
        c.graph.add_node("c")
        self.assertRaises(KeyError, c.output, "c")

    def test_nodes(self):
        c = cg.Circuit()
        c.add("a", "xor")
        c.add("b", "or")
        c.add("c", "and")
        c.add("d", "xor", output=True)
        self.assertSetEqual(c.nodes(), set(["a", "b", "c", "d"]))
        self.assertSetEqual(c.nodes(types="xor"), set(["a", "d"]))
        self.assertSetEqual(c.nodes(output=True), set(["d"]))
        self.assertSetEqual(c.nodes(types="xor", output=True), set(["d"]))
        self.assertSetEqual(c.nodes(types=["xor", "or"]), set(["a", "b", "d"]))

    def test_edges(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.edges(), set([("a", "c"), ("b", "c")]))

    def test_add(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "not", fanin="a")
        c.add("c", "xor")
        c.add("d", "nor")
        c.add("e", "input", fanout=["c", "d"])
        c.add("f", "input", fanout="c")
        self.assertSetEqual(
            c.edges(), set([("a", "b"), ("e", "c"), ("e", "d"), ("f", "c")])
        )
        self.assertRaises(ValueError, c.add, "g", "ff", fanin=["a", "b"])
        self.assertRaises(ValueError, c.add, "g", "input", fanin="a")
        self.assertRaises(ValueError, c.add, "0g", "input")

    def test_remove(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.nodes(), set(["a", "b", "c"]))
        c.remove("a")
        self.assertSetEqual(c.nodes(), set(["b", "c"]))
        c.remove(["b", "c"])
        self.assertSetEqual(c.nodes(), set())

    def test_extend(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "not", fanin="a")
        c2 = cg.Circuit()
        c2.add("c", "input")
        c2.add("d", "buf", fanin="c")
        c.extend(c2)
        self.assertSetEqual(c.nodes(), set(["a", "b", "c", "d"]))

    def test_connect(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor")
        c.add("d", "or")
        self.assertSetEqual(c.edges(), set())
        c.connect("a", "c")
        c.connect("b", "c")
        self.assertSetEqual(c.edges(), set([("a", "c"), ("b", "c")]))
        c.connect(["a", "b"], ["d", "d"])
        self.assertSetEqual(
            c.edges(), set([("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")])
        )

    def test_disconnect(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "not", fanin="a")
        self.assertSetEqual(c.edges(), set([("a", "b")]))
        c.disconnect("a", "b")
        self.assertSetEqual(c.edges(), set())
        c.add("c", "xor", fanin=["a", "b"])
        self.assertSetEqual(c.edges(), set([("a", "c"), ("b", "c")]))
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
        self.assertSetEqual(c.fanin("d"), set(["a", "b"]))
        self.assertSetEqual(c.fanin(["d", "e"]), set(["a", "b", "c"]))
        self.assertSetEqual(c.fanout("e"), set())
        self.assertSetEqual(c.fanout("a"), set(["d"]))
        self.assertSetEqual(c.fanout(["b", "c"]), set(["d", "e"]))

    def test_transitive_fanin_fanout(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "input")
        c.add("e", "xor", fanin=["a", "b"])
        c.add("f", "not", fanin="c")
        c.add("g", "or", fanin=["c", "d"])
        c.add("h", "and", fanin=["e", "f"])
        c.add("i", "ff", fanin="g")
        c.add("j", "nor", fanin=["i", "h"])
        c.add("k", "not", fanin="i")
        c.add("l", "buf", fanin="k")
        self.assertSetEqual(c.transitive_fanin("a"), set())
        self.assertSetEqual(
            c.transitive_fanin("j"), set(["a", "b", "c", "e", "f", "h", "i"])
        )
        self.assertSetEqual(
            c.transitive_fanin(["j", "l"]),
            set(["a", "b", "c", "e", "f", "h", "i", "k"]),
        )
        self.assertSetEqual(
            c.transitive_fanin(["j"], stopat_types=[]),
            set(["a", "b", "c", "d", "e", "f", "g", "h", "i"]),
        )
        self.assertSetEqual(
            c.transitive_fanin(["j"], stopat_nodes=["e", "f"]),
            set(["e", "f", "h", "i"]),
        )
        self.assertSetEqual(c.transitive_fanout("l"), set())
        self.assertSetEqual(c.transitive_fanout(["c"]), set(["f", "g", "h", "i", "j"]))
        self.assertSetEqual(
            c.transitive_fanout(["a", "c"]), set(["e", "f", "g", "h", "i", "j"])
        )
        self.assertSetEqual(
            c.transitive_fanout(["c"], stopat_types=[]),
            set(["f", "g", "h", "j", "i", "k", "l"]),
        )
        self.assertSetEqual(
            c.transitive_fanout(["c"], stopat_nodes=["f", "g"]), set(["f", "g"])
        )

    def test_comb_depth(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "input")
        c.add("e", "xor", fanin=["a", "b"])
        c.add("f", "not", fanin="c")
        c.add("g", "or", fanin=["c", "d"])
        c.add("h", "and", fanin=["e", "f"])
        c.add("i", "ff", fanin="g")
        c.add("j", "nor", fanin=["i", "h"])
        self.assertEqual(c.fanin_comb_depth("j"), 3)
        self.assertEqual(c.fanin_comb_depth(["i", "j"]), 3)
        self.assertEqual(c.fanin_comb_depth("j", shortest=True), 1)
        # FIXME: What should be fanin_comb_depth of input or ff?
        #        and fanout_comb_depth of output
        # FIXME: How should this and transitive act when there's a cycle
        self.assertEqual(c.fanout_comb_depth("c"), 3)
        self.assertEqual(c.fanout_comb_depth(["a", "c"]), 3)
        self.assertEqual(c.fanout_comb_depth("c", shortest=True), 1)

    def test_seq(self):
        c = cg.Circuit()
        c.add("clk", "input")
        c.add("rst", "input")
        c.add("set", "input")
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "and", fanin=["c", "d"])
        c.add("f", "ff", fanin="d", clk="clk", r="rst", s="set")
        c.add("g", "lat", fanin="e", clk="clk", r="rst", s="set")
        c.add("h", "output", fanin="f")
        c.add("i", "output", fanin="g")
        c.graph.add_node("j", type="and")
        self.assertSetEqual(c.lats(), set("g"))
        self.assertSetEqual(c.ffs(), set("f"))
        self.assertSetEqual(c.seq(), set(["f", "g"]))
        self.assertListEqual(c.r(["f", "g"]), ["rst", "rst"])
        self.assertListEqual(c.s(["f", "g"]), ["set", "set"])
        self.assertListEqual(c.clk(["f", "g"]), ["clk", "clk"])
        self.assertListEqual(c.d(["f", "g"]), ["d", "e"])
        self.assertRaises(KeyError, c.r, "j")
        self.assertRaises(KeyError, c.s, "j")
        self.assertRaises(KeyError, c.clk, "j")
        self.assertRaises(KeyError, c.d, "j")

    def test_io(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"], output=True)
        self.assertSetEqual(c.inputs(), set(["a", "b"]))
        self.assertSetEqual(c.outputs(), set(["c"]))
        self.assertSetEqual(c.io(), set(["a", "b", "c"]))

    def test_standpoints_endpoints(self):
        c = cg.Circuit()
        c.add("clk", "input")
        c.add("rst", "input")
        c.add("set", "input")
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "and", fanin=["c", "d"])
        c.add("f", "ff", fanin="d", clk="clk", r="rst", s="set")
        c.add("g", "lat", fanin="e", clk="clk", r="rst", s="set")
        c.add("h", "output", fanin="f")
        c.add("i", "output", fanin="g")
        self.assertSetEqual(
            c.startpoints(), set(["clk", "rst", "set", "a", "b", "c", "f", "g"])
        )
        self.assertSetEqual(c.endpoints(), set(["d", "e"]))
        self.assertSetEqual(c.startpoints("h"), set(["f"]))
        self.assertSetEqual(c.endpoints("c"), set(["e"]))
        self.assertSetEqual(c.startpoints("c"), set(["c"]))
        self.assertSetEqual(c.endpoints("e"), set(["e"]))

    def test_is_cyclic(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "xor", fanin="a")
        self.assertFalse(c.is_cyclic())
        c.connect("b", "b")
        self.assertTrue(c.is_cyclic())
