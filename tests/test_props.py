import unittest
from itertools import product
from random import choice

import circuitgraph as cg


class TestProps(unittest.TestCase):
    def setUp(self):
        self.s27 = cg.tx.strip_blackboxes(cg.from_lib("s27"))

    def test_avg_sensitivity(self):
        c = cg.Circuit()
        c.add("and", "and")
        c.add("in0", "input", fanout="and")
        c.add("in1", "input", fanout="and")
        self.assertEqual(cg.props.avg_sensitivity(c, "and", approx=False), 1.0)

        avg_sen = cg.props.avg_sensitivity(self.s27, "G17", approx=False)

        # get startpoints of node
        avg_sen_comp = 0
        n = "G17"
        sp = self.s27.startpoints(n)
        for s in sp:
            # compute influence
            infl = 0
            for vs in product([False, True], repeat=len(sp)):
                asmp = dict(zip(sp, vs))
                asmp_ns = {i: v if i != s else not v for i, v in zip(sp, vs)}
                r = cg.sat.solve(self.s27, asmp)[n]
                r_ns = cg.sat.solve(self.s27, asmp_ns)[n]
                if r != r_ns:
                    infl += 1
            avg_sen_comp += infl / (2 ** len(sp))

        self.assertEqual(avg_sen, avg_sen_comp)

    def test_avg_sensitivity_supergates(self):
        c = cg.logic.adder(4, carry_in=True)
        total_influences = cg.props.avg_sensitivity(
            c, c.outputs(), approx=False, supergates=True
        )

        for n in c.outputs():
            avg_sen_comp = 0
            sp = c.startpoints(n)
            for s in sp:
                # compute influence
                infl = 0
                for vs in product([False, True], repeat=len(sp)):
                    asmp = dict(zip(sp, vs))
                    asmp_ns = {i: v if i != s else not v for i, v in zip(sp, vs)}
                    r = cg.sat.solve(c, asmp)[n]
                    r_ns = cg.sat.solve(c, asmp_ns)[n]
                    if r != r_ns:
                        infl += 1
                avg_sen_comp += infl / (2 ** len(sp))
            self.assertEqual(total_influences[n], avg_sen_comp)

    def test_sensitivity(self):
        # pick random node and input value
        n = choice(tuple(self.s27.nodes()))
        sp = self.s27.startpoints(n)
        while len(sp) < 1:
            n = choice(tuple(self.s27.nodes()))
            sp = self.s27.startpoints(n)

        # find sensitivity
        sen = cg.props.sensitivity(self.s27, n)

        # check
        sen_sim = 0
        for vs in product([False, True], repeat=len(sp)):
            input_sen = 0
            input_val = dict(zip(sp, vs))
            n_val = cg.sat.solve(self.s27, input_val)[n]
            for s in sp:
                flip_input_val = {i: v if i != s else not v for i, v in zip(sp, vs)}
                flip_n_val = cg.sat.solve(self.s27, flip_input_val)[n]
                if flip_n_val != n_val:
                    input_sen += 1
            sen_sim = max(sen_sim, input_sen)

        self.assertEqual(sen, sen_sim)

    def test_sensitize(self):
        # pick random node
        nr = choice(
            tuple(self.s27.nodes() - {"clk"} - self.s27.filter_type(["0", "1"]))
        )

        # pick startpoint
        ns = choice(tuple(self.s27.startpoints() - {"clk"}))

        # pick endpoint
        ne = choice(tuple(self.s27.endpoints() - {"clk"}))

        for n in [nr, ns, ne]:
            # get input
            input_val = cg.props.sensitize(self.s27, n, {f"c0_{n}": True})

            # simulate input
            result = cg.sat.solve(self.s27, input_val)
            self.assertTrue(result[n])

            # remove constrained input
            if n in input_val:
                input_val.pop(n)

            # simulate on faulty circuit
            c_f = self.s27.copy()
            c_f.disconnect(c_f.fanin(n), n)
            c_f.set_type(n, "input")
            result_f = cg.sat.solve(c_f, {**input_val, n: False})
            self.assertFalse(result_f[n])
            self.assertTrue(
                any(result_f[e] != result[e] for e in self.s27.endpoints(n))
            )

    def test_signal_probability(self):
        # pick random node
        n = choice(
            tuple(self.s27.nodes() - self.s27.startpoints() - self.s27.endpoints())
        )
        sp = self.s27.startpoints(n)

        # get signal prob
        p = cg.props.signal_probability(self.s27, n, approx=False)

        # compute prob
        m = 0
        for vs in product([False, True], repeat=len(sp)):
            asmp = dict(zip(sp, vs))
            m += cg.sat.solve(self.s27, asmp)[n]
        self.assertEqual(m / (2 ** len(sp)), p)

    def test_levelize(self):
        c = cg.Circuit()
        levels = {}
        levels[c.add("i0", "input")] = 0
        levels[c.add("i1", "input")] = 0
        levels[c.add("const0", "0")] = 0
        levels[c.add("g0", "and", fanin=["i0", "i1"])] = 1
        levels[c.add("g1", "and", fanin=["i0", "g0"])] = 2
        levels[c.add("g2", "or", output=True, fanin=["const0", "g1"])] = 3

        self.assertEqual(levels, cg.props.levelize(c))
