import unittest
import shutil

import circuitgraph as cg
from circuitgraph import clog2, int_to_bin
from itertools import product


class TestCircuit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c17 = cg.from_lib("c17_gates", "c17")
        cls.s27 = cg.from_lib("s27")

    def test_fanin(self):
        self.assertSetEqual(self.c17.fanin("G9"), set(["G3", "G4"]))
        self.assertSetEqual(self.c17.fanin("G9"), set(["G3", "G4"]))
        self.assertSetEqual(self.c17.fanin("G17"), set(["G12", "G15"]))
        self.assertFalse(self.c17.fanin("G1"))
        self.assertSetEqual(
            self.c17.fanin(["G9", "G17"]), self.c17.fanin("G9") | self.c17.fanin("G17")
        )

    def test_fanin_comb_depth(self):
        self.assertEqual(self.s27.fanin_comb_depth("n_5"), 2)
        self.assertEqual(self.s27.fanin_comb_depth("n_20", shortest=True), 1)
        self.assertEqual(self.s27.fanin_comb_depth(["n_5", "n_1"]), 2)
        self.assertEqual(self.s27.fanin_comb_depth(["n_5", "n_1"], shortest=True), 1)

    def test_fanout_comb_depth(self):
        self.assertEqual(self.s27.fanout_comb_depth("n_10"), 2)
        self.assertEqual(self.s27.fanout_comb_depth("n_10", shortest=True), 1)
        self.assertEqual(self.s27.fanout_comb_depth(["n_10", "n_11"]), 2)
        self.assertEqual(self.s27.fanout_comb_depth(["n_10", "n_11"], shortest=True), 1)

    def test_fanout(self):
        self.assertSetEqual(self.c17.fanout("G1"), set(["G8"]))
        self.assertSetEqual(self.c17.fanout("G12"), set(["G16", "G17"]))
        self.assertFalse(self.c17.fanout("G17"))
        self.assertSetEqual(
            self.c17.fanout(["G1", "G8"]), self.c17.fanout("G1") | self.c17.fanout("G8")
        )

    def test_node(self):
        self.assertFalse(self.s27.nodes("nand") & self.c17.nodes("lat"))
        self.assertSetEqual(self.s27.nodes("ff"), set(["G7", "G6", "G5"]))
        self.assertSetEqual(
            self.s27.nodes("input"), set(["clk", "G0", "G1", "G2", "G3"])
        )
        self.assertSetEqual(self.s27.nodes(output=True), set(["G17"]))

    def test_add(self):
        c17_c = self.c17.copy()
        self.assertRaises(
            ValueError, c17_c.add, "test_ff", type="ff", fanin=["N1", "N2"]
        )
        self.assertRaises(ValueError, c17_c.add, "test_const", type="0", fanin=["N1"])

    def test_output(self):
        s27_c = self.s27.copy()
        s27_c.set_output("n_3")
        self.assertSetEqual(s27_c.nodes(output=True), set(["n_3", "G17"]))
        self.assertSetEqual(s27_c.nodes(output=True, types=["nor"]), set(["n_3"]))
        self.assertListEqual(s27_c.output(["G5", "G17"]), [False, True])
        s27_c.graph.add_node("test", type="or")
        self.assertRaises(KeyError, s27_c.output, "test")

    def test_contains(self):
        self.assertFalse("adsf" in self.s27)
        self.assertTrue("G7" in self.s27)

    def test_io(self):
        self.assertSetEqual(self.s27.io(), set(["clk", "G0", "G1", "G2", "G3", "G17"]))

    def test_is_cyclic(self):
        c = cg.Circuit()
        c.add("a", "buf")
        c.add("b", "buf", fanin="a", fanout="a")
        self.assertTrue(c.is_cyclic())
        self.assertFalse(self.c17.is_cyclic())

    def test_ff_lat(self):
        self.assertSetEqual(self.s27.ffs(), {"G5", "G6", "G7"})
        s27_c = self.s27.copy()
        s27_c.add("c_t", "input")
        s27_c.add("r_t", "input")
        s27_c.add("s_t", "input")
        s27_c.add("test_lat", "lat", fanin=["G5"], clk="c_t", r="r_t", s="s_t")
        self.assertSetEqual(s27_c.lats(), {"test_lat"})
        self.assertSetEqual(s27_c.seq(), {"G5", "G6", "G7", "test_lat"})
        self.assertEqual(s27_c.d("test_lat"), "G5")
        self.assertEqual(s27_c.clk("test_lat"), "c_t")
        self.assertEqual(s27_c.r("test_lat"), "r_t")
        self.assertEqual(s27_c.s("test_lat"), "s_t")
        s27_c.graph.add_node("test_node", type="or")
        self.assertRaises(KeyError, s27_c.r, ["test_node", "G5"])
        self.assertRaises(KeyError, s27_c.s, ["test_node", "G5"])
        self.assertRaises(KeyError, s27_c.d, ["test_node", "G5"])
        self.assertRaises(KeyError, s27_c.clk, ["test_node", "G5"])

    def test_seq_graph(self):
        g = self.s27.seq_graph()
        self.assertSetEqual(
            set(g.nodes), set(["G1", "G3", "clk", "G5", "G6", "G0", "G2", "G7", "G17"])
        )

    def test_disconnect(self):
        s27_c = self.s27.copy()
        s27_c.disconnect("G5", "n_1")
        self.assertSetEqual(s27_c.fanout("G5"), {"n_21", "n_20"})

    def test_remove(self):
        c17_c = self.c17.copy()
        c17_c.remove("G16")
        self.assertNotIn("G16", c17_c.nodes())
        self.assertSetEqual(c17_c.fanout("G8"), set())

    def test_edges(self):
        self.assertSetEqual(
            set(tuple((u, v)) for u, v in self.c17.edges()),
            set(
                tuple((u, v))
                for u, v in [
                    ("G8", "G16"),
                    ("G1", "G8"),
                    ("G3", "G8"),
                    ("G3", "G9"),
                    ("G9", "G12"),
                    ("G9", "G15"),
                    ("G4", "G9"),
                    ("G12", "G16"),
                    ("G12", "G17"),
                    ("G2", "G12"),
                    ("G15", "G17"),
                    ("G5", "G15"),
                ]
            ),
        )

    def test_type(self):
        self.assertTrue(self.s27.type("G7") == "ff")
        self.assertTrue(self.s27.type("n_4") == "nand")
        self.s27.set_type("n_4", "nor")
        self.assertTrue(self.s27.type("n_4") == "nor")
        self.assertListEqual(self.s27.type(["G7", "n_4"]), ["ff", "nor"])
        s27_c = self.s27.copy()
        s27_c.graph.add_node("temp")
        self.assertRaises(KeyError, s27_c.type, "temp")

    def test_endpoints(self):
        self.assertSetEqual(self.s27.endpoints(), set(["G5", "G6", "G7", "G17"]))
        self.assertSetEqual(self.s27.endpoints("n_20"), set(["G17"]))
        self.assertSetEqual(self.s27.endpoints(["n_20", "n_11"]), set(["G17", "G5"]))

    def test_startpoints(self):
        self.assertSetEqual(
            self.s27.startpoints(),
            set(["G5", "G6", "G7", "clk", "G0", "G1", "G2", "G3"]),
        )
        self.assertSetEqual(self.s27.startpoints("n_5"), set(["G6", "G0"]))
        self.assertSetEqual(self.s27.startpoints(["n_1", "n_2"]), set(["G5", "G0"]))

    def test_transitive_fanout(self):
        self.assertSetEqual(
            self.s27.transitive_fanout("G5"),
            set(["n_1", "G17", "G5", "n_12", "n_11", "n_9", "n_20", "G6", "n_21",]),
        )
        self.assertSetEqual(
            self.s27.transitive_fanout("G5", stopatTypes=["not", "nor"]),
            set(["n_1", "n_20", "n_21"]),
        )
        self.assertSetEqual(
            self.s27.transitive_fanout("G5", stopatNodes=["n_21", "n_20", "n_1"]),
            set(["n_1", "n_20", "n_21"]),
        )
        self.assertSetEqual(
            self.s27.transitive_fanout(
                "G5", stopatTypes=["not"], stopatNodes=["n_21", "n_20"]
            ),
            set(["n_1", "n_20", "n_21"]),
        )
        self.assertSetEqual(
            self.s27.transitive_fanout(["G5", "n_3"]),
            set(
                [
                    "n_6",
                    "G7",
                    "n_1",
                    "G17",
                    "G5",
                    "n_12",
                    "n_11",
                    "n_9",
                    "n_20",
                    "G6",
                    "n_21",
                ]
            ),
        )

    def test_transitive_fanin(self):
        self.assertSetEqual(self.s27.transitive_fanin("n_4"), set(["G3", "n_0", "G1"]))
        self.assertSetEqual(
            self.s27.transitive_fanin("n_4", stopatTypes=["not"]), set(["G3", "n_0"])
        )
        self.assertSetEqual(
            self.s27.transitive_fanin("n_4", stopatNodes=["n_0"]), set(["G3", "n_0"])
        )
        self.assertSetEqual(
            self.s27.transitive_fanin("n_4", stopatTypes=["not"], stopatNodes=["n_0"]),
            set(["n_0", "G3"]),
        )
        self.assertSetEqual(
            self.s27.transitive_fanin(["n_4", "n_3"]), set(["G3", "n_0", "G7", "G1"])
        )

    def test_clog2(self):
        self.assertEqual(clog2(9), 4)
        self.assertRaises(ValueError, clog2, 0)

    def test_int_to_bin(self):
        self.assertEqual(int_to_bin(5, 6), tuple(i == "1" for i in "000101"))
        self.assertEqual(int_to_bin(5, 6, True), tuple(i == "1" for i in "101000"))

    @unittest.skipIf(shutil.which("approxmc") == None, "Approxmc is not installed")
    def test_avg_sensitivity(self):
        c = cg.Circuit()
        c.add('and','and')
        c.add('in0','input',fanout='and')
        c.add('in1','input',fanout='and')
        self.assertEqual(c.avg_sensitivity('and'),1.0)

        avg_sen = self.s27.avg_sensitivity('G17',approx=False)

        # get startpoints of node
        avg_sen_comp = 0
        n = 'G17'
        sp = self.s27.startpoints(n)
        for s in sp:
            # compute influence
            infl = 0
            for vs in product([False, True], repeat=len(sp)):
                asmp = {i:v for i,v in zip(sp,vs)}
                asmp_ns = {i:v if i!=s else not v for i,v in zip(sp,vs)}
                r = cg.sat(self.s27,asmp)[n]
                r_ns = cg.sat(self.s27,asmp_ns)[n]
                if r!=r_ns:
                    infl +=1
            avg_sen_comp += infl/(2**len(sp))

        self.assertEqual(avg_sen,avg_sen_comp)




