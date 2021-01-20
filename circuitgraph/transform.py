"""Functions for transforming circuits"""

from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
import os

import networkx as nx

from circuitgraph import Circuit
from circuitgraph.utils import clog2
from circuitgraph.logic import popcount
from circuitgraph.io import verilog_to_circuit, circuit_to_verilog


def copy(c):
    """
    Returns copy of a circuit.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit copy.

    """
    return Circuit(graph=c.graph.copy(), name=c.name, blackboxes=c.blackboxes.copy())


def strip_io(c):
    """
    Removes circuit's outputs and converts inputs to buffers for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for o in c.io():
        g.nodes[o]["type"] = "buf"

    return Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_outputs(c):
    """
    Removes a circuit's outputs for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for o in c.outputs():
        g.nodes[o]["type"] = "buf"

    return Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_inputs(c):
    """
    Converts inputs to buffers for easy
    instantiation.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io
    """
    g = c.graph.copy()
    for i in c.inputs():
        g.nodes[i]["type"] = "buf"

    return Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_blackboxes(c):
    """
    Converts blackboxes to io.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed blackboxes.
    """
    g = c.graph.copy()
    bb_pins = []
    for n in c.filter_type("bb_input"):
        g.nodes[n]["type"] = "output"
        bb_pins.append(n)
    for n in c.filter_type("bb_output"):
        g.nodes[n]["type"] = "input"
        bb_pins.append(n)

    # rename nodes
    mapping = {n: n.replace(".", "_") for n in bb_pins}
    for k in mapping.values():
        if k in g:
            raise ValueError(f"Overlapping blackbox name: {k}")
    nx.relabel_nodes(g, mapping, copy=False)

    return Circuit(graph=g, name=c.name)


def relabel(c):
    """
    Builds copy with relabeled nodes.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    mapping : dict of str:str
            Relabeling of nodes.

    Returns
    -------
    Circuit
            Circuit with removed blackboxes.
    """
    g = nx.relabel_nodes(g, mapping)
    return Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


# def seq_graph(c):
#    """
#    Creates a Circuit of the sequential elements and IO.
#
#    Parameters
#    ----------
#    c: Circuit
#
#    Returns
#    -------
#    Circuit
#            Sequential circuit.
#
#    """
#    s = Circuit(name=f"{c.name}_seq")
#
#    # add nodes
#    for n in c.inputs() | c.seq():
#        s.add(n, c.type(n), output=c.output(n))
#
#    # add edges
#    for n in c.seq():
#        s.connect(c.startpoints(c.d(n)), n)
#
#    # add outputs
#    for n in s:
#        if c.endpoints(n) & c.outputs():
#            s.set_output(n, True)
#
#    return s


def syn(c, engine="yosys", print_output=False):
    """
    Synthesizes the circuit using Genus.

    Parameters
    ----------
    c : Circuit
            Circuit to synthesize.
    engine : str
            Synthesis tool to use ('genus' or 'yosys')
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
            if engine == "genus":
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
            elif engine == "yosys":
                cmd = [
                    "yosys",
                    "-p",
                    f"read_verilog {tmp_in.name}; "
                    "synth; "
                    f"write_verilog -noattr {tmp_out.name}",
                ]

            else:
                raise ValueError("synthesis engine must be yosys or genus")

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
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")
    t = copy(c)

    # add dual nodes
    for n in c:
        if c.type(n) in ["and", "nand"]:
            t.add(f"{n}_x", "and")
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
            t.add(f"{n}_x", "and")
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
            t.add(f"{n}_x", "buf", fanin=f"{p}_x")

        elif c.type(n) in ["output"]:
            p = c.fanin(n).pop()
            t.add(f"{n}_x", "output", fanin=f"{p}_x")

        elif c.type(n) in ["xor", "xnor"]:
            t.add(f"{n}_x", "or", fanin=(f"{p}_x" for p in c.fanin(n)))

        elif c.type(n) in ["0", "1"]:
            t.add(f"{n}_x", "0")

        elif c.type(n) in ["input"]:
            t.add(f"{n}_x", "input")

        else:
            raise ValueError(f"Node {n} has unrecognized type: {c.type(n)}")

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
    # check for blackboxes
    if c0.blackboxes:
        raise ValueError(f"{c0.name} contains a blackbox")
    if c1 and c1.blackboxes:
        raise ValueError(f"{c1.name} contains a blackbox")

    # clean inputs
    if not c1:
        c1 = c0
    if not startpoints:
        startpoints = c0.startpoints() & c1.startpoints()
    if not endpoints:
        endpoints = c0.endpoints() & c1.endpoints()

    # create miter, relabel
    m = Circuit(name=f"miter_{c0.name}_{c1.name}")
    m.add_subcircuit(c0, "c0")
    m.add_subcircuit(c1, "c1")

    # tie inputs
    for n in startpoints:
        m.add(n, "input", fanout=[f"c0_{n}", f"c1_{n}"])

    # compare outputs
    m.add("miter", "or")
    m.add("sat", "output", fanin="miter")
    for n in endpoints:
        m.add(f"dif_{n}", "xor", fanin=[f"c0_{n}", f"c1_{n}"], fanout="miter")

    return m


# def comb(c):
#    """
#    Creates combinational version of the circuit.
#
#    Parameters
#    ----------
#    c : Circuit
#            Sequential circuit to make combinational.
#
#    Returns
#    -------
#    Circuit
#            Combinational circuit.
#
#    """
#    import circuitgraph.logic as logic
#
#    c_comb = copy(c)
#    lat_model = logic.comb_lat()
#    ff_model = logic.comb_ff()
#
#    for s in c.seq():
#        model = lat_model if c.type(s) == "lat" else ff_model
#        relabeled_model = relabel(model, {n: f"{s}_{n}" for n in model})
#        c_comb.extend(relabeled_model)
#        c_comb.connect(f"{s}_q", c_comb.fanout(s))
#        c_comb.connect(c_comb.fanin(s), f"{s}_d")
#        if c.clk(s):
#            c_comb.connect(c.clk(s), f"{s}_clk")
#        if c.r(s):
#            c_comb.connect(c.r(s), f"{s}_rst")
#        if c.s(s):
#            c_comb.connect(c.s(s), f"{s}_set")
#        c_comb.remove(s)
#
#    return c_comb


