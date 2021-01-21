"""Functions for reading/writing CircuitGraphs"""

import re
import os
from glob import glob
from lark import Lark, Transformer, v_args
import tempfile

from circuitgraph import Circuit, BlackBox
from circuitgraph.parsing import get_verilog_parser


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
    regex = f"(module\s+{name}\s*\(.*?\);(.*?)endmodule)"
    m = re.search(regex, netlist, re.DOTALL)
    module = m.group(1)

    if blackboxes is None:
        blackboxes = []

    verilog_parser = get_verilog_parser(blackboxes)

    c = verilog_parser.parse(module)
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

    # sanitize escaped nets
    for node in c.nodes():
        if node.startswith('\\'):
            c.relabel({node: node + ' '})

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

    # de-sanitize escaped nets
    for node in c.nodes():
        if node.startswith('\\'):
            c.relabel({node: node[:-1]})

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
