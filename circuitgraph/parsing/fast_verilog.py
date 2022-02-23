"""
Utils for parsing verilog with regex.

Faster than Lark parsing for large netlists, but less safe and more
restrictive.

"""
import re
from collections import defaultdict

import networkx as nx

from circuitgraph import Circuit, primitive_gates


def fast_parse_verilog_netlist(netlist, blackboxes):
    """
    Parse a verilog netlist quickly but with some restrictions.

    Can speed up parsing on very large netlists by making a handful of
    assumptions. It is much safer to use `parse_verilog_netlist`. This
    function should only be used if necessary.

    The input netlist must conform to the following rules:
        - Only one module definition is present
        - There are no comments
        - Assign statements must have a single net as the LHS, and the RHS
          must be a constant
        - The only constants that may be used are `1'b0` and `1'b1` (or h/d)
        - Primitive gates can only have one output
        - Instantiations must be named.
        - Only one instantation per line (e.g. `buf b1(a, b) b2(c, d);` is
          not allowed)
        - No expressions (e.g. `buf (a, b & c);` is not allowed)
        - No escaped identifiers

    The code does not overtly check that these rules are satisfied, and if
    they are not this function may still return a malformed Circuit object.
    It is up to the caller of the function to assure that these rules are
    followed.

    If an output is undriven, a driver for the output will still be added to
    the circuit, which is a discrepancy with `parse_verilog_netlist` (in which
    no output drive will be added).

    Note that thorough error checking that is done in `parse_verilog_netlist`
    is skipped in this function (e.g. checking if nets are declared as wires,
    checking if the portlist matches the input/output declarations, etc.).

    Note also that wires that are declared but not used will not be added to
    the circuit.

    Parameters
    ----------
    netlist: str
            Verilog code.
    blackboxes: seq of BlackBox
            Blackboxes in module.

    Returns
    -------
    Circuit
            Parsed circuit.

    """
    regex = r"module\s+(.+?)\s*\(.*?\);"
    m = re.search(regex, netlist, re.DOTALL)
    name = m.group(1)
    module = netlist[m.end() :]

    regex = "endmodule"
    m = re.search(regex, netlist, re.DOTALL)
    module = module[: m.start()]

    # create graph
    g = nx.DiGraph()

    # parse io
    regex = r"(input)\s(.+?);"
    inputs = set()
    for _, net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.split(",")
        for net in nets:
            inputs.add(net.strip())
    g.add_nodes_from(inputs, type="input")

    # create constants, (will be removed if unused)
    tie_0 = "tie0"
    while tie_0 in g:
        tie_0 = "tie0_{random.randint(1111, 9999)}"
    tie_1 = "tie1"
    while tie_1 in g:
        tie_1 = "tie1_{random.randint(1111, 9999)}"
    g.add_node(tie_0, type="0")
    g.add_node(tie_1, type="1")

    # parse insts
    regex = r"([a-zA-Z][a-zA-Z\d_]*)\s+([a-zA-Z][a-zA-Z\d_]*)\s*\(([^;]+)\);"

    all_nets = defaultdict(list)
    all_edges = []
    blackboxes_to_add = {}
    for gate, inst, net_str in re.findall(regex, module, re.DOTALL):

        # parse generics
        if gate in primitive_gates:
            # parse nets
            nets = [n.strip() for n in net_str.split(",")]

            # replace constants
            nets = [tie_0 if n == "1'b0" else tie_1 if n == "1'b1" else n for n in nets]

            all_nets[gate].append(nets[0])
            all_edges += [(i, nets[0]) for i in nets[1:]]
        # parse non-generics
        else:
            # get blackbox definition
            try:
                bb = next(bb for bb in blackboxes if bb.name == gate)
            except StopIteration as e:
                raise ValueError(f"blackbox {gate} not defined") from e

            # parse pins
            all_nets["bb_input"] += [f"{inst}.{n}" for n in bb.inputs()]
            all_nets["bb_output"] += [f"{inst}.{n}" for n in bb.outputs()]

            regex = r"\.\s*(\S+)\s*\(\s*(\S+)\s*\)"
            for pin, net in re.findall(regex, net_str):
                # replace constants
                if net == "1'b1":
                    net = tie_1
                elif net == "1'b0":
                    net = tie_0

                if pin in bb.inputs():
                    all_edges.append((net, f"{inst}.{pin}"))
                elif pin in bb.outputs():
                    # add intermediate net for outputs
                    all_nets["buf"].append(net)
                    all_edges.append((f"{inst}.{pin}", net))
                else:
                    raise ValueError(f"node {pin} not defined for blackbox {gate}")

            blackboxes_to_add[inst] = bb

    regex = r"assign\s+([a-zA-Z][a-zA-Z\d_]*)\s*=\s*([a-zA-Z\d][a-zA-Z\d_']*)\s*;"
    for n0, n1 in re.findall(regex, module):
        all_nets["buf"].append(n0)
        if n1 in ["1'b0", "1'h0", "1'd0"]:
            all_edges.append((tie_0, n0))
        elif n1 in ["1'b1", "1'h1", "1'd1"]:
            all_edges.append((tie_1, n0))
        else:
            all_edges.append((n1, n0))

    for k, v in all_nets.items():
        g.add_nodes_from(v, type=k, output=False)
    g.add_edges_from(all_edges)

    regex = r"(output)\s(.+?);"
    for _, net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.split(",")
        for net in nets:
            g.nodes[net.strip()]["output"] = True

    try:
        next(g.successors(tie_0))
    except StopIteration:
        g.remove_node(tie_0)

    try:
        next(g.successors(tie_1))
    except StopIteration:
        g.remove_node(tie_1)

    return Circuit(name=name, graph=g, blackboxes=blackboxes_to_add)
