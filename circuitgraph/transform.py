"""Functions for transforming circuits"""

import subprocess
from tempfile import NamedTemporaryFile
import os
from pathlib import Path

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


def strip_blackboxes(c, ignore_pins=None):
    """
    Converts blackboxes to io.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    ingnore_pins: str or list of str
            Pins to not create io for, just disconnect and delete.

    Returns
    -------
    Circuit
            Circuit with removed blackboxes.
    """
    if not ignore_pins:
        ignore_pins = []
    elif isinstance(ignore_pins, str):
        ignore_pins = [ignore_pins]
    g = c.graph.copy()
    bb_pins = []
    for n in c.filter_type("bb_input"):
        if n.split(".")[-1] in ignore_pins:
            g.remove_node(n)
        else:
            g.nodes[n]["type"] = "output"
            bb_pins.append(n)
    for n in c.filter_type("bb_output"):
        if n.split(".")[-1] in ignore_pins:
            g.remove_node(n)
        else:
            g.nodes[n]["type"] = "input"
            bb_pins.append(n)

    # rename nodes
    mapping = {n: n.replace(".", "_") for n in bb_pins}
    for k in mapping.values():
        if k in g:
            raise ValueError(f"Overlapping blackbox name: {k}")
    nx.relabel_nodes(g, mapping, copy=False)

    return Circuit(graph=g, name=c.name)


def relabel(c, mapping):
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
    g = nx.relabel_nodes(c.graph, mapping)
    return Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def subcircuit(c, nodes):
    """
    Creates a subcircuit from a set of nodes of a given circuit.

    Parameters
    ----------
    c: Circuit
            The circuit to create a subcircuit from.
    nodes: list of str
            The nodes to include in the subcircuit.

    Returns
    -------
    Circuit
            The subcircuit.
    """
    sc = Circuit()
    for node in nodes:
        if c.type(node) in ["bb_output", "bb_input"]:
            raise NotImplementedError("Cannot create a subcircuit with blackboxes")
        sc.add(node, type=c.type(node))
    for edge in c.edges():
        if edge[0] in nodes and edge[1] in nodes:
            sc.connect(edge[0], edge[1])
    return sc


