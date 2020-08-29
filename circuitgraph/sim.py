"""Functions for simulating circuits using Verilator"""

from tempfile import NamedTemporaryFile

import pyverilator

from circuitgraph.io import circuit_to_verilog
from circuitgraph.transform import copy


def construct_simulator(c):
    """
    Constructs a PyVerilator instance.

    Parameters
    ----------
    c : Circuit
            Circuit to simulate.

    Returns
    -------
    PyVerilator
            Simulation instance.
    """
    # make all nodes outputs for PyVerilator interfacing
    c_out = copy(c)
    c_out.set_output(c_out.nodes() - c_out.inputs(), True)
    verilog = circuit_to_verilog(c_out)

    with NamedTemporaryFile(suffix=".v") as tmp:
        tmp.write(bytes(verilog, "ascii"))
        tmp.flush()
        sim = pyverilator.PyVerilator.build(tmp.name)

    return sim


def sim(c, vectors):
    """
    Simulates circuit with given values

    Parameters
    ----------
    c : Circuit
            Circuit to simulate.
    vectors : iter of dict of str:bool
            Iterable of values to force in the simulation.

    Returns
    -------
    iter of dict of str:bool
            Output values.
    """
    sim = construct_simulator(c)

    for vector in vectors:
        for n, v in vector.items():
            sim[n] = v
        outs = {n: sim[n] for n in c.nodes() - c.inputs()}
        yield {**outs, **vector}
