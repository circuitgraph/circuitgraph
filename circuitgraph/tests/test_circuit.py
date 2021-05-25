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
        c.add("c", "and", fanin=["a", "b"])
        c.add("co", "output", fanin="c")
        self.assertTrue("a" in c)
        self.assertTrue(len(c) == 4)
        self.assertSetEqual(c.nodes(), set(["a", "b", "c", "co"]))

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
        self.assertSetEqual(c.filter_type("xor"), set(["a", "b"]))
        self.assertSetEqual(c.filter_type(["xor", "input"]), set(["a", "b", "c"]))
        self.assertRaises(ValueError, c.filter_type, ["ad", "input"])

    def test_nodes(self):
        c = cg.Circuit()
        c.add("a", "xor")
        c.add("b", "or")
        c.add("c", "and")
        c.add("d", "xor")
        self.assertSetEqual(c.nodes(), set(["a", "b", "c", "d"]))

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

    def test_connect(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor")
        c.add("d", "or")
        c.add("e", "buf")
        c.add("f", "output")
        self.assertSetEqual(c.edges(), set())
        c.connect("a", "c")
        c.connect("b", "c")
        self.assertSetEqual(c.edges(), set([("a", "c"), ("b", "c")]))
        c.connect(["a", "b"], ["d", "d"])
        self.assertSetEqual(
            c.edges(), set([("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")])
        )

        self.assertRaises(ValueError, c.connect, "q", "a")
        self.assertRaises(ValueError, c.connect, ["a", "b"], "e")
        c.connect("b", "e")
        self.assertRaises(ValueError, c.connect, "a", "e")
        self.assertRaises(ValueError, c.connect, "f", "c")
        self.assertRaises(ValueError, c.connect, ["a", "b"], ["a", "b"])

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
        c.add("d", "output")
        c.add("clk", "input")
        c.add("e", "xor", fanin=["a", "b"])
        c.add("f", "not", fanin="c")
        c.add("g", "or", fanin=["c", "d"])
        c.add("h", "and", fanin=["e", "f"])

        ff = cg.BlackBox("ff", ["CK", "D"], ["Q"])
        c.add_blackbox(ff, "ff0", {"CK": "clk", "D": "a", "Q": "d"})
        c.add_blackbox(ff, "ff1", {"CK": "clk", "D": "g"})

        c.add("j", "nor", fanin=["ff1.Q", "h"])
        c.add("k", "not", fanin="ff1.Q")
        c.add("l", "buf", fanin="k")

        self.assertSetEqual(c.transitive_fanin("a"), set())
        self.assertSetEqual(
            c.transitive_fanin("j"), set(["a", "b", "c", "e", "f", "h", "ff1.Q"])
        )
        self.assertSetEqual(
            c.transitive_fanin(["j", "l"]),
            set(["a", "b", "c", "e", "f", "h", "ff1.Q", "k"]),
        )
        self.assertSetEqual(c.transitive_fanout("l"), set())
        self.assertSetEqual(
            c.transitive_fanout(["c"]), set(["f", "g", "h", "ff1.D", "j"])
        )
        self.assertSetEqual(
            c.transitive_fanout(["a", "c"]),
            set(["e", "f", "g", "h", "ff1.D", "j", "ff0.D"]),
        )

    def test_comb_depth(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        c.add("d", "buf", fanin=["a"])
        c.add("e", "not", fanin=["c"])
        c.add("f", "not", fanin=["c"])
        c.add("g", "buf", fanin="d")
        c.add("h", "output", fanin="d")
        c.add("i", "buf", fanin="e")
        c.add("j", "input")
        c.add("k", "and", fanin=["i", "j", "f"])
        c.add("l", "and", fanin=["k", "g"])
        c.add("m", "output", fanin="l")

        self.assertEqual(c.fanout_depth("e"), 4)
        self.assertEqual(c.fanout_depth(["e", "g"]), 4)
        self.assertEqual(c.fanout_depth("a"), 6)

        self.assertEqual(c.fanin_depth("m"), 6)
        self.assertEqual(c.fanin_depth(["f", "m"]), 6)
        self.assertEqual(c.fanin_depth("g"), 2)

        c.connect("f", "c")
        self.assertRaises(ValueError, c.fanout_depth, "a")

    def test_blackbox(self):
        c = cg.Circuit()
        c.add("clk", "input")
        c.add("rst", "input")
        c.add("set", "input")
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "and", fanin=["c", "d"])

        ff = cg.BlackBox("ff", ["CK", "D"], ["Q"])
        c.add_blackbox(ff, "ff0", {"CK": "clk", "D": "a", "Q": "d"})

        self.assertRaises(ValueError, c.add_blackbox, ff, "ff0")

        c.add("h", "output", fanin="ff0.Q")
        # catch before adding
        # c.add("i", "output", fanin="ff0.D")

        # add node that will overlap
        c.add("ff1_Q", "input")
        f = cg.Circuit()
        f.add("CK", "input")
        f.add("D", "input")
        f.add("Q", "output")
        f.add("o", "or", fanin=["CK", "D"], fanout=["Q"])
        f.add_blackbox(ff, "ff0", {"CK": "CK", "D": "D", "Q": "o"})

        self.assertRaises(ValueError, c.fill_blackbox, "ff1", f)
        c.fill_blackbox("ff0", f)

        self.assertSetEqual(c.fanin("ff0_CK"), set(["clk"]))
        self.assertSetEqual(c.fanout("ff0_CK"), set(["ff0_o", "ff0_ff0.CK"]))

        self.assertEqual(c.type("ff0_Q"), "buf")
        self.assertSetEqual(c.fanout("ff0_Q"), set(["d", "h"]))
        self.assertSetEqual(c.fanin("ff0_Q"), set(["ff0_o"]))

    def test_io(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "xor", fanin=["a", "b"])
        c.add("co", "output", fanin="c")
        self.assertSetEqual(c.inputs(), set(["a", "b"]))
        self.assertSetEqual(c.outputs(), set(["co"]))
        self.assertSetEqual(c.io(), set(["a", "b", "co"]))

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

        ff = cg.BlackBox("ff", ["CK", "D"], ["Q"])
        c.add_blackbox(ff, "ff0", {"CK": "clk", "D": "d", "Q": "d"})
        c.add_blackbox(ff, "ff1", {"CK": "clk", "D": "e", "Q": "d"})

        c.add("h", "output", fanin="ff0.Q")
        c.add("i", "output", fanin="ff1.Q")

        self.assertSetEqual(
            c.startpoints(), set(["clk", "rst", "set", "a", "b", "c", "ff0.Q", "ff1.Q"])
        )
        self.assertSetEqual(
            c.endpoints(), set(["ff1.D", "ff0.D", "ff0.CK", "ff1.CK", "h", "i"])
        )
        self.assertSetEqual(c.startpoints("h"), set(["ff0.Q"]))
        self.assertSetEqual(c.endpoints("c"), set(["ff1.D"]))
        self.assertSetEqual(c.startpoints("c"), set(["c"]))
        self.assertSetEqual(c.endpoints("e"), set(["ff1.D"]))

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
        self.assertSetEqual(c.nodes(), set(["b", "n"]))

    def test_kcuts(self):
        c = cg.from_lib("c432")
        for n in c:
            for cut in c.kcuts(n, 2):
                clc = cg.copy(c)
                for g in cut:
                    clc.disconnect(clc.fanin(g), g)
                    clc.set_type(g, "input")
                self.assertSetEqual(clc.startpoints(n), cut)

    def test_topo_sort(self):
        c = cg.from_lib("c432")
        visited = set()
        for n in c.topo_sort():
            self.assertFalse(c.transitive_fanout(n) & visited)
            visited.add(n)

    def test_remove_unloaded(self):
        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "output", fanin="d")
        c.add("f", "and", fanin=["c", "d"])
        c.add("g", "buf", fanin="f")
        c.remove_unloaded()
        self.assertSetEqual(c.nodes(), set(["a", "b", "c", "d", "e"]))

        c = cg.Circuit()
        c.add("a", "input")
        c.add("b", "input")
        c.add("c", "input")
        c.add("d", "xor", fanin=["a", "b"])
        c.add("e", "output", fanin="d")
        c.add("f", "and", fanin=["c", "d"])
        c.add("g", "buf", fanin="f")
        c.remove_unloaded(inputs=True)
        self.assertSetEqual(c.nodes(), set(["a", "b", "d", "e"]))
