"""
Functions for transforming circuits.

Examples
--------
Synthesize a circuit using yosys

>>> import circuitgraph as cg
>>> c = cg.from_lib("c1908")
>>> c = cg.tx.syn(c, suppress_output=True)

"""
import os
import re
import shutil
import subprocess
from collections import defaultdict
from functools import reduce
from pathlib import Path
from queue import Queue
from tempfile import NamedTemporaryFile

import networkx as nx

import circuitgraph as cg


def strip_io(c):
    """
    Remove a circuit's outputs and convert inputs to buffers.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io.

    """
    g = c.graph.copy()
    for i in c.inputs():
        g.nodes[i]["type"] = "buf"
    for o in c.outputs():
        g.nodes[o]["output"] = False

    return cg.Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_outputs(c):
    """
    Remove a circuit's outputs for easy instantiation.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io.

    """
    g = c.graph.copy()
    for o in c.outputs():
        g.nodes[o]["output"] = False

    return cg.Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_inputs(c):
    """
    Convert inputs to buffers for easy instantiation.

    Parameters
    ----------
    c : Circuit
            Input circuit.

    Returns
    -------
    Circuit
            Circuit with removed io.

    """
    g = c.graph.copy()
    for i in c.inputs():
        g.nodes[i]["type"] = "buf"

    return cg.Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def strip_blackboxes(c, ignore_pins=None):
    """
    Convert blackboxes to io.

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
            g.nodes[n]["type"] = "buf"
            g.nodes[n]["output"] = True
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

    return cg.Circuit(graph=g, name=c.name)


def relabel(c, mapping):
    """
    Build copy of circuit with relabeled nodes.

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
    return cg.Circuit(graph=g, name=c.name, blackboxes=c.blackboxes.copy())