# def unroll(c, cycles):
#    """
#    Creates combinational unrolling of the circuit.
#
#    Parameters
#    ----------
#    c : Circuit
#            Sequential circuit to unroll.
#    cycles : int
#            Number of cycles to unroll
#
#    Returns
#    -------
#    Circuit
#            Unrolled circuit.
#
#    """
#    u = Circuit()
#    c_comb = comb(c)
#    for i in range(cycles):
#        u.extend(c_comb, {n: f"{n}_{i}" for n in c_comb})
#        if i == 0:
#            # convert si to inputs
#            for n in c:
#                if c.type(n) in ["lat", "ff"]:
#                    u.set_type(f"{n}_si_{i}", "input")
#
#        else:
#            # connect prev si
#            for n in c:
#                if c.type(n) in ["lat", "ff"]:
#                    u.connect(f"{n}_si_{i-1}", f"{n}_si_{i}")
#
#    return u


def influence_transform(c, n, s):
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
    # check for blackboxes
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")

    # check if s is in startpoints
    sp = c.startpoints(n)
    if s not in sp:
        raise ValueError(f"{s} is not in startpoints of {n}")

    # get input cone
    fi_nodes = c.transitive_fanin(n) | set([n])
    sub_c = Circuit("sub_cone", c.graph.subgraph(fi_nodes).copy())

    # create two copies of sub circuit, share inputs except s
    infl = Circuit(name=f"infl_{s}_on_{n}")
    infl.add_subcircuit(sub_c, "c0")
    infl.add_subcircuit(sub_c, "c1")
    for g in sp:
        if g != s:
            infl.add(g, "input", fanout=[f"c0_{g}", f"c1_{g}"])
        else:
            infl.add(f"not_{g}", "not", fanout=f"c1_{s}")
            infl.add(g, "input", fanout=[f"c0_{g}", f"not_{g}"])
    infl.add("dif", "xor", fanin=[f"c0_{n}", f"c1_{n}"])
    infl.add("sat", "output", fanin="dif")

    return infl


def sensitivity_transform(c, n):
    """
    Creates a circuit to compute sensitivity.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    n : str
            Node to compute sensitivity at.

    Returns
    -------
    Circuit
            Sensitivity circuit.

    """

    # check for blackboxes
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")

    # check for startpoints
    startpoints = c.startpoints(n)
    if len(startpoints) < 1:
        raise ValueError(f"{n} has no startpoints")

    # get input cone
    fi_nodes = c.transitive_fanin(n) | set([n])
    sub_c = Circuit(graph=c.graph.subgraph(fi_nodes).copy())

    # create sensitivity circuit
    sen = Circuit()
    sen.add_subcircuit(sub_c, "orig")
    for s in startpoints:
        sen.add(s, "input", fanout=f"orig_{s}")

    # add popcount
    sen.add_subcircuit(popcount(len(startpoints)), "pc")

    # add inverted input copies
    for i, s0 in enumerate(startpoints):
        sen.add_subcircuit(sub_c, f"inv_{s0}")

        # connect inputs
        for s1 in startpoints:
            if s0 != s1:
                sen.connect(s1, f"inv_{s0}_{s1}")
            else:
                # connect inverted input
                sen.set_type(f"inv_{s0}_{s1}", "not")
                sen.connect(s0, f"inv_{s0}_{s1}")

        # compare to orig
        sen.add(
            f"dif_{s0}",
            "xor",
            fanin=[f"orig_{n}", f"inv_{s0}_{n}"],
            fanout=f"pc_in_{i}",
        )
        sen.add(f"dif_out_{s0}", "output", fanin=f"dif_{s0}")

    # instantiate population count
    for o in range(clog2(len(startpoints) + 1)):
        sen.add(f"sen_out_{o}", "output", fanin=f"pc_out_{o}")

    return sen


def sensitization_transform(c, n):
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
    # create miter
    m = miter(c)
    m.name = f"{c.name}_sensitized_{n}"

    # flip node in c1
    m.disconnect(m.fanin(f"c1_{n}"), f"c1_{n}")
    m.set_type(f"c1_{n}", "not")
    m.connect(f"c0_{n}", f"c1_{n}")

    return m
