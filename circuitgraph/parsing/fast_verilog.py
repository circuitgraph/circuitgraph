import re
import random
from collections import defaultdict

import networkx as nx

from circuitgraph import Circuit
from circuitgraph.parsing import addable_types


def fast_parse_verilog_netlist(netlist, blackboxes):
    """
    A fast version of `parse_verilog_netlist` that can speed up parsing on
    very large netlists by making a handful of assumptions. It is much
    safer to use `parse_verilog_netlist`. This function should only be used
    if necessary.

    The input netlist must conform to the following rules:
        - Only one module definition is present
        - There are no comments
        - Only primitive gate or module instantiations, no assign statements
        - Primitive gates can only have one output
        - Only one instantation per line (e.g. `buf b1(a, b) b2(c, d);` is
          not allowed)
        - No expressions (e.g. `buf (a, b & c);` is not allowed)
        - No escaped identifiers
        - The only constants that may be used are `1'b0` and `1'b1`

    The code does not overtly check that these rules are satisfied, and if
    they are not this function may still return a malformed Circuit object.
    It is up to the caller of the function to assure that these rules are
    followed.

    Note that normal error checking that is done in `parse_verilog_netlist` is
    skipped in this function (e.g. checking if nets are declared as wires,
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

    regex = f"module\s+(.+?)\s*\(.*?\);"
    m = re.search(regex, netlist, re.DOTALL)
    name = m.group(1)
    module = netlist[m.end() :]

    regex = f"endmodule"
    m = re.search(regex, netlist, re.DOTALL)
    module = module[: m.start()]

    # create graph
    g = nx.DiGraph()

    # parse io
    regex = "(input)\s(.+?);"
    inputs = set()
    for net_type, net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.split(",")
        for net in nets:
            inputs.add(net.strip())
    g.add_nodes_from(inputs, type="input")

    regex = "(output)\s(.+?);"
    outputs = set()
    for net_type, net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.split(",")
        for net in nets:
            outputs.add(net.strip())
    g.add_nodes_from(outputs, type="output")

    # create output drivers, ensure unique names
    output_drivers = dict()
    for o in outputs:
        driver = f"{o}_driver"
        while driver in g:
            driver = f"{o}_driver_{random.randint(1111, 9999)}"
        output_drivers[o] = driver

    g.add_nodes_from(output_drivers.values(), type="wire")
    g.add_edges_from((v, k) for k, v in output_drivers.items())

    # create constants, (will be removed if unused)
    tie_0 = "tie_0"
    while tie_0 in g:
        tie_0 = "tie_0_{random.randint(1111, 9999)}"
    tie_1 = "tie_1"
    while tie_1 in g:
        tie_1 = "tie_1_{random.randint(1111, 9999)}"
    g.add_node(tie_0, type="0")
    g.add_node(tie_1, type="1")

    # parse insts
    regex = "([a-zA-Z][a-zA-Z\d_]*)\s+([a-zA-Z][a-zA-Z\d_]*)\s*\(([^;]+)\);"

    all_nets = defaultdict(list)
    all_edges = list()
    blackboxes_to_add = dict()
    for gate, inst, net_str in re.findall(regex, module, re.DOTALL):

        # parse generics
        if gate in addable_types:
            # parse nets
            nets = [n.strip() for n in net_str.split(",")]

            # check for outputs, replace constants
            nets = [
                output_drivers[n]
                if n in output_drivers
                else tie_0
                if n == "1'b0"
                else tie_1
                if n == "1'b1"
                else n
                for n in nets
            ]

            all_nets[gate].append(nets[0])
            all_edges += [(i, nets[0]) for i in nets[1:]]

        # parse non-generics
        else:
            # get blackbox definition
            try:
                bb = next(bb for bb in blackboxes if bb.name == gate)
            except:
                raise ValueError(f"blackbox {gate} not defined")

            # parse pins
            all_nets["bb_input"] += [f"{inst}.{n}" for n in bb.inputs()]
            all_nets["bb_output"] += [f"{inst}.{n}" for n in bb.outputs()]

            regex = "\.\s*(\S+)\s*\(\s*(\S+)\s*\)"
            connections = {}
            for pin, net in re.findall(regex, net_str):
                # check for outputs
                if net in output_drivers:
                    net = output_drivers[net]
                elif net == "1'b1":
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

    for k, v in all_nets.items():
        g.add_nodes_from(v, type=k)
    g.add_edges_from(all_edges)

    return Circuit(name=name, graph=g, blackboxes=blackboxes_to_add)
