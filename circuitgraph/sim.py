"""Functions for simulating circuits using Verilator"""

import pyverilator
from circuitgraph.io import circuit_to_verilog
from tempfile import NamedTemporaryFile


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

    verilog = circuit_to_verilog(c)

    with NamedTemporaryFile(suffix='.v') as tmp:
        tmp.write(bytes(verilog, 'ascii'))
        tmp.flush()
        sim = pyverilator.PyVerilator.build(tmp.name)

    return sim


def sim(c, forced):
    """
    Simulates circuit with given values

    Parameters
    ----------
    c : Circuit
            Circuit to simulate.
    forced : dict of str:bool
            Values to force in the simulation.

    Returns
    -------
    dict of str:bool
            Output values.
    """
    sim = construct_simulator(c)

    for n, v in forced.items():
        sim[n] = v

    return {n: sim[n.replace('output[', '')[:-1]] for n in c.outputs()}
