"""Functions for reading/writing CircuitGraphs"""

import re
from pathlib import Path

from circuitgraph import Circuit, BlackBox
from circuitgraph.parsing import parse_verilog_netlist, fast_parse_verilog_netlist


genus_flops = [
    BlackBox("flopd", ["CK", "D"], ["Q"]),
    BlackBox("fflopd", ["CK", "D"], ["Q"]),
    BlackBox("flopdrs", ["CK", "D", "R", "S"], ["Q"]),
    BlackBox("fflopdrs", ["CK", "D", "R", "S"], ["Q"]),
]


dc_flops = [
    BlackBox("GTECH_FD1", ["CP", "D"], ["Q", "QN"]),
    BlackBox("GTECH_FD2", ["CP", "CD", "D"], ["Q", "QN"]),
    BlackBox("GTECH_FD3", ["CP", "CD", "SD", "D"], ["Q", "QN"]),
]


def from_file(
    path,
    name=None,
    fmt=None,
    blackboxes=None,
    warnings=False,
    error_on_warning=False,
    fast=False,
):
    """
    Creates a new `Circuit` from a verilog file.

    Parameters
    ----------
    path: str or pathlib.Path
            the path to the file to read from.
    name: str
            the name of the module to read if different from the filename.
    fmt: str
            the format of the file to be read, overrides the extension.
    blackboxes: seq of BlackBox
            sub circuits in the circuit to be parsed.
    warnings: bool
            If True, warnings about unused nets will be printed.
    error_on_warning: bool
            If True, unused nets will cause raise `VerilogParsingWarning`
            exceptions.
    fast: bool
            If True, uses the `fast_parse_verilog_netlist` function from
            parsing/fast_verilog.py. This function is faster for parsing
            very large netlists, but makes stringent assumptions about
            the netlist and does not provide error checking. Read
            the docstring for `fast_parse_verilog_netlist` in order to
            confirm that `netlist` adheres to these assumptions before
            using this flag.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    path = Path(path)
    infer_module_name = False
    if name is None:
        infer_module_name = True
        name = path.stem
    with open(path, "r") as f:
        netlist = f.read()
    if fmt == "verilog" or path.suffix == ".v":
        return verilog_to_circuit(
            netlist,
            name,
            infer_module_name,
            blackboxes,
            warnings,
            error_on_warning,
            fast,
        )
    elif fmt == "bench" or path.suffix == ".bench":
        return bench_to_circuit(netlist, name)
    else:
        raise ValueError(f"extension {path.suffix} not supported")


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
    [path] = Path(__file__).parent.absolute().glob(f"netlists/{name}.*")
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

    dff = BlackBox("dff", ["D"], ["Q"])

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

    regex = r"([a-zA-Z][a-zA-Z\d_]*)\s*=\s*(DFF|dff)\(([^\)]+)\)"
    for net, gate, input_str in re.findall(regex, netlist):
        # parse all nets
        inputs = input_str.replace(" ", "").replace("\n", "").replace("\t", "")
        c.add(net, "buf")
        c.add_blackbox(dff, f"{net}_dff", connections={"D": inputs, "Q": net})

    # get outputs
    in_regex = r"(?:OUTPUT|output)\s*\(\s*([a-zA-Z][a-zA-Z\d_]*)\s*\)"
    for net_str in re.findall(in_regex, netlist, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            driver = c.uid(f"{n}_driver")
            c.relabel({n: driver})
            c.add(n, "output", fanin=driver)

    return c


def verilog_to_circuit(
    netlist,
    name,
    infer_module_name=False,
    blackboxes=None,
    warnings=False,
    error_on_warning=False,
    fast=False,
):
    """
    Creates a new Circuit from a module inside Verilog code.

    Parameters
    ----------
    netlist: str
            Verilog code.
    name: str
            Module name.
    infer_module_name: bool
            If True and no module named `name` is found, parse the first
            module in the netlist.
    blackboxes: seq of BlackBox
            Blackboxes in module.
    warnings: bool
            If True, warnings about unused nets will be printed.
    error_on_warning: bool
            If True, unused nets will cause raise `VerilogParsingWarning`
            exceptions.
    fast: bool
            If True, uses the `fast_parse_verilog_netlist` function from
            parsing/fast_verilog.py. This function is faster for parsing
            very large netlists, but makes stringent assumptions about
            the netlist and does not provide error checking. Read
            the docstring for `fast_parse_verilog_netlist` in order to
            confirm that `netlist` adheres to these assumptions before
            using this flag.

    Returns
    -------
    Circuit
            Parsed circuit.
    """

    if blackboxes is None:
        blackboxes = []

    if fast:
        return fast_parse_verilog_netlist(netlist, blackboxes)

    # parse module
    regex = f"(module\s+{name}\s*\(.*?\);(.*?)endmodule)"
    m = re.search(regex, netlist, re.DOTALL)
    try:
        module = m.group(1)
    except AttributeError:
        if infer_module_name:
            regex = f"(module\s+(.*?)\s*\(.*?\);(.*?)endmodule)"
            m = re.search(regex, netlist, re.DOTALL)
            try:
                module = m.group(1)
            except AttributeError:
                raise ValueError("Could not read netlist: no modules found")
        else:
            raise ValueError(f"Could not read netlist: {name} module not found")

    return parse_verilog_netlist(module, blackboxes, warnings, error_on_warning)


def to_file(c, path, fmt="verilog"):
    """
    Writes a `Circuit` to a Verilog file.

    Parameters
    ----------
    c: Circut
            the circuit
    path: str
            the path to the file to read from.
    fmt: str
            the format of the file (verilog or bench)
    """
    with open(path, "w") as f:
        if fmt == "verilog":
            f.write(circuit_to_verilog(c))
        elif fmt == "bench":
            f.write(circuit_to_bench(c))
        else:
            raise ValueError(f"Unrecognized fmt: {fmt}")


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
    c = Circuit(graph=c.graph.copy(), name=c.name, blackboxes=c.blackboxes.copy())
    # sanitize escaped nets
    for node in c.nodes():
        if node.startswith("\\"):
            c.relabel({node: node + " "})

    inputs = list(c.inputs())
    outputs = list(c.outputs())
    insts = []
    wires = []

    # remove outputs drivers
    driver_mapping = dict()
    for output in outputs:
        if len(c.fanin(output)) > 1:
            raise ValueError(f"Output {output} has multiple drivers.")
        elif len(c.fanin(output)) == 1:
            driver = c.fanin(output).pop()
            if c.type(driver) in ["input", "1", "0"]:
                driver = c.add(f"{output}_driver", type="buf", fanin=driver, uid=True)
            driver_mapping[driver] = output
    c.remove(c.outputs())
    c.relabel(driver_mapping)

    # blackboxes
    output_map = {}
    for name, bb in c.blackboxes.items():
        io = []
        for n in bb.inputs():
            driver = c.fanin(f"{name}.{n}").pop()
            io += [f".{n}({driver})"]

        for n in bb.outputs():
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
        elif c.type(n) in ["0", "1", "x"]:
            insts.append(f"assign {n} = 1'b{c.type(n)}")
            wires.append(n)
        elif c.type(n) in ["input", "output", "bb_input", "bb_output"]:
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
