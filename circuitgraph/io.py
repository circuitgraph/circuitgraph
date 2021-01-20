"""Functions for reading/writing CircuitGraphs"""

import re
import os
from glob import glob
from lark import Lark, Transformer
import tempfile

from circuitgraph import Circuit, BlackBox


def from_file(path, name=None, fmt=None, blackboxes=None):
    """
    Creates a new `Circuit` from a verilog file.

    Parameters
    ----------
    path: str
            the path to the file to read from.
    name: str
            the name of the module to read if different from the filename.
    fmt: str
            the format of the file to be read, overrides the extension.
    blackboxes: seq of BlackBox
            sub circuits in the circuit to be parsed.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    ext = path.split(".")[-1]
    if name is None:
        name = path.split("/")[-1].replace(f".{ext}", "")

    with open(path, "r") as f:
        netlist = f.read()

    if fmt == "verilog" or ext == "v":
        return verilog_to_circuit(netlist, name, blackboxes)
    elif fmt == "bench" or ext == "bench":
        return bench_to_circuit(netlist, name)
    else:
        raise ValueError(f"extension {ext} not supported")


def from_lib(name):
    """
    Creates a new `Circuit` from a netlist in the `netlists`
    folder

    Parameters
    ----------
    name: the name of the circuit.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    bbs = [BlackBox("ff", ["CK", "D"], ["Q"])]
    path = glob(f"{os.path.dirname(__file__)}/netlists/{name}.*")[0]
    return from_file(path, name, blackboxes=bbs)


