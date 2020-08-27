"""Functions for transforming circuits"""

import math
import code
from subprocess import PIPE, Popen
import subprocess
from tempfile import NamedTemporaryFile
from random import sample
import os
import shutil

import networkx as nx

from circuitgraph import Circuit
from circuitgraph.utils import clog2, lint
from circuitgraph.io import verilog_to_circuit, circuit_to_verilog


def relabel(c, mapping):
    """
    Returns renamed copy of a circuit.

    Parameters
    ----------
    c: Circuit
            circuit to rename
    mapping : dict of str:str
            mapping of old to new names

    Returns
    -------
    Circuit
            Relabeled circuit.

    """
    return Circuit(graph=nx.relabel_nodes(c.graph, mapping), name=c.name)


def strip_io(c):
    """
    Removes a circuit's outputs and converts inputs to buffers for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            circuit to strip io from

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for o in c.outputs():
        g.nodes[o]["output"] = False
    for i in c.inputs():
        g.nodes[i]["type"] = "buf"

    return Circuit(graph=g, name=c.name)


def strip_outputs(c):
    """
    Removes a circuit's outputs for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            circuit to strip io from

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for o in c.outputs():
        g.nodes[o]["output"] = False

    return Circuit(graph=g, name=c.name)


def strip_inputs(c):
    """
    Converts inputs to buffers for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            circuit to strip inputs from

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for i in c.inputs():
        g.nodes[i]["type"] = "buf"

    return Circuit(graph=g, name=c.name)


def seq_graph(c):
    """
    Creates a Circuit of the sequential elements and IO.

    Parameters
    ----------
    c: Circuit

    Returns
    -------
    Circuit
            Sequential circuit.

    """
    s = Circuit(name=f"{c.name}_seq")

    # add nodes
    for n in c.io() | c.seq():
        s.add(n, c.type(n))

    # add edges
    for n in s:
        s.connect(c.startpoints(n), n)

    return s


def syn(c, engine, print_output=False):
    """
    Synthesizes the circuit using Genus.

    Parameters
    ----------
    c : Circuit
            Circuit to synthesize.
    engine : str
            Synthesis tool to use ('Genus' or 'Yosys')
    print_output : bool
            Option to print synthesis log

    Returns
    -------
    Circuit
            Synthesized circuit.
    """
    verilog = circuit_to_verilog(c)

    with NamedTemporaryFile(prefix="circuitgraph_syn_genus_input") as tmp_in:
        tmp_in.write(bytes(verilog, "ascii"))
        tmp_in.flush()
        with NamedTemporaryFile(prefix="circuitgraph_syn_genus_output") as tmp_out:
            if engine == "Genus":
                cmd = [
                    "genus",
                    "-no_gui",
                    "-execute",
                    "set_db / .library "
                    f"{os.environ['CIRCUITGRAPH_GENUS_LIBRARY_PATH']};\n"
                    f"read_hdl -sv {tmp_in.name};\n"
                    "elaborate;\n"
                    "set_db syn_generic_effort high;\n"
                    "syn_generic;\n"
                    "syn_map;\n"
                    "syn_opt;\n"
                    f'redirect {tmp_out.name} "write_hdl -generic";\n'
                    "exit;",
                ]
            elif engine == "Yosys":
                cmd = [
                    "yosys",
                    "-p",
                    f"read_verilog {tmp_in.name}; "
                    "proc; opt; fsm; opt; memory; opt; clean; "
                    f"write_verilog -noattr {tmp_out.name}",
                ]

            else:
                raise ValueError("synthesis engine must be Yosys or Genus")

            process = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
            while True:
                line = process.stdout.readline()
                if line == "" and process.poll() is not None:
                    break
                if line:
                    if print_output:
                        print(line.strip())
            output = tmp_out.read().decode("utf-8")
            if print_output:
                print(output)

    return verilog_to_circuit(output, c.name)


def ternary(c):
    """
    Encodes the circuit with ternary values

    Parameters
    ----------
    c : Circuit
            Circuit to encode.

    Returns
    -------
    Circuit
            Encoded circuit.

    """
    t = c.copy()

    # add dual nodes
    for n in c:
        if c.type(n) in ["and", "nand"]:
            t.add(f"{n}_x", "and", output=c.output(n))
            t.add(
                f"{n}_x_in_fi",
                "or",
                fanout=f"{n}_x",
                fanin=[f"{p}_x" for p in c.fanin(n)],
            )
            t.add(f"{n}_0_not_in_fi", "nor", fanout=f"{n}_x")

            for p in c.fanin(n):
                t.add(
                    f"{p}_is_0", "nor", fanout=f"{n}_0_not_in_fi", fanin=[p, f"{p}_x"]
                )

        elif c.type(n) in ["or", "nor"]:
            t.add(f"{n}_x", "and", output=c.output(n))
            t.add(
                f"{n}_x_in_fi",
                "or",
                fanout=f"{n}_x",
                fanin=[f"{p}_x" for p in c.fanin(n)],
            )
            t.add(f"{n}_1_not_in_fi", "nor", fanout=f"{n}_x")

            for p in c.fanin(n):
                t.add(f"{p}_is_1", "and", fanout=f"{n}_1_not_in_fi", fanin=p)
                t.add(f"{p}_not_x", "not", fanout=f"{p}_is_1", fanin=f"{p}_x")

        elif c.type(n) in ["buf", "not"]:
            p = c.fanin(n).pop()
            t.add(f"{n}_x", "buf", output=c.output(n), fanin=f"{p}_x")

        elif c.type(n) in ["xor", "xnor"]:
            t.add(
                f"{n}_x", "or", output=c.output(n), fanin=(f"{p}_x" for p in c.fanin(n))
            )

        elif c.type(n) in ["0", "1"]:
            t.add(f"{n}_x", "0", output=c.output(n))

        elif c.type(n) in ["input"]:
            t.add(f"{n}_x", "input", output=c.output(n))

        elif c.type(n) in ["ff", "lat"]:
            t.add(
                f"{n}_x",
                c.type(n),
                output=c.output(n),
                clk=f"{c.clk(n)}_x",
                r=f"{c.r(n)}_x",
                s=f"{c.s(n)}_x",
                fanin=f"{c.fanin(n).pop()}_x",
            )

        elif c.type(n) in ["0", "1"]:
            continue

    return t


def miter(c0, c1=None, startpoints=None, endpoints=None):
    """
    Creates a miter circuit

    Parameters
    ----------
    c0 : Circuit
            First circuit.
    c1 : Circuit
            Optional second circuit, if None c0 is mitered with itself.
    startpoints : set of str
            Nodes to be tied together, must exist in both circuits.
    endpoints : set of str
            Nodes to be compared, must exist in both circuits.

    Returns
    -------
    Circuit
            Miter circuit.
    """
    if not c1:
        c1 = c0
    if not startpoints:
        startpoints = c0.startpoints() & c1.startpoints()
    if not endpoints:
        endpoints = c0.endpoints() & c1.endpoints()

    # create miter, relabel to avoid overlap except for common startpoints
    m = relabel(c0, {n: f"c0_{n}" for n in c0.nodes() - startpoints})
    m.extend(relabel(c1, {n: f"c1_{n}" for n in c1.nodes() - startpoints}))

    # compare outputs
    # FIXME: Make sure this is robust to corner cases
    m.add("sat", "or", output=True)
    for o in endpoints:
        if c0.type(o) in ["lat", "ff"]:
            if c0.d(o) not in startpoints:
                m.add(
                    f"miter_{o}",
                    "xor",
                    fanin=[f"c0_{c0.d(o)}", f"c1_{c1.d(o)}"],
                    fanout=["sat"],
                )
        else:
            m.add(f"miter_{o}", "xor", fanin=[f"c0_{o}", f"c1_{o}"], fanout=["sat"])

    return m


def comb(c):
    """
    Creates combinational version of the circuit.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to make combinational.

    Returns
    -------
    Circuit
            Combinational circuit.

    """
    import circuitgraph.logic as logic

    c_comb = c.copy()
    lat_model = logic.comb_lat()
    ff_model = logic.comb_ff()

    for lat in c.lats():
        relabeled_model = relabel(lat_model, {n: f"{lat}_{n}" for n in lat_model})
        c_comb.extend(relabeled_model)
        c_comb.graph.add_edges_from(
            (f"{lat}_q", s) for s in c_comb.graph.successors(lat)
        )
        c_comb.graph.add_edges_from(
            (p, f"{lat}_d") for p in c_comb.graph.predecessors(lat)
        )
        c_comb.graph.add_edge(c.clk(lat), f"{lat}_clk")
        c_comb.graph.add_edge(c.r(lat), f"{lat}_rst")
        c_comb.graph.remove_node(lat)

    for ff in c.ffs():
        relabeled_model = relabel(ff_model, {n: f"{ff}_{n}" for n in ff_model})
        c_comb.extend(relabeled_model)
        c_comb.graph.add_edges_from((f"{ff}_q", s) for s in c_comb.graph.successors(ff))
        c_comb.graph.add_edges_from(
            (p, f"{ff}_d") for p in c_comb.graph.predecessors(ff)
        )
        c_comb.graph.add_edge(c.clk(ff), f"{ff}_clk")
        c_comb.graph.remove_node(ff)

    return c_comb


def unroll(c, cycles):
    """
    Creates combinational unrolling of the circuit.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    cycles : int
            Number of cycles to unroll

    Returns
    -------
    Circuit
            Unrolled circuit.

    """
    u = Circuit()
    c_comb = comb(c)
    for i in range(cycles):
        u.extend(c_comb, {n: f"{n}_{i}" for n in c_comb})
        if i == 0:
            # convert si to inputs
            for n in c:
                if c.type(n) in ["lat", "ff"]:
                    u.set_type(f"{n}_si_{i}", "input")

        else:
            # connect prev si
            for n in c:
                if c.type(n) in ["lat", "ff"]:
                    u.connect(f"{n}_si_{i-1}", f"{n}_si_{i}")

    return u


def influence(c, n, s):
    """
    Creates a circuit to compute sensitivity.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    n : str
            Node to compute influence at.
    s : str
            Startpoint to compute influence for.

    Returns
    -------
    Circuit
            Influence circuit.

    """
    # check if s is in startpoints
    sp = c.startpoints(n)
    if s not in sp:
        raise ValueError(f"{s} is not in startpoints of {n}")

    # get input cone
    fiNodes = c.transitive_fanin(n) | set([n])
    sub_c = Circuit(c.graph.subgraph(fiNodes).copy())

    # remove outs, convert startpoints
    sub_c.set_output(sub_c.outputs(), False)
    sub_c.set_type(sub_c.startpoints(), "input")

    # create two copies of sub circuit
    infl = Circuit(name=f"infl_{s}_on_{n}")
    infl.extend(sub_c)
    infl.extend(relabel(sub_c, {g: f"s1_{g}" for g in sub_c if g not in sp - set([s])}))
    infl.add("sat", "xor", fanin=[n, f"s1_{n}"], output=True)
    infl.add(f"not_{s}", "not", fanin=s, fanout=f"s1_{s}")

    return infl


def sensitivity(c, n, startpoints=None):
    """
    Creates a circuit to compute sensitivity.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    n : str
            Node to compute sensitivity at.
    startpoints : iterable of str
            startpoints of n to flip.

    Returns
    -------
    Circuit
            Sensitivity circuit.

    """
    import circuitgraph.logic as logic

    # choose all startpoints if not specified
    if startpoints is None:
        startpoints = c.startpoints(n)
    all_startpoints = c.startpoints(n)

    # get fanin cone of node
    if n in c.startpoints():
        raise ValueError(f"{n} is in startpoints")

    # get input cone
    fiNodes = c.transitive_fanin(n) | set([n])
    sub_c = Circuit(c.graph.subgraph(fiNodes).copy())

    # remove outs, convert startpoints
    sub_c.set_output(sub_c.outputs(), False)
    sub_c.set_type(sub_c.startpoints(), "input")
    sub_c.disconnect(sub_c.nodes(), sub_c.startpoints())

    # create sensitivity circuit and add first copy of subcircuit
    sen = Circuit()
    sen.extend(sub_c)

    # instantiate population count
    p = strip_io(logic.popcount(len(startpoints)))
    p = relabel(p, {g: f"pop_{g}" for g in p})
    sen.extend(p)
    for o in range(clog2(len(startpoints) + 1)):
        sen.add(f"out_{o}", "buf", fanin=f"pop_out_{o}", output=True)

    # stamp out a copies of the circuit with s inverted
    for i, s in enumerate(startpoints):
        mapping = {
            g: f"sen_{s}_{g}" for g in sub_c if g not in all_startpoints - set([s])
        }
        sen.extend(relabel(sub_c, mapping))

        # connect inverted input
        sen.set_type(f"sen_{s}_{s}", "not")
        sen.connect(s, f"sen_{s}_{s}")

        # compare to first copy
        sen.add(
            f"difference_{s}",
            "xor",
            fanin=[n, f"sen_{s}_{n}"],
            fanout=f"pop_in_{i}",
            output=True,
        )

    return sen


def sensitize(c, n):
    """
    Creates a circuit to sensitize a node to an endpoint.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    n : str
            Node to sensitize.

    Returns
    -------
    Circuit
            Output circuit.

    """
    # get fanin/out cone of node
    nodes = c.transitive_fanin(n) | c.transitive_fanout(n) | set([n])
    subCircuit = Circuit(c.graph.subgraph(nodes).copy())

    # create miter
    m = miter(subCircuit)

    # cut and invert n in one side of miter
    m.graph.nodes[f"c1_{n}"]["type"] = "not"
    m.graph.remove_edges_from((f, f"c1_{n}") for f in m.fanin(f"c1_{n}"))
    m.graph.add_edge(f"c0_{n}", f"c1_{n}")

    return m