def syn(
    c,
    engine="yosys",
    suppress_output=False,
    stdout_file=None,
    stderr_file=None,
    working_dir=".",
    fast_parsing=False,
    pre_syn_file=None,
    post_syn_file=None,
    verilog_exists=False,
    effort="high",
):
    """
    Synthesizes the circuit using yosys or genus.

    Parameters
    ----------
    c : Circuit
            Circuit to synthesize.
    engine : str
            Synthesis tool to use ('genus', 'dc', or 'yosys')
    suppress_output: bool
            If True, synthesis stdout will not be printed.
    stdout_file: file or str or None
            If defined, synthesis stdout will be directed to this file instead
            of being printed.
    output_file: file or str or None
            If defined, synthesis stderr will be written to this file instead
            of being printed.
    working_dir: str
            The path to run synthesis from. If using genus, this will effect
            where the genus run files are stored. Directory will be created
            if it does not exist.
    fast_parsing: bool
            If True, will use fast verilog parsing (which requires
            specifically formatted netlists, see the documentation for
            `verilog_to_circuit`).
    pre_syn_file: file or str or None
            If specified, the circuit verilog will be written to this file
            before synthesis. If None, a temporary file will be used.
    post_syn_file: file or str or None
            If specified, the synthesis output verilog will be written to this
            file. If None, a temporary file will be used.
    verilog_exists: bool
            If True, does not write `c` to a file, instead uses the verilog
            already present in `pre_syn_file`.
    effort: str
            The effort to use for synthesis. Either 'high', 'medium', or 'low'

    Returns
    -------
    Circuit
            Synthesized circuit.
    """

    working_dir = Path(working_dir)
    working_dir.mkdir(exist_ok=True)
    working_dir = str(working_dir)

    # Make paths absolute in case synthesis is run from different working dir
    if pre_syn_file:
        pre_syn_file = Path(pre_syn_file).absolute()
    if post_syn_file:
        post_syn_file = Path(post_syn_file).absolute()

    if verilog_exists and not pre_syn_file:
        raise ValueError("Must specify pre_syn_file if using verilog_exists")

    with open(pre_syn_file, "r") if verilog_exists else open(
        pre_syn_file, "w"
    ) if pre_syn_file else NamedTemporaryFile(
        prefix="circuitgraph_synthesis_input", suffix=".v", mode="w"
    ) as tmp_in:
        if not verilog_exists:
            verilog = circuit_to_verilog(c)
            tmp_in.write(verilog)
            tmp_in.flush()
        with open(post_syn_file, "w+") if post_syn_file else NamedTemporaryFile(
            prefix="circuitgraph_synthesis_output", suffix=".v", mode="r"
        ) as tmp_out:
            if engine == "genus":
                try:
                    lib_path = os.environ["CIRCUITGRAPH_GENUS_LIBRARY_PATH"]
                except KeyError:
                    raise ValueError(
                        "In order to run synthesis with Genus, "
                        "please set the "
                        "CIRCUITGRAPH_GENUS_LIBRARY_PATH "
                        "variable in your os environment to the "
                        "path to the tech library to use"
                    )
                cmd = [
                    "genus",
                    "-no_gui",
                    "-execute",
                    "set_db / .library "
                    f"{lib_path};\n"
                    f"read_hdl -sv {tmp_in.name};\n"
                    "elaborate;\n"
                    f"set_db syn_generic_effort {effort};\n"
                    "syn_generic;\n"
                    "syn_map;\n"
                    "syn_opt;\n"
                    f'redirect {tmp_out.name} "write_hdl -generic";\n'
                    "exit;",
                ]
            elif engine == "dc":
                try:
                    lib_path = os.environ["CIRCUITGRAPH_DC_LIBRARY_PATH"]
                except KeyError:
                    raise ValueError(
                        "In order to run synthesis with DC, "
                        "please set the "
                        "CIRCUITGRAPH_DC_LIBRARY_PATH "
                        "variable in your os environment to the "
                        "path to the GTECH library"
                    )

                execute = (
                    f"set_app_var target_library {lib_path};\n"
                    f"set_app_var link_library {lib_path};\n"
                )
                unusable_cells = [
                    "GTECH_ADD*",
                    "GTECH_AO*",
                    "GTECH_AND_NOT",
                    "GTECH_FD1S",
                    "GTECH_FD2S",
                    "GTECH_FD3S",
                    "GTECH_FD4",
                    "GTECH_FD4S",
                    "GTECH_FD14",
                    "GTECH_FD18",
                    "GTECH_FD24",
                    "GTECH_FD28",
                    "GTECH_FD34",
                    "GTECH_FD38",
                    "GTECH_FD44",
                    "GTECH_FD48",
                    "GTECH_FJK1",
                    "GTECH_FJK1S",
                    "GTECH_FJK2",
                    "GTECH_FJK2S",
                    "GTECH_FJK3",
                    "GTECH_FJK3S",
                    "GTECH_INBUF",
                    "GTECH_INOUTBUF",
                    "GTECH_ISO0_EN0",
                    "GTECH_ISO0_EN1",
                    "GTECH_ISO1_EN0",
                    "GTECH_ISO1_EN1",
                    "GTECH_ISOLATCH_EN0",
                    "GTECH_ISOLATCH_EN1",
                    "GTECH_LD2",
                    "GTECH_LD2_1",
                    "GTECH_LD3",
                    "GTECH_LD4",
                    "GTECH_LD4_1",
                    "GTECH_LSR0",
                    "GTECH_MAJ23",
                    "GTECH_MUX*",
                    "GTECH_OA*",
                    "GTECH_OR_NOT",
                    "GTECH_OUTBUF",
                    "GTECH_TBUF",
                ]
                for cell in unusable_cells:
                    execute += f"set_dont_use gtech/{cell};\n"
                execute += (
                    f"read_file {tmp_in.name}\n"
                    "link;\n"
                    "uniquify;\n"
                    "check_design;\n"
                    "simplify_constants;\n"
                    f"compile -map_effort {effort};\n"
                    f"write -format verilog -output {tmp_out.name};\n"
                    "exit;"
                )
                cmd = ["dc_shell-t", "-no_gui", "-x", execute]
            elif engine == "yosys":
                cmd = [
                    "yosys",
                    "-p",
                    f"read_verilog {tmp_in.name}; "
                    "synth; "
                    f"write_verilog -noattr {tmp_out.name}",
                ]
            else:
                raise ValueError("synthesis engine must be yosys, dc, or genus")

            if suppress_output and not stdout_file:
                stdout = subprocess.DEVNULL
            elif stdout_file:
                stdout = open(stdout_file, "w")
            else:
                stdout = None
            if stderr_file:
                stderr = open(stderr_file, "w")
            else:
                stderr = None
            subprocess.run(cmd, stdout=stdout, stderr=stderr, cwd=working_dir)
            if stdout_file:
                stdout.close()
            if stderr_file:
                stderr.close()

            output_netlist = tmp_out.read()

    return verilog_to_circuit(output_netlist, c.name, fast=fast_parsing)


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


