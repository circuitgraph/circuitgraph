"""A collection of common logic elements as `Circuit` objects"""

from itertools import product

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

    i = 0
    while len(ps) > 1:
        # get values
        ns = ps.pop(0)
        ms = ps.pop(0)

        # pad
        aw = max(len(ns), len(ms))
        while len(ms) < aw:
            ms += ["null"]
        while len(ns) < aw:
            ns += ["null"]

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

    if "null" in c:
        c.set_type("null", "0")

    return c


# def comb_lat():
#    """
#    Combinational model of a latch.
#
#    Returns
#    -------
#    Circuit
#            Latch model circuit.
#    """
#    lm = Circuit(name="lat")
#
#    # mux
#    m = strip_io(mux(2))
#    lm.extend(m, {n: f"mux_{n}" for n in m.nodes()})
#
#    # inputs
#    lm.add("si", "input", fanout="mux_in_0")
#    lm.add("d", "input", fanout="mux_in_1")
#    lm.add("clk", "input", fanout="mux_sel_0")
#    lm.add("r", "input")
#    lm.add("s", "input")
#
#    # logic
#    lm.add("r_b", "not", fanin="r")
#    lm.add("qr", "and", fanin=["mux_out", "r_b"])
#    lm.add("q", "or", fanin=["qr", "s"], output=True)
#    lm.add("so", "buf", fanin="q", output=True)
#
#    return lm
#
#
# def comb_ff():
#    """
#    Combinational model of a flip-flop.
#
#    Returns
#    -------
#    Circuit
#            Flip-flop model circuit.
#    """
#    fm = Circuit(name="ff")
#
#    # mux
#    m = strip_io(mux(2))
#    fm.extend(m, {n: f"mux_{n}" for n in m.nodes()})
#
#    # inputs
#    fm.add("si", "input", fanout="mux_in_1")
#    fm.add("d", "input", fanout="mux_in_0")
#    fm.add("clk", "input", fanout="mux_sel_0")
#    fm.add("r", "input")
#    fm.add("s", "input")
#
#    # logic
#    fm.add("r_b", "not", fanin="r")
#    fm.add("qr", "and", fanin=["si", "r_b"])
#    fm.add("q", "or", fanin=["qr", "s"], output=True)
#    fm.add("so", "buf", fanin="mux_out", output=True)
#
#    return fm
