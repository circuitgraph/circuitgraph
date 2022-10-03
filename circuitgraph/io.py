"""Functions for reading/writing CircuitGraphs."""
import re
from pathlib import Path

from circuitgraph import BlackBox, Circuit
from circuitgraph.parsing import fast_parse_verilog_netlist, parse_verilog_netlist

generic_flop = BlackBox("ff", ["clk", "d"], ["q"])

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
    Create a new `Circuit` from a verilog file.

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
    with open(path) as f:
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
    if fmt == "bench" or path.suffix == ".bench":
        return bench_to_circuit(netlist, name)
    raise ValueError(f"extension {path.suffix} not supported")


def from_lib(name):
    """
    Create a new `Circuit` from a netlist in the `netlists` folder.

    Parameters
    ----------
    name: the name of the circuit.

    Returns
    -------
    Circuit
            the parsed circuit.

    """
    bbs = [BlackBox("ff", ["CK", "D"], ["Q"])] + genus_flops + dc_flops
    [path] = Path(__file__).parent.absolute().glob(f"netlists/{name}.*")
    return from_file(path, name, blackboxes=bbs)


def bench_to_circuit(netlist, name):
    """
    Create a new Circuit from a netlist string.

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
    gate_types = ["buf", "buff", "not", "or", "nor", "and", "nand", "xor", "xnor"]
    gate_types = "|".join(gate_types + [s.upper() for s in gate_types])
    regex = rf"([a-zA-Z][a-zA-Z\d_]*)\s*=\s*({gate_types})\(([^\)]+)\)"
    for net, gate, input_str in re.findall(regex, netlist):
        # parse all nets
        inputs = (
            input_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        )
        if gate in ("buff", "BUFF"):
            gate = "buf"
        c.add(
            net,
            gate.lower(),
            fanin=inputs,
            add_connected_nodes=True,
            allow_redefinition=True,
        )

    regex = r"([a-zA-Z][a-zA-Z\d_]*)\s*=\s*(DFF|dff)\(([^\)]+)\)"
    for net, gate, input_str in re.findall(regex, netlist):
        # parse all nets
        inputs = input_str.replace(" ", "").replace("\n", "").replace("\t", "")
        c.add(net, "buf", allow_redefinition=True)
        c.add_blackbox(dff, f"{net}_dff", connections={"D": inputs, "Q": net})

    # get outputs
    in_regex = r"(?:OUTPUT|output)\s*\(\s*([a-zA-Z][a-zA-Z\d_]*)\s*\)"
    for net_str in re.findall(in_regex, netlist, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            c.set_output(n)

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
    Create a new Circuit from a module inside Verilog code.

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
    regex = rf"(module\s+{name}\s*\(.*?\);(.*?)endmodule)"
    m = re.search(regex, netlist, re.DOTALL)
    try:
        module = m.group(1)
    except AttributeError as e1:
        if infer_module_name:
            regex = r"(module\s+(.*?)\s*\(.*?\);(.*?)endmodule)"
            m = re.search(regex, netlist, re.DOTALL)
            try:
                module = m.group(1)
            except AttributeError as e2:
                raise ValueError("Could not read netlist: no modules found") from e2
        else:
            raise ValueError(f"Could not read netlist: {name} module not found") from e1

    return parse_verilog_netlist(module, blackboxes, warnings, error_on_warning)


def to_file(c, path, fmt="verilog", behavioral=False):
    """
    Write a `Circuit` to a Verilog file.

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
            f.write(circuit_to_verilog(c, behavioral=behavioral))
        elif fmt == "bench":
            f.write(circuit_to_bench(c))
        else:
            raise ValueError(f"Unrecognized fmt: {fmt}")


def circuit_to_verilog(c, behavioral=False):
    """
    Generate a `str` of Verilog code from a `CircuitGraph`.

    Parameters
    ----------
    c: Circuit
            the circuit to turn into Verilog.
    behavioral: bool
            if True, use assign statements instead of primitive gates.

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

    # blackboxes
    for name, bb in c.blackboxes.items():
        io = []
        for n in bb.inputs():
            try:
                driver = c.fanin(f"{name}.{n}").pop()
                io += [f".{n}({driver})"]
            except KeyError:
                io += [f".{n}()"]

        for n in bb.outputs():
            try:
                driven = c.fanout(f"{name}.{n}").pop()
                # Disconnect so no buffer is created
                c.disconnect(f"{name}.{n}", driven)
                io += [f".{n}({driven})"]
            except KeyError:
                io += [f".{n}()"]

        io_def = ", ".join(io)
        insts.append(f"{bb.name} {name} ({io_def})")

    # gates
    for n in c.nodes():
        if c.type(n) in ["xor", "xnor", "buf", "not", "nor", "or", "and", "nand"]:
            wires.append(n)
            fanin = list(c.fanin(n))
            if not fanin:
                continue
            if behavioral:
                if c.type(n) == "buf":
                    insts.append(f"assign {n} = {fanin[0]}")
                elif c.type(n) == "not":
                    insts.append(f"assign {n} = ~{fanin[0]}")
                else:
                    if c.type(n) in ["xor", "xnor"]:
                        symbol = "^"
                    elif c.type(n) in ["and", "nand"]:
                        symbol = "&"
                    elif c.type(n) in ["nor", "or"]:
                        symbol = "|"
                    fanin = f" {symbol} ".join(fanin)
                    if c.type(n) in ["xnor", "nor", "nand"]:
                        insts.append(f"assign {n} = ~({fanin})")
                    else:
                        insts.append(f"assign {n} = {fanin}")
            else:
                fanin = ", ".join(fanin)
                gate_name = c.uid(f"g_{len(insts)}")
                insts.append(f"{c.type(n)} {gate_name}({n}, {fanin})")
        elif c.type(n) in ["0", "1", "x"]:
            insts.append(f"assign {n} = 1'b{c.type(n)}")
            wires.append(n)
        elif c.type(n) in ["input", "bb_input", "bb_output"]:
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
    Generate a `str` of Bench code from a `CircuitGraph`.

    Parameters
    ----------
    c: Circuit
            the circuit to turn into Bench.

    Returns
    -------
    str
        Bench code.

    """
    insts = []

    if c.blackboxes:
        raise ValueError(f"Bench format does not support blackboxes: {c.name}")

    # gates
    const_inp = c.inputs().pop()
    for n in c.nodes() - c.inputs():
        if c.type(n) in ["xor", "xnor", "buf", "not", "nor", "or", "and", "nand"]:
            fanin = ", ".join(c.fanin(n))
            insts.append(f"{n} = {c.type(n).upper()}({fanin})")
        elif c.type(n) in ["0"]:
            insts.append(f"{n} = XOR({const_inp}, {const_inp})")
        elif c.type(n) in ["1"]:
            insts.append(f"{n} = XNOR({const_inp}, {const_inp})")
        else:
            raise ValueError(f"unknown gate type: {c.type(n)}")

    bench = f"# {c.name}\n"
    bench += "".join(f"INPUT({inp})\n" for inp in c.inputs())
    bench += "\n"
    bench += "".join(f"OUTPUT({out})\n" for out in c.outputs())
    bench += "\n"
    bench += "\n".join(insts)

    return bench