def subcircuit(c, nodes, modify_io=False):
    """
    Create a subcircuit from a set of nodes of a given circuit.

    Parameters
    ----------
    c: Circuit
            The circuit to create a subcircuit from.
    nodes: list of str
            The nodes to include in the subcircuit.
    modify_io: bool
            If True, gates without drivers will be turned into inputs and gates without
            fanout will be marked as outputs.

    Returns
    -------
    Circuit
            The subcircuit.

    """
    sc = cg.Circuit()
    for node in nodes:
        if c.type(node) in ["bb_output", "bb_input"]:
            raise NotImplementedError("Cannot create a subcircuit with blackboxes")
        sc.add(node, c.type(node), output=c.is_output(node))
    for edge in c.edges():
        if edge[0] in nodes and edge[1] in nodes:
            sc.connect(edge[0], edge[1])
    if modify_io:
        for node in sc:
            if sc.type(node) not in ["0", "1", "x"] and not sc.fanin(node):
                sc.set_type(node, "input")
            if not sc.fanout(node):
                sc.set_output(node)
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
    Synthesize the circuit using a third-party synthesis tool.

    Parameters
    ----------
    c : Circuit
            Circuit to synthesize.
    engine : str
            Synthesis tool to use ('genus', 'dc', or 'yosys').
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
            The effort to use for synthesis. Either 'high', 'medium', or 'low'.

    Returns
    -------
    Circuit
            Synthesized circuit.

    """
    if engine == "yosys" and shutil.which("yosys") is None:
        raise OSError("'yosys' installation not found")

    if engine == "genus" and shutil.which("genus") is None:
        raise OSError("'genus' installation not found")

    if engine == "dc":
        dc_engine = "dc_shell-t"
        if shutil.which("dc_shell-t") is None:
            dc_engine = "dc_shell"
            if shutil.which("dc_shell") is None:
                raise OSError("'dc_shell-t' or 'dc_shell' installation not found")

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

    with open(pre_syn_file) if verilog_exists else open(
        pre_syn_file, "w"
    ) if pre_syn_file else NamedTemporaryFile(
        prefix="circuitgraph_synthesis_input", suffix=".v", mode="w"
    ) as tmp_in:
        if not verilog_exists:
            verilog = cg.io.circuit_to_verilog(c)
            tmp_in.write(verilog)
            tmp_in.flush()
        with open(post_syn_file, "w+") if post_syn_file else NamedTemporaryFile(
            prefix="circuitgraph_synthesis_output", suffix=".v", mode="r"
        ) as tmp_out:
            if engine == "genus":
                try:
                    lib_path = os.environ["CIRCUITGRAPH_GENUS_LIBRARY_PATH"]
                except KeyError as e:
                    raise ValueError(
                        "In order to run synthesis with Genus, please set the "
                        "CIRCUITGRAPH_GENUS_LIBRARY_PATH variable in your os "
                        "environment to the path to the tech library to use"
                    ) from e
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
                except KeyError as e:
                    raise ValueError(
                        "In order to run synthesis with DC, please set the "
                        "CIRCUITGRAPH_DC_LIBRARY_PATH variable in your os environment "
                        "to the path to the GTECH library"
                    ) from e
                libname = "GTECH"
                usable_cells = [f"{libname.lower()}/{libname}_NOT"]
                for gate in ["OR", "NOR", "AND", "NAND", "XOR", "XNOR"]:
                    usable_cells += [
                        f"{libname.lower()}/{libname}_{gate}{i}" for i in range(2, 5)
                    ]
                usable_cells += [
                    f"{libname.lower()}/{libname}_FD{i}" for i in range(1, 4)
                ]
                execute = (
                    f"set_app_var target_library {lib_path};\n"
                    f"set_app_var link_library {lib_path};\n"
                    "set_dont_use [remove_from_collection "
                    f"[get_lib_cells {libname.lower()}/*] "
                    f"\"{' '.join(usable_cells)}\"];\n"
                    f"read_file {tmp_in.name}\n"
                    "link;\n"
                    "uniquify;\n"
                    "check_design;\n"
                    "simplify_constants;\n"
                    f"compile;\n"
                    f"write -format verilog -output {tmp_out.name};\n"
                    "exit;"
                )
                cmd = [dc_engine, "-no_gui", "-x", execute]
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
            subprocess.run(
                cmd, stdout=stdout, stderr=stderr, cwd=working_dir, check=True
            )
            if stdout_file:
                stdout.close()
            if stderr_file:
                stderr.close()

            output_netlist = tmp_out.read()

            # Rename dc library gates
            if engine == "dc":

                def replace_gate(match):
                    # Keep flops as they are
                    if match.group(1).startswith(f"{libname}_FD"):
                        return match
                    ports = [
                        i.strip().split("(")[-1].strip(")")
                        for i in match.group(3).split(",")
                    ]
                    portlist = ", ".join(reversed(ports))
                    return f"{match.group(1).lower()} {match.group(2)}({portlist});"

                output_netlist = re.sub(
                    rf"{libname}_([A-Z]+)[1-4]?\s+"
                    r"([a-zA-Z][a-zA-Z\d_]*)\s*\(([^;]+)\);",
                    replace_gate,
                    output_netlist,
                )

    return cg.io.verilog_to_circuit(output_netlist, c.name, fast=fast_parsing)


def aig(c):
    """
    Transform a circuit into and and-inverter graph.

    Parameters
    ----------
    c: Circuit
            The circuit to transform to an AIG.

    Returns
    -------
    Circuit
            The AIG circuit.

    """
    with NamedTemporaryFile(
        prefix="circuitgraph_aig_input", suffix=".v", mode="w"
    ) as tmp_in:
        cg.to_file(c, tmp_in.name)
        with NamedTemporaryFile(
            prefix="circuitgraph_aig_output", suffix=".v", mode="r"
        ) as tmp_out:
            execute = (
                f"read_verilog {tmp_in.name}; aigmap; "
                "opt; "
                f"write_verilog -noattr {tmp_out.name}"
            )
            subprocess.run(
                ["yosys", "-p", execute], stdout=subprocess.DEVNULL, check=True
            )
            c = cg.from_file(tmp_out.name)
    # c = remove_bufs(c)
    return c


def ternary(c):
    """
    Encode the circuit with ternary values.

    The ternary circuit adds a second net for each net in the original circuit.
    The second net encodes a don't care, or X, value. That net being high
    corresponds to a don't care value on original net. If the second net is
    low, the logical value on the original net is valid.

    Parameters
    ----------
    c : Circuit
            Circuit to encode.
    suffix: str
            The suffix to give the added nets. Note that it is safest to use
            the returned dictionary to refer to the added nets because they
            are uniquified when they are added to the circuit.

    Returns
    -------
    Circuit, dict of str:str
            Encoded circuit and dictionary mapping original net names to added ternary
            net names.

    """
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")
    t = c.copy()

    # add dual nodes
    mapping = {n: c.uid(f"{n}_X") for n in c}
    for n in c:
        if c.type(n) in ["and", "nand"]:
            t.add(mapping[n], "and", output=c.is_output(n), allow_redefinition=True)
            t.add(
                f"{n}_x_in_fi",
                "or",
                fanout=mapping[n],
                fanin=[mapping[p] for p in c.fanin(n)],
                uid=True,
                add_connected_nodes=True,
            )
            zero_not_in_fi = t.add(
                f"{n}_0_not_in_fi", "nor", fanout=mapping[n], uid=True
            )
            for p in c.fanin(n):
                t.add(
                    f"{p}_is_0",
                    "nor",
                    fanout=zero_not_in_fi,
                    fanin=[p, mapping[p]],
                    uid=True,
                )
        elif c.type(n) in ["or", "nor"]:
            t.add(mapping[n], "and", output=c.is_output(n), allow_redefinition=True)
            t.add(
                f"{n}_x_in_fi",
                "or",
                fanout=mapping[n],
                fanin=[mapping[p] for p in c.fanin(n)],
                uid=True,
                add_connected_nodes=True,
            )
            one_not_in_fi = t.add(
                f"{n}_1_not_in_fi", "nor", fanout=mapping[n], uid=True
            )
            for p in c.fanin(n):
                is_one = t.add(
                    f"{p}_is_1", "and", fanout=one_not_in_fi, fanin=p, uid=True
                )
                t.add(f"{p}_not_x", "not", fanout=is_one, fanin=mapping[p], uid=True)
        elif c.type(n) in ["buf", "not"]:
            p = c.fanin(n).pop()
            t.add(
                mapping[n],
                "buf",
                fanin=mapping[p],
                output=c.is_output(n),
                add_connected_nodes=True,
                allow_redefinition=True,
            )
        elif c.type(n) in ["xor", "xnor"]:
            t.add(
                mapping[n],
                "or",
                fanin=[mapping[p] for p in c.fanin(n)],
                output=c.is_output(n),
                add_connected_nodes=True,
                allow_redefinition=True,
            )
        elif c.type(n) in ["0", "1"]:
            t.add(mapping[n], "0", output=c.is_output(n), allow_redefinition=True)
        elif c.type(n) in ["input"]:
            t.add(mapping[n], "input", allow_redefinition=True)
        else:
            raise ValueError(f"Node '{n}' has invalid type: '{c.type(n)}'")

    return t, mapping


def miter(c0, c1=None, startpoints=None, endpoints=None):
    """
    Create a miter circuit.

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
    m = cg.Circuit(name=f"miter_{c0.name}_{c1.name}")
    m.add_subcircuit(c0, "c0")
    m.add_subcircuit(c1, "c1")

    # tie inputs
    for n in startpoints:
        m.add(n, "input", fanout=[f"c0_{n}", f"c1_{n}"])

    # compare outputs
    m.add("sat", "or" if len(endpoints) > 1 else "buf", output=True)
    for n in endpoints:
        m.add(f"dif_{n}", "xor", fanin=[f"c0_{n}", f"c1_{n}"], fanout="sat")

    return m