def sequential_unroll(c, n, reg_d_port, reg_q_port, remove_unused_ports=True):
    """
    Unroll a sequential circuit. Provides a higher level API than `unroll`
    by accepting a circuit with sequential elements kept as blackboxes.
    Assumes that all blackboxes in the circuit are sequential elements.

    Parameters
    ----------
    c: Circuit
            Circuit to unroll.
    n: int
            The number of times to unroll.
    reg_d_port: str
            The name of the D port in the blackboxes in `c`.
    reg_q_port: str
            The name of the Q port in the blackboxes in `cc`.
    remove_unused_ports: bool
            If True, any inputs to the combinational circuit without drivers will
            be removed before returning. This can be used to remove drivers for
            the register ports besides `reg_d_port` and `reg_q_port`, e.g. a clk 
            or rst.

    Returns
    -------
    Circuit
            The unrolled circuit.
    """
    cs = strip_blackboxes(c)
    blackbox = c.blackboxes[set(c.blackboxes.keys()).pop()]

    if reg_d_port not in blackbox.inputs():
        raise ValueError(f"Provided d port {reg_d_port} not in bb inputs")
    cs.remove(
        f"{bb}_{p}" for p in blackbox.inputs() - {reg_d_port} for bb in c.blackboxes
    )

    if reg_q_port not in blackbox.outputs():
        raise ValueError(f"Provided q port {reg_q_port} not in bb outputs")
    cs.remove(
        f"{bb}_{p}" for p in blackbox.outputs() - {reg_q_port} for bb in c.blackboxes
    )

    cs.remove(i for i in cs.inputs() if not cs.fanout(i))

    state_io = {f"{bb}_{reg_d_port}": f"{bb}_{reg_q_port}" for bb in c.blackboxes}
    uc = unroll(cs, n, state_io)
    return uc


def unroll(c, n, state_io):
    """
    Unrolls a circuit.

    Parameters
    ----------
    c: Circuit
            Circuit to unroll.
    n: int
            The number of times to unroll.
    state_io: dict of str:str
            For each `(k, v)` pair in the dict, `k` of circuit iteration `n - 1` will be
            tied to `v` of circuit iteration `n`.

    Returns
    -------
    Circuit
            Unrolled circuit.
    """
    # check for blackboxes
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")

    if n < 1:
        raise ValueError(f"n must be >= 1 ({n})")

    uc = Circuit()
    for itr in range(n + 1):
        for i in c.io():
            if f"{i}_{itr}" in c:
                raise ValueError(f"Naming clash: {i}_{itr} already in circuit")

            if i in state_io or i in state_io.values():
                t = "buf"
            elif i in c.inputs():
                t = "input"
            elif i in c.outputs():
                t = "output"

            uc.add(f"{i}_{itr}", t)

        uc.add_subcircuit(c, f"unrolled_{itr}", {i: f"{i}_{itr}" for i in c.io()})

        if itr == 0:
            for i in state_io.values():
                uc.set_type(f"{i}_{itr}", "input")
        else:
            for k, v in state_io.items():
                uc.connect(f"{k}_{itr-1}", f"{v}_{itr}")

        if itr == n:
            for i in state_io:
                uc.set_type(f"{i}_{itr}", "output")

    return uc


def influence_transform(c, n, s):
    """
    Creates a circuit to compute influence.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to compute influence for.
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
            Sequential circuit to ccompute sensitivity for.
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


def limit_fanin(c, k):
    """
    Reduces the maximum fanin of circuit gates to k

    Parameters
    ----------
    c : Circuit
            Input circuit.
    k : str
            Maximum fanin. (k>1)

    Returns
    -------
    Circuit
            Output circuit.

    """
    if k < 2:
        raise ValueError(f"maximum fanin, k, must be > 2")

    ck = copy(c)
    for n in ck.nodes():
        i = 0
        while len(ck.fanin(n)) > k:
            fi = ck.fanin(n)
            f0 = fi.pop()
            f1 = fi.pop()
            ck.disconnect([f0, f1], n)
            if ck.type(n) in ["and", "nand"]:
                ck.add(f"{n}_new_{i}", "and", fanin=[f0, f1], fanout=n)
            elif ck.type(n) in ["or", "nor"]:
                ck.add(f"{n}_new_{i}", "or", fanin=[f0, f1], fanout=n)
            elif ck.type(n) in ["xor"]:
                ck.add(f"{n}_new_{i}", "xor", fanin=[f0, f1], fanout=n)
            elif ck.type(n) in ["xnor"]:
                ck.add(f"{n}_new_{i}", "xnor", fanin=[f0, f1], fanout=n)
            else:
                raise ValueError(f"Unknown gate type: {ck.type(n)}")
            i += 1

    return ck
