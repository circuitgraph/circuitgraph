"""A collection of common logic elements as `Circuit` objects"""

from itertools import product
from random import random

from circuitgraph import Circuit
from circuitgraph.utils import clog2


def adder(w):
    """
    Create an adder.

    Parameters
    ----------
    w : int
            Input width of adder.

    Returns
    -------
    Circuit
            Adder circuit.
    """
    c = Circuit(name="adder")
    carry = c.add("null", "0")
    for i in range(w):
        # sum
        c.add(f"a_{i}", "input")
        c.add(f"b_{i}", "input")
        c.add(f"sum_{i}", "xor", fanin=[f"a_{i}", f"b_{i}", carry])
        c.add(f"out_{i}", "output", fanin=f"sum_{i}")

        # carry
        c.add(f"and_ab_{i}", "and", fanin=[f"a_{i}", f"b_{i}"])
        c.add(f"and_ac_{i}", "and", fanin=[f"a_{i}", carry])
        c.add(f"and_bc_{i}", "and", fanin=[f"b_{i}", carry])
        carry = c.add(
            f"carry_{i}", "or", fanin=[f"and_ab_{i}", f"and_ac_{i}", f"and_bc_{i}"],
        )

    c.add(f"out_{w}", "output", fanin=carry)
    return c


def mux(w):
    """
    Create a mux.

    Parameters
    ----------
    w : int
            Input width of the mux.

    Returns
    -------
    Circuit
            Mux circuit.
    """
    c = Circuit(name="mux")

    # create inputs
    for i in range(w):
        c.add(f"in_{i}", "input")
    sels = []
    for i in range(clog2(w)):
        c.add(f"sel_{i}", "input")
        c.add(f"not_sel_{i}", "not", fanin=f"sel_{i}")
        sels.append([f"not_sel_{i}", f"sel_{i}"])

    # create output or
    c.add("or", "or")
    c.add("out", "output", fanin="or")

    i = 0
    for sel in product(*sels[::-1]):
        c.add(f"and_{i}", "and", fanin=[*sel, f"in_{i}"], fanout="or")

        i += 1
        if i == w:
            break

    return c


def popcount(w):
    """
    Create a population count circuit.

    Parameters
    ----------
    w : int
            Input width of the circuit.

    Returns
    -------
    Circuit
            Population count circuit.
    """
    c = Circuit(name="popcount")
    ps = [[c.add(f"in_{i}", "input")] for i in range(w)]
    c.add("tie0", "0")

    i = 0
    while len(ps) > 1:
        # get values
        ns = ps.pop(0)
        ms = ps.pop(0)

        # pad
        aw = max(len(ns), len(ms))
        while len(ms) < aw:
            ms += ["tie0"]
        while len(ns) < aw:
            ns += ["tie0"]

        # instantiate and connect adder
        c.add_subcircuit(adder(aw), f"add_{i}")
        for j, (n, m) in enumerate(zip(ns, ms)):
            c.connect(n, f"add_{i}_a_{j}")
            c.connect(m, f"add_{i}_b_{j}")

        # add adder outputs
        ps.append([f"add_{i}_out_{j}" for j in range(aw + 1)])
        i += 1

    # connect outputs
    for i, o in enumerate(ps[0]):
        c.add(f"out_{i}", "output", fanin=o)

    if not c.fanout("tie0"):
        c.remove("tie0")

    return c


def xor_hash(n, m):
    """
    Create a XOR hash function H_{xor}(n,m,3) as in:
    Chakraborty, Supratik, Kuldeep S. Meel, and Moshe Y. Vardi. "A scalable approximate model counter." International Conference on Principles and Practice of Constraint Programming. Springer, Berlin, Heidelberg, 2013.

    Each output of the hash is the xor/xnor of a random subset of the input.

    Parameters
    ----------
    n : int
            Input width of the hash function.
    m : int
            Output width of the hash function.

    Returns
    -------
    Circuit
            XOR hash function.
    """

    h = Circuit()

    for i in range(n):
        h.add(f"in_{i}", "input")

    for o in range(m):
        h.add(f"out_{o}", "output")

        # select inputs
        cons = [random() < 0.5 for i in range(n)]

        if sum(cons) == 0:
            # constant output
            h.add(f"c_{o}", "1" if random() < 0.5 else "0", fanout=f"out_{o}")
        else:
            # choose between xor/xnor
            h.add(f"xor_{o}", "xor", fanout=f"out_{o}")
            h.add(f"c_{o}", "1" if random() < 0.5 else "0", fanout=f"xor_{o}")
            for i, con in enumerate(cons):
                if con:
                    h.connect(f"in_{i}", f"xor_{o}")

    return h


def banyan(bw):
    """
    Create a Banyan switching network

    Parameters
    ----------
    bw : int
            Input/output width of the network.

    Returns
    -------
    Circuit
            Network circuit.
    """

    b = Circuit()

    # generate switch
    m = mux(2)
    s = Circuit(name="switch")
    s.add_subcircuit(m, f"m0")
    s.add_subcircuit(m, f"m1")
    s.add("in_0", "buf", fanout=["m0_in_0", "m1_in_1"])
    s.add("in_1", "buf", fanout=["m0_in_1", "m1_in_0"])
    s.add("out_0", "buf", fanin="m0_out")
    s.add("out_1", "buf", fanin="m1_out")
    s.add("sel", "input", fanout=["m0_sel_0", "m1_sel_0"])

    # generate banyan
    I = int(2 * clog2(bw) - 2)
    J = int(bw / 2)

    # add switches
    for i in range(I * J):
        b.add_subcircuit(s, f"swb_{i}")

    # make connections
    swb_ins = [f"swb_{i//2}_in_{i%2}" for i in range(I * J * 2)]
    swb_outs = [f"swb_{i//2}_out_{i%2}" for i in range(I * J * 2)]

    # connect switches
    for i in range(clog2(J)):
        r = J / (2 ** i)
        for j in range(J):
            t = (j % r) >= (r / 2)
            # straight
            out_i = int((i * bw) + (2 * j) + t)
            in_i = int((i * bw + bw) + (2 * j) + t)
            b.connect(swb_outs[out_i], swb_ins[in_i])

            # cross
            out_i = int((i * bw) + (2 * j) + (1 - t) + ((r - 1) * ((1 - t) * 2 - 1)))
            in_i = int((i * bw + bw) + (2 * j) + (1 - t))
            b.connect(swb_outs[out_i], swb_ins[in_i])

            if r > 2:
                # straight
                out_i = int(((I * J * 2) - ((2 + i) * bw)) + (2 * j) + t)
                in_i = int(((I * J * 2) - ((1 + i) * bw)) + (2 * j) + t)
                b.connect(swb_outs[out_i], swb_ins[in_i])

                # cross
                out_i = int(
                    ((I * J * 2) - ((2 + i) * bw))
                    + (2 * j)
                    + (1 - t)
                    + ((r - 1) * ((1 - t) * 2 - 1))
                )
                in_i = int(((I * J * 2) - ((1 + i) * bw)) + (2 * j) + (1 - t))
                b.connect(swb_outs[out_i], swb_ins[in_i])

    # create banyan io
    net_ins = swb_ins[:bw]
    net_outs = swb_outs[-bw:]

    for i, net_in in enumerate(net_ins):
        b.add(f"in_{i}", "input", fanout=net_in)
    for i, net_out in enumerate(net_outs):
        b.add(f"out_{i}", "output", fanin=net_out)
    for i in range(I * J):
        b.add(f"sel_{i}", "input", fanout=f"swb_{i}_sel")

    return b