def sequential_unroll(
    c,
    n,
    reg_d_port,
    reg_q_port,
    ignore_pins=None,
    add_flop_outputs=False,
    initial_values=None,
    remove_unloaded=True,
    prefix="cg_unroll",
):
    """
    Unroll a sequential circuit.

    Provides a higher level API than `unroll` by accepting a circuit with
    sequential elements kept as blackboxes. Assumes that all blackboxes in
    the circuit are sequential elements.

    Parameters
    ----------
    c: Circuit
            Circuit to unroll.
    n: int
            The number of unrolled copies of the circuit to create.
    reg_d_port: str
            The name of the D port in the blackboxes in `c`.
    reg_q_port: str
            The name of the Q port in the blackboxes in `c`.
    ignore_pins: str or list of str
            The names of pins in the blackboxes to ignore.
    add_flop_outputs: bool
            If True, the Q port of the flops will be added as primary outputs.
    initial_values: str or dict of str:str
            The initial values of the data ports for the first timestep.
            If None, the ports will be added as primary inputs.
            If a single value ('0', '1', or 'x'), every flop will get that value.
            Can also pass in dict mapping flop names to values.
    remove_unloaded: bool
            If True, unloaded inputs will be removed after unrolling. This can remove
            unused sequential signals such as the clock and reset.
    prefix: str
            The prefix to use for naming unrolled nodes.

    Returns
    -------
    Circuit, dict of str:list of str
            Unrolled circuit and mapping of original circuit io to list of unrolled
            circuit io. The lists are in order of the unroll iterations.

    """
    cs = strip_blackboxes(c, ignore_pins=ignore_pins)
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

    if remove_unloaded:
        for i in cs.inputs():
            if not cs.fanout(i):
                cs.remove(i)

    state_io = {f"{bb}_{reg_d_port}": f"{bb}_{reg_q_port}" for bb in c.blackboxes}
    uc, io_map = unroll(cs, n, state_io, prefix=prefix)

    for state_output in (f"{bb}_{reg_d_port}" for bb in c.blackboxes):
        uc.set_output(io_map[state_output], add_flop_outputs)

    if initial_values:
        if isinstance(initial_values, str):
            for fi in [io_map[f"{bb}_{reg_q_port}"][0] for bb in c.blackboxes]:
                uc.set_type(fi, initial_values)
        else:
            for k, v in initial_values.items():
                uc.set_type(io_map[f"{k}_{reg_q_port}"][0], v)

    return uc, io_map


