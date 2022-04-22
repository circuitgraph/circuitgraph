"""
A collection of common logic elements as `Circuit` objects.

They can be added to existing circuits using `Circuit.add_subcircuit`

Examples
--------
Either add `a` and `c` or `b` and `c` depending on `sel`.

>>> import circuitgraph as cg

>>> a = cg.logic.half_adder()
>>> m = cg.logic.mux(2)

>>> c = cg.Circuit()
>>> c.add("a", "input")
'a'
>>> c.add("b", "input")
'b'
>>> c.add("c", "input")
'c'
>>> c.add("sel", "input")
'sel'
>>> c.add("d", "buf")
'd'
>>> c.add("sum", "buf", output=True)
'sum'
>>> c.add("carry", "buf", output=True)
'carry'

Add mux subcircuit

>>> mux_conns = {"in_0": "a", "in_1": "b", "sel_0": "sel", "out": "d"}
>>> c.add_subcircuit(m, "mux", mux_conns)

Add adder subcircuit

>>> add_conns = {"x": "c", "y": "d", "c": "carry", "s": "sum"}
>>> c.add_subcircuit(a, "adder", add_conns)

Simulate to verify

>>> res = cg.sat.solve(c, {"a": 0, "b": 1, "c": 1, "sel": 0}) # a + c
>>> res["sum"]
True
>>> res["carry"]
False

>>> res = cg.sat.solve(c, {"a": 0, "b": 1, "c": 1, "sel": 1}) # b + c
>>> res["sum"]
False
>>> res["carry"]
True

"""
from itertools import product

import circuitgraph as cg


def half_adder():
    """
    Create an AND/XOR half adder.

    Returns
    -------
    Circuit
            Half adder circuit.

    """
    c = cg.Circuit(name="half_adder")
    ins = [c.add("x", "input"), c.add("y", "input")]
    c.add("c", "and", fanin=ins, output=True)
    c.add("s", "xor", fanin=ins, output=True)
    return c


def full_adder():
    """
    Create a full adder from two half adders.

    Returns
    -------
    Circuit
            Full adder circuit.

    """
    c = cg.Circuit("full_adder")
    c.add("x", "input")
    c.add("y", "input")
    c.add("cin", "input")

    c.add_subcircuit(half_adder(), "x_y_ha", connections={"x": "x", "y": "y"})
    c.add_subcircuit(
        half_adder(), "cin_s_ha", connections={"x": "x_y_ha_s", "y": "cin"}
    )

    c.add("cout", "or", fanin=["x_y_ha_c", "cin_s_ha_c"], output=True)
    c.add("s", "buf", fanin="cin_s_ha_s", output=True)
    return c


def adder(width, carry_in=False, carry_out=False):
    """
    Create a ripple carry adder.

    Parameters
    ----------
    width : int
            Input width of adder.
    carry_in: bool
            Add a carry input.
    carry_out: bool
            Add a carry output.

    Returns
    -------
    Circuit
            Adder circuit.

    """
    c = cg.Circuit(name="adder")
    carry = c.add("cin", "input" if carry_in else "0")
    for bit in range(width):
        a = c.add(f"a_{bit}", "input")
        b = c.add(f"b_{bit}", "input")
        out = c.add(f"out_{bit}", "buf", output=True)
        c.add_subcircuit(
            full_adder(), f"fa_{bit}", {"x": a, "y": b, "cin": carry, "s": out}
        )
        carry = f"fa_{bit}_cout"

    if carry_out:
        c.add("cout", "buf", fanin=carry, output=True)
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
    c = cg.Circuit(name="mux")

    # create inputs
    for i in range(w):
        c.add(f"in_{i}", "input")
    sels = []
    for i in range(cg.utils.clog2(w)):
        c.add(f"sel_{i}", "input")
        c.add(f"not_sel_{i}", "not", fanin=f"sel_{i}")
        sels.append([f"not_sel_{i}", f"sel_{i}"])

    # create output or
    c.add("out", "or", output=True)

    i = 0
    for sel in product(*sels[::-1]):
        c.add(f"and_{i}", "and", fanin=[*sel, f"in_{i}"], fanout="out")

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
    c = cg.Circuit(name="popcount")
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
        c.add_subcircuit(adder(aw, carry_out=True), f"add_{i}")
        c.relabel({f"add_{i}_cout": f"add_{i}_out_{aw}"})
        for j, (n, m) in enumerate(zip(ns, ms)):
            c.connect(n, f"add_{i}_a_{j}")
            c.connect(m, f"add_{i}_b_{j}")

        # add adder outputs
        ps.append([f"add_{i}_out_{j}" for j in range(aw + 1)])
        i += 1

    # connect outputs
    for i, o in enumerate(ps[0]):
        c.add(f"out_{i}", "buf", fanin=o, output=True)

    if not c.fanout("tie0"):
        c.remove("tie0")

    return c