def bench_to_circuit(netlist, name):
    """
    Creates a new Circuit from a netlist string.

    Parameters
    ----------
    netlist: str
            netlist code.
    name: str
            the module name.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    # create circuit
    c = Circuit(name=name)

    # get inputs
    in_regex = r"(?:INPUT|input)\s*\(\s*([a-zA-Z][a-zA-Z\d_]*)\s*\)"
    for net_str in re.findall(in_regex, netlist, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            c.add(n, "input")

    # handle gates
    regex = r"([a-zA-Z][a-zA-Z\d_]*)\s*=\s*(BUF|NOT|OR|NOR|AND|NAND|XOR|XNOR|buf|not|or|nor|and|nand|not|xor|xnor)\(([^\)]+)\)"
    for net, gate, input_str in re.findall(regex, netlist):
        # parse all nets
        inputs = (
            input_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        )
        c.add(net, gate.lower(), fanin=inputs)

    # get outputs
    in_regex = r"(?:OUTPUT|output)\s*\(\s*([a-zA-Z][a-zA-Z\d_]*)\s*\)"
    for net_str in re.findall(in_regex, netlist, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            driver = c.uid(f"{n}_driver")
            c.relabel({n: driver})
            c.add(n, "output", fanin=driver)

    return c


def verilog_to_circuit(netlist, name, blackboxes=None):
    """
    Creates a new Circuit from a module inside Verilog code.

    Parameters
    ----------
    path: str
            Verilog code.
    name: str
            Module name.
    blackboxes: seq of BlackBox
            Blackboxes in module.

    Returns
    -------
    Circuit
            Parsed circuit.
    """

    # parse module
    regex = f"module\s+{name}\s*\(.*?\);(.*?)endmodule"
    m = re.search(regex, netlist, re.DOTALL)
    module = m.group(1)

    # create circuit
    c = Circuit(name=name)

    # parse wires, will all be replaced with gate types
    regex = "wire\s(.+?);"
    for net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for net in nets:
            c.add(net, "wire")

    # parse io
    regex = "(input|output)\s(.+?);"
    for net_type, net_str in re.findall(regex, module, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for net in nets:
            c.add(net, net_type)

    # create output drivers, ensure unique names
    output_drivers = {o: c.add(f"{o}_driver", "wire", uid=True) for o in c.outputs()}

    # create constants, (will be removed if unused)
    tie_1 = c.add("tie_1", "1", uid=True)
    tie_0 = c.add("tie_0", "0", uid=True)

    # parse insts
    regex = "([a-zA-Z][a-zA-Z\d_]*)\s+([a-zA-Z][a-zA-Z\d_]*)\s*\(([^;]+)\);"
    for gate, inst, net_str in re.findall(regex, module, re.DOTALL):

        # parse generics
        if gate in set(["and", "nand", "or", "nor", "xor", "xnor", "buf", "not"]):
            # parse nets
            nets = (
                net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
            )

            # check for outputs, replace constants
            nets = [output_drivers[n] if n in output_drivers else n for n in nets]
            nets = [tie_1 if n == "1'b1" else n for n in nets]
            nets = [tie_0 if n == "1'b0" else n for n in nets]

            # add to graph
            c.add(nets[0], gate, fanin=nets[1:])

        # parse non-generics
        else:
            # get blackbox definition
            try:
                bb = next(bb for bb in blackboxes if bb.name == gate)
            except:
                raise ValueError(f"blackbox {gate} not defined")

            # parse pins
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

                if pin in bb.outputs:
                    # add intermediate net for outputs
                    connections[pin] = c.add(net, "buf")
                else:
                    connections[pin] = net

            # add inst
            c.add_blackbox(bb, inst, connections)

    # parse assigns
    class TreeToCircuit(Transformer):
        def add_not(self, items):
            io = "_".join(items)
            return c.add(f"not_{io}", "not", fanin=items[0], uid=True)

        def add_xor(self, items):
            io = "_".join(items)
            return c.add(f"xor_{io}", "xor", fanin=[items[0], items[1]], uid=True)

        def add_xnor(self, items):
            io = "_".join(items)
            return c.add(f"xnor_{io}", "xnor", fanin=[items[0], items[1]], uid=True)

        def add_and(self, items):
            io = "_".join(items)
            return c.add(f"and_{io}", "and", fanin=[items[0], items[1]], uid=True)

        def add_or(self, items):
            io = "_".join(items)
            return c.add(f"or_{io}", "or", fanin=[items[0], items[1]], uid=True)

        def add_mux(self, items):
            io = "_".join(items)
            n = c.add(f"mux_n_{io}", "not", fanin=items[0], uid=True)
            a0 = c.add(f"mux_a0_{io}", "and", fanin=[n, items[2]], uid=True)
            a1 = c.add(f"mux_a1_{io}", "and", fanin=[items[0], items[1]], uid=True)
            return c.add(f"mux_o_{io}", "or", fanin=[a0, a1], uid=True)

        def add_node(self, items):
            if items[0] in ["1'b0", "1'h0"]:
                return tie_0
            elif items[0] in ["1'b1", "1'h1"]:
                return tie_1
            elif items[0].value in output_drivers:
                return output_drivers[items[0].value]
            else:
                return items[0].value

    exp_parser = Lark(
        r"""
        ?cond : or
              | or "?" or ":" or -> add_mux

        ?or : xor
              | or "|" xor -> add_or

        ?xor : and
              | xor "^" and -> add_xor
              | xor "~^" and -> add_xnor
              | xor "^~" and -> add_xnor

        ?and : unary
             | and "&" unary -> add_and

        ?unary : primary
                | ( "!" | "~" ) primary -> add_not

        ?primary : VAL -> add_node
                  | "(" or ")"

        VAL : CNAME | "1'b0" | "1'b1" | "1'h0" | "1'h1"

        %import common.CNAME
        %import common.WS
        %ignore WS
    """,
        start="cond",
    )

    # parse expressions
    regex = "assign\s+(.+?)\s*=\s*(.+?)\s*;"
    for n0, n1 in re.findall(regex, module):
        tree = exp_parser.parse(n1)
        rhs = TreeToCircuit(c).transform(tree)
        if n0 in output_drivers:
            n0 = output_drivers[n0]
        c.add(n0, "buf", fanin=rhs)

    # connect outputs
    for o, od in output_drivers.items():
        c.connect(od, o)

    # remove unused ties
    # cg.lint(c)
    # check for unconnected wires
    if "wire" in c.type(c.nodes()):
        raise ValueError(f"uninitialized wire")

    return c


def to_file(c, path):
    """
    Writes a `Circuit` to a Verilog file.

    Parameters
    ----------
    c: Circut
            the circuit
    path: str
            the path to the file to read from.
    """
    with open(path, "w") as f:
        f.write(circuit_to_verilog(c))


def circuit_to_verilog(c):
    """
    Generates a str of Verilog code from a `CircuitGraph`.

    Parameters
    ----------
    c: Circuit
            the circuit to turn into Verilog.

    Returns
    -------
    str
        Verilog code.
    """
    inputs = []
    outputs = []
    insts = []
    wires = []

    # blackboxes
    output_map = {}
    for name, bb in c.blackboxes.items():
        io = []
        for n in bb.inputs:
            driver = c.fanin(f"{name}.{n}").pop()
            io += [f".{n}({driver})"]

        for n in bb.outputs:
            w = c.uid(f"{name}_{n}_load")
            wires.append(w)
            output_map[f"{name}.{n}"] = w
            io += [f".{n}({w})"]

        io_def = ", ".join(io)
        insts.append(f"{bb.name} {name} ({io_def})")

    # gates
    for n in c.nodes():
        if c.type(n) in ["xor", "xnor", "buf", "not", "nor", "or", "and", "nand"]:
            fanin = [output_map[f] if f in output_map else f for f in c.fanin(n)]
            fanin = ", ".join(fanin)
            insts.append(f"{c.type(n)} g_{len(insts)} " f"({n}, {fanin})")
            wires.append(n)
        elif c.type(n) in ["0", "1"]:
            insts.append(f"assign {n} = 1'b{c.type(n)}")
            wires.append(n)
        elif c.type(n) in ["input"]:
            inputs.append(n)
        elif c.type(n) in ["output"]:
            fanin = c.fanin(n).pop()
            if fanin in output_map:
                fanin = output_map[fanin]
            insts.append(f"assign {n} = {fanin}")
            outputs.append(n)
        elif c.type(n) in ["bb_output", "bb_input"]:
            pass
        else:
            raise ValueError(f"unknown gate type: {c.type(n)}")

    verilog = f"module {c.name} ("
    verilog += ", ".join(inputs + outputs)
    verilog += ");\n"
    verilog += "".join(f"  input {inp};\n" for inp in inputs)
    verilog += "\n"
    verilog += "".join(f"  output {out};\n" for out in outputs)
    verilog += "\n"
    verilog += "".join(f"  wire {wire};\n" for wire in wires)
    verilog += "\n"
    verilog += "".join(f"  {inst};\n" for inst in insts)
    verilog += "endmodule\n"

    return verilog


def circuit_to_bench(c):
    """
    Generates a str of Bench code from a `CircuitGraph`.

    Parameters
    ----------
    c: Circuit
            the circuit to turn into Bench.

    Returns
    -------
    str
        Bench code.
    """
    inputs = []
    outputs = []
    insts = []

    if c.blackboxes:
        raise ValueError(f"Bench format does not support blackboxes: {c.name}")

    # gates
    const_inp = c.inputs().pop()
    for n in c.nodes():
        if c.type(n) in ["xor", "xnor", "buf", "not", "nor", "or", "and", "nand"]:
            fanin = ", ".join(c.fanin(n))
            insts.append(f"{n} = {c.type(n).upper()}({fanin})")
        elif c.type(n) in ["0"]:
            insts.append(f"{n} = XOR({const_inp}, {const_inp})")
        elif c.type(n) in ["1"]:
            insts.append(f"{n} = XNOR({const_inp}, {const_inp})")
        elif c.type(n) in ["input"]:
            inputs.append(n)
        elif c.type(n) in ["output"]:
            fanin = c.fanin(n).pop()
            insts.append(f"{n} = BUF({fanin})")
            outputs.append(n)
        else:
            raise ValueError(f"unknown gate type: {c.type(n)}")

    bench = f"# {c.name}\n"
    bench += "".join(f"INPUT({inp})\n" for inp in inputs)
    bench += "\n"
    bench += "".join(f"OUTPUT({out};)\n" for out in outputs)
    bench += "\n"
    bench += "\n".join(insts)

    return bench