def unroll(c, n, state_io, prefix="cg_unroll"):
    """
    Unroll a circuit.

    Create multiple copies of the circuit and connect together state io.

    Parameters
    ----------
    c: Circuit
            Circuit to unroll.
    n: int
            The number of unrolled copies of the circuit to create.
    state_io: dict of str:str
            For each `(k, v)` pair in the dict, `k` of circuit iteration `n - 1` will be
            tied to `v` of circuit iteration `n`.
    prefix: str
            The prefix to use for naming new io for each iteration.

    Returns
    -------
    Circuit, dict of str:list of str
            Unrolled circuit and mapping of original circuit io to list of unrolled
            circuit io. The lists are in order of the unroll iterations.

    """
    # check for blackboxes
    if c.blackboxes:
        raise ValueError(f"{c.name} contains a blackbox")

    if n < 1:
        raise ValueError(f"n must be >= 1 ({n})")

    for k, v in state_io.items():
        if k not in c.io():
            raise ValueError(f"Node '{k}' in state_io dict but not in io of circuit")
        if v not in c.io():
            raise ValueError(f"Node '{v}' in state_io dict but not in io of circuit")

    uc = cg.Circuit()

    io_map = {io: [] for io in c.io()}
    for itr in range(n):
        for io in c.io():
            new_io = c.uid(f"{io}_{prefix}_{itr}")
            if io in state_io or io in state_io.values():
                t = "buf"
            elif io in c.inputs():
                t = "input"
            else:
                t = "buf"

            uc.add(new_io, t, output=c.is_output(io))
            io_map[io].append(new_io)

        uc.add_subcircuit(
            c, f"unrolled_{itr}", {i: f"{i}_{prefix}_{itr}" for i in c.io()}
        )

        if itr == 0:
            for i in state_io.values():
                uc.set_type(f"{i}_{prefix}_{itr}", "input")
        else:
            for k, v in state_io.items():
                uc.connect(f"{k}_{prefix}_{itr-1}", f"{v}_{prefix}_{itr}")

    return uc, io_map


def sensitization_transform(c, n, endpoints=None):
    """
    Create a circuit to sensitize a node to an endpoint.

    Create a miter circuit with that node inverted in one circuit copy.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    n : str
            Node to sensitize.
    endpoints: str or list of str
            Endpoints to sensitize to. If None, any output
            can be used for sensitization.

    Returns
    -------
    Circuit
            Output circuit.

    """
    # check for blackboxes
    if c.blackboxes:
        raise ValueError("Circuit contains a blackbox")

    if endpoints:
        if isinstance(endpoints, str):
            endpoints = {endpoints}
        else:
            endpoints = set(endpoints)
        fi = c.transitive_fanin(endpoints)
        if n not in fi:
            raise ValueError(f"'{n}' is not in fanin of given endpoints")
        subc = subcircuit(c, endpoints | fi)
        for node in subc:
            subc.set_output(node, node in endpoints)
        miter_name = f"{c.name}_sensitize_{n}_to_{'_'.join(endpoints)}"
    else:
        subc = c
        miter_name = f"{c.name}_sensitize_{n}"

    # create miter
    m = miter(subc)
    m.name = miter_name

    # flip node in c1
    m.disconnect(m.fanin(f"c1_{n}"), f"c1_{n}")
    m.set_type(f"c1_{n}", "not")
    m.connect(f"c0_{n}", f"c1_{n}")

    return m


def sensitivity_transform(c, n):
    """
    Create a circuit to compute sensitivity.

    Creatie a miter circuit for each input 'i' with the fanin cone of `n`
    where the second circuit has 'i' inverted, so that the miter output is
    high when `n` is sensitive to 'i'. The uninverted circuit is shared
    across all miters and the outputs of the miters are fed into a
    population count circuit so that the output of the population count
    circuit gives the sensitivity of `n` for a given input pattern.

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
    fi_nodes = c.transitive_fanin(n) | {n}
    sub_c = cg.Circuit(graph=c.graph.subgraph(fi_nodes).copy())

    # create sensitivity circuit
    sen = cg.Circuit()
    sen.add_subcircuit(sub_c, "orig")
    for s in startpoints:
        sen.add(s, "input", fanout=f"orig_{s}")

    # add popcount
    sen.add_subcircuit(cg.logic.popcount(len(startpoints)), "pc")

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
            f"dif_out_{s0}",
            "xor",
            fanin=[f"orig_{n}", f"inv_{s0}_{n}"],
            fanout=f"pc_in_{i}",
            output=True,
        )

    # instantiate population count
    for o in range(cg.utils.clog2(len(startpoints) + 1)):
        sen.add(f"sen_out_{o}", "buf", fanin=f"pc_out_{o}", output=True)

    return sen


def limit_fanin(c, k):
    """
    Reduce the maximum fanin of circuit gates to k.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    k : str
            Maximum fanin. (k >= 2)

    Returns
    -------
    Circuit
            Output circuit.

    """
    if k < 2:
        raise ValueError(f"'k' must be >= 2, not '{k}'")

    gatemap = {
        "and": "and",
        "nand": "and",
        "or": "or",
        "nor": "or",
        "xor": "xor",
        "xnor": "xnor",
    }

    ck = c.copy()
    for n in ck.nodes():
        i = 0
        while len(ck.fanin(n)) > k:
            fi = ck.fanin(n)
            f0 = fi.pop()
            f1 = fi.pop()
            ck.disconnect([f0, f1], n)
            ck.add(
                f"{n}_limit_fanin_{i}",
                gatemap[ck.type(n)],
                fanin=[f0, f1],
                fanout=n,
                uid=True,
            )
            i += 1

    return ck


def limit_fanout(c, k):
    """
    Reduce the maximum fanout of circuit gates to k.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    k : str
            Maximum fanout. (k >= 2)

    Returns
    -------
    Circuit
            Output circuit.

    """
    if k < 2:
        raise ValueError(f"'k' must be >= 2, not '{k}'")

    ck = c.copy()
    for n in ck.nodes():
        i = 0
        while len(ck.fanout(n)) > k:
            fo = ck.fanout(n)
            f0 = fo.pop()
            f1 = fo.pop()
            ck.disconnect(n, [f0, f1])
            ck.add(
                f"{n}_limit_fanout_{i}",
                "buf",
                fanin=n,
                fanout=[f0, f1],
                uid=True,
            )
            i += 1

    return ck


def acyclic_unroll(c):
    """
    Unroll a cyclic circuit to remove cycles.

    Parameters
    ----------
    c: Circuit
            Circuit to unroll.

    Returns
    -------
    Circuit
            The unrolled circuit.

    """
    if c.blackboxes:
        raise ValueError("Cannot perform acyclic unroll with blackboxes")

    def approx_min_fas(g):
        g_copy = g.copy()
        s1, s2 = [], []
        while g_copy.nodes:
            # find sinks
            sinks = [n for n in g_copy.nodes if g_copy.out_degree(n) == 0]
            while sinks:
                s2 += sinks
                g_copy.remove_nodes_from(sinks)
                sinks = [n for n in g_copy.nodes if g_copy.out_degree(n) == 0]

            # find sources
            sources = [n for n in g_copy.nodes if g_copy.in_degree(n) == 0]
            while sources:
                s1 += sources
                g_copy.remove_nodes_from(sources)
                sources = [n for n in g_copy.nodes if g_copy.in_degree(n) == 0]

            # choose max in/out degree difference
            if g_copy.nodes:
                n = max(
                    g_copy.nodes,
                    key=lambda x: g_copy.out_degree(x) - g_copy.in_degree(x),
                )
                s1.append(n)
                g_copy.remove_node(n)

        ordering = s1 + list(reversed(s2))
        feedback_edges = [
            e for e in g.edges if ordering.index(e[0]) > ordering.index(e[1])
        ]
        feedback_edges = [
            (u, v) for u, v in feedback_edges if u in nx.descendants(g, v)
        ]

        g_copy = g.copy()
        g_copy.remove_edges_from(feedback_edges)
        try:
            if nx.find_cycle(g_copy):
                raise ValueError("approx_min_fas has failed")
        except nx.NetworkXNoCycle:
            pass

        return feedback_edges

    # find feedback nodes
    feedback = {e[0] for e in approx_min_fas(c.graph)}

    # get startpoints
    sp = c.startpoints()

    # create acyclic circuit
    acyc = cg.Circuit(name=f"acyc_{c.name}")
    for n in sp:
        acyc.add(n, "input")

    # create copy with broken feedback
    c_cut = c.copy()
    for f in feedback:
        fanout = c.fanout(f)
        c_cut.disconnect(f, fanout)
        c_cut.add(f"aux_in_{f}", "buf", fanout=fanout)
    c_cut.set_output(c.outputs(), False)

    # cut feedback
    for i in range(len(feedback) + 1):
        # instantiate copy
        acyc.add_subcircuit(c_cut, f"c{i}", {n: n for n in sp})

        if i > 0:
            # connect to last
            for f in feedback:
                acyc.connect(f"c{i-1}_{f}", f"c{i}_aux_in_{f}")
        else:
            # make feedback inputs
            for f in feedback:
                acyc.set_type(f"c{i}_aux_in_{f}", "input")

    # connect outputs
    for o in c.outputs():
        acyc.add(o, "buf", fanin=f"c{i}_{o}", output=True)

    cg.lint(acyc)
    if acyc.is_cyclic():
        raise ValueError("Circuit still cyclic")
    return acyc


def supergates(c, construct_supercircuit=False):
    """
    Break the circuit up into supergates.

    Calculate the minimal covering of all circuit nodes with maximal supergates
    of a circuit. For more information, see
    Sharad C. Seth and Vishwani D. Agrawal. "A new model for computation of
    probabilistic testability in combinational circuits." Integration 7.1
    (1989): 49-75.

    Parameters
    ----------
    c: Circuit
            The circuit to compute supergates for
    construct_supercircuit: bool
            If True, a circuit connecting together the supergates as black boxes
            will be formed. Currently this only works if `c` has only one output.

    Returns
    -------
    list of Circuit or (Circuit, dict of str:Circuit)
            If `construct_supercircuit` is `False`, the supergate circuits,
            topologically sorted. Otherwise, the supercircuit and a dict
            mapping blackbox names to corresponding supergates.

    """
    if construct_supercircuit and len(c.outputs()) > 1:
        raise ValueError(
            "Can only use `construct_supercircuit` one a single-output circuit"
        )
    # The current algorithm seems to fail for some circuits (like c880) with gates with
    # fanin greater than 2. At the moment not sure if this is a bug in the
    # implementation or expected behavior
    c = limit_fanin(c, 2)
    supergate_circuits = set()
    for output in c.outputs():
        c_output = subcircuit(c, c.transitive_fanin(output) | {output})
        c_output.set_output(c_output.outputs(), False)
        c_output.set_output(output, True)

        g = c_output.graph.copy()

        # Add backwards edge for every forward edge not connected to an output
        rm_edges = []
        for u, v in g.edges:
            g.add_edge(v, u)
            if v == output:
                rm_edges.append((u, v))
        for u, v in rm_edges:
            g.remove_edge(u, v)

        # Get dominator tree
        doms = nx.immediate_dominators(g, output)
        dom_tree = defaultdict(set)
        for k, v in doms.items():
            dom_tree[v].add(k)

        # Build supergates starting at the output
        dom_tree[output].remove(output)
        frontier = Queue()
        frontier.put(output)
        while not frontier.empty():
            # Build the supergate for this node
            node = frontier.get()
            supergate = {node}
            # Include children and single successors
            fanins = Queue()
            for fi in dom_tree[node]:
                fanins.put(fi)
            while not fanins.empty():
                fi = fanins.get()
                supergate.add(fi)
                if len(dom_tree[fi]) > 1:
                    frontier.put(fi)
                elif len(dom_tree[fi]) == 1:
                    fanins.put(dom_tree[fi].pop())
            supergate_circuit = subcircuit(c_output, supergate, modify_io=True)
            supergate_circuit.set_output(node, True)
            supergate_circuits.add(supergate_circuit)

    # Find minimal covering of supergates indexed by the output
    minimal_supergate_circuits = {}
    for supergate in supergate_circuits:
        remaining_cover = reduce(
            lambda a, b: a | b,
            (s.nodes() - s.inputs() for s in supergate_circuits - {supergate}),
            set(),
        )
        if supergate.nodes() - remaining_cover:
            minimal_supergate_circuits[supergate.outputs().pop()] = supergate

    if construct_supercircuit:
        superc = cg.Circuit(f"{c.name}_supergates")
        for i in c.inputs():
            superc.add(i, "input")
        for o in c.outputs():
            superc.add(o, "buf", output=True)

        supergate_map = {}
        for output, supergate in minimal_supergate_circuits.items():
            sg_name = f"sg_{output}"
            supergate_map[sg_name] = supergate
            bb = cg.BlackBox(name=sg_name, inputs=supergate.inputs(), outputs={output})
            for n in supergate.io():
                if n not in superc:
                    superc.add(n, "buf")
            superc.add_blackbox(bb, sg_name, {i: i for i in supergate.io()})

        return superc, supergate_map

    # Find topological ordering of supergates
    g = nx.DiGraph()
    for output, supergate in minimal_supergate_circuits.items():
        g.add_node(output)
        for i in supergate.inputs() - c.inputs():
            for other_output in set(minimal_supergate_circuits) - {output}:
                other_supergate = minimal_supergate_circuits[other_output]
                if i in other_supergate.nodes() - other_supergate.inputs():
                    g.add_edge(other_output, output)

    sorted_supergate_circuits = []
    for node in nx.topological_sort(g):
        sorted_supergate_circuits.append(minimal_supergate_circuits[node])
    return sorted_supergate_circuits


def insert_registers(
    c,
    num_stages,
    ff=cg.generic_flop,
    d_port="d",
    q_port="q",
    other_flop_io={"clk": "clk"},
    q_suffix="_cg_insert_reg_q_",
):
    """
    Insert pipeline registers into a combinational design.

    Parameters
    ----------
    c: circuitgraph.Circuit
            The circuit to insert registers into.
    num_stages: int
            The number of stages to add.
    ff: circuitgraph.BlackBox
            The flip flop blackbox to use.
    d_port: str
            The d port on the flip flop blackbox.
    q_port: str
            The q port on the flip flop blackbox.
    other_flop_io: dict of str:str
            Other io to connect on the flop (e.g. clk, rst ports).
            Dict maps circuit nodes to flop ports. If a node is
            present in the dict but not in the circuit, it will be
            added as an input.
    q_suffix: str
            Inserted q nodes are named with the suffix `{q_suffix}{i}` where
            `i` is the level the flop is inserted at.

    Returns
    -------
    circuitgraph.Circuit
            The circuit with added registers.

    """
    c_reg = c.copy()
    nodes_at_depths = []
    max_depth = 0
    for n in c_reg:
        depth = c_reg.fanin_depth(n)
        while depth >= len(nodes_at_depths):
            nodes_at_depths.append([])
        nodes_at_depths[depth].append(n)
        if depth > max_depth:
            max_depth = depth

    depth_inc = round(max_depth / (num_stages + 1))
    for n in other_flop_io:
        if n not in c_reg:
            c_reg.add(n, "input")
    for i in range(depth_inc, max_depth, depth_inc):
        for n in nodes_at_depths[i]:
            fanout = c_reg.fanout(n)
            c_reg.disconnect(n, fanout)
            q = c_reg.add(f"{n}{q_suffix}{i}", "buf", uid=True, fanout=fanout)
            conns = {d_port: n, q_port: q}
            conns.update(other_flop_io)
            c_reg.add_blackbox(ff, f"ff_{n}", conns)
    return c_reg
