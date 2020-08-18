"""Functions for reading/writing CircuitGraphs"""

import re
import os
from glob import glob

from pyeda.parsing import boolexpr
import pyverilog
from pyverilog.vparser.parser import VerilogParser
from pyverilog.vparser import ast as ast_types

from circuitgraph import Circuit


class SequentialElement:
    """Defines a representation of a sequential element for reading/writing
    sequential circuits."""

    def __init__(self, name, seq_type, io, code_def):
        """
        Parameters
        ----------
        name: str
                Name of the element (the module name)
        seq_type: str
                The type of sequential element, either 'ff' or 'lat'
        io: dict of str:str
                The mapping the 'd', 'q', 'clk', and potentially 'r', 's'
                ports to the names of the ports on the module
        code_def:
                The code defining the module, used for writing the circuit
                to verilog
        """
        self.name = name
        self.seq_type = seq_type
        self.io = io
        self.code_def = code_def


default_seq_types = [
    SequentialElement(
        name="fflopd",
        seq_type="ff",
        io={"d": "D", "q": "Q", "clk": "CK"},
        code_def="module fflopd(CK, D, Q);\n"
        "  input CK, D;\n"
        "  output Q;\n"
        "  wire CK, D;\n"
        "  wire Q;\n"
        "  wire next_state;\n"
        "  reg  qi;\n"
        "  assign #1 Q = qi;\n"
        "  assign next_state = D;\n"
        "  always\n"
        "    @(posedge CK)\n"
        "      qi <= next_state;\n"
        "  initial\n"
        "    qi <= 1'b0;\n"
        "endmodule",
    ),
    SequentialElement(
        name="latchdrs",
        seq_type="lat",
        io={"d": "D", "q": "Q", "clk": "ENA", "r": "R", "s": "S"},
        code_def="",
    ),
]


cadence_seq_types = [
    # Note that this is a modified version of CDN_flop with only a synchronous
    # reset that always resets to 0
    SequentialElement(
        name="CDN_flop",
        seq_type="ff",
        io={"d": "d", "q": "q", "clk": "clk", "r": "srl"},
        code_def="module CDN_flop(clk, d, srl, q);\n"
        "  input clk, d, srl;\n"
        "  output q;\n"
        "  wire clk, d, srl;\n"
        "  wire q;\n"
        "  reg  qi;\n"
        "  assign #1 q = qi;\n"
        "  always\n"
        "    @(posedge clk)\n"
        "      if (srl)\n"
        "        qi <= 1'b0;\n"
        "      else if (sena)\n"
        "        qi <= d;\n"
        "      end\n"
        "  initial\n"
        "    qi <= 1'b0;\n"
        "endmodule",
    )
]


def from_file(path, name=None, seq_types=None):
    """
    Creates a new `Circuit` from a verilog file.

    Parameters
    ----------
    path: str
            the path to the file to read from.
    name: str
            the name of the module to read if different from the filename.
    seq_types: list of dicts of str:str
            the types of sequential elements in the file.

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
    if ext == "v":
        return verilog_to_circuit(netlist, name, seq_types)
    elif ext == "bench":
        return bench_to_circuit(netlist, name)
    else:
        raise ValueError(f"extension {ext} not supported")


def from_lib(circuit, name=None):
    """
    Creates a new `Circuit` from a netlist in the `../netlists`
    folder

    Parameters
    ----------
    circuit: the name of the netlist.
    name: the module name, if different from the netlist name.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    path = glob(f"{os.path.dirname(__file__)}/../netlists/{circuit}.*")[0]
    return from_file(path, name)


def bench_to_circuit(bench, name):
    """
    Creates a new Circuit from a bench string.

    Parameters
    ----------
    bench: str
            bench code.
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
    in_regex = r"(?:INPUT|input)\s*\((.+?)\)"
    for net_str in re.findall(in_regex, bench, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            c.add(n, "input")

    # handle gates
    regex = r"(\S+)\s*=\s*(NOT|OR|NOR|AND|NAND|XOR|XNOR|not|or|nor|and|nand|not|xor|xnor)\((.+?)\)"
    for net, gate, input_str in re.findall(regex, bench):
        # parse all nets
        inputs = (
            input_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        )
        c.add(net, gate.lower(), fanin=inputs)

    # get outputs
    in_regex = r"(?:OUTPUT|output)\s*\((.+?)\)"
    for net_str in re.findall(in_regex, bench, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            c.set_output(n)

    return c


def verilog_to_circuit(verilog, name, seq_types=None):
    """
    Creates a new Circuit from a verilog file.

    Parameters
    ----------
    path: str
            verilog code.
    name: str
            the module name.
    seq_types: list of dicts of str:str
            the sequential element types.

    Returns
    -------
    Circuit
            the parsed circuit.
    """
    if seq_types is None:
        seq_types = default_seq_types

    c = Circuit(name=name)

    codeparser = VerilogParser(debug=False)
    ast = codeparser.parse(verilog, debug=False)
    description = ast.children()[0]

    module_def = [d for d in description.children() if d.name == name]
    if not module_def:
        raise ValueError(f"Module {name} not found")
    module_def = module_def[0]
    outputs = set()
    widths = dict()
    for child in module_def.children():
        if type(child) == ast_types.Paramlist:
            if child.children():
                raise ValueError(
                    "circuitgraph cannot parse parameters " f"(line {child.lineno})"
                )
        # Parse portlist
        elif type(child) == ast_types.Portlist:
            for cip in [i for i in child.children() if type(i) == ast_types.Ioport]:
                for ci in cip.children():
                    parse_io(c, ci, outputs)
        # Parse declarations
        elif type(child) == ast_types.Decl:
            if ast_types.Parameter in [type(i) for i in child.children()]:
                raise ValueError(
                    "circuitgraph cannot parse parameters " f"(line {child.lineno})"
                )
            for ci in [
                i
                for i in child.children()
                if type(i) in [ast_types.Input, ast_types.Output]
            ]:
                parse_io(c, ci, outputs)
        # Parse instances
        elif type(child) == ast_types.InstanceList:
            # FIXME: Parse sequential elements
            for instance in child.instances:
                if instance.module in [
                    "and",
                    "nand",
                    "or",
                    "nor",
                    "xor",
                    "xnor",
                    "buf",
                ]:
                    gate = instance.module
                    dest = parse_argument(instance.portlist[0].argname, c)
                    sources = [
                        parse_argument(i.argname, c) for i in instance.portlist[1:]
                    ]
                    c.add(dest, gate, fanin=sources, output=dest in outputs)
                else:
                    raise ValueError(
                        "circuitgraph cannot parse instance of "
                        f"type {instance.module} (line "
                        f"{instance.lineno})"
                    )
        # Parse assigns
        elif type(child) == ast_types.Assign:
            dest = child.left.var
            dest = parse_argument(dest, c)
            if type(child.right.var) == ast_types.IntConst:
                c.add(child.right.var.value, child.right.var.value)
                c.add(dest, "buf", fanin=child.right.var.value, output=dest in outputs)
            elif issubclass(type(child.right.var), ast_types.Operator):
                parse_operator(child.right.var, c, outputs, dest=dest)
            elif issubclass(type(child.right.var), ast_types.Concat):
                raise ValueError(
                    "circuitgraph cannot parse concatenations "
                    f"(line {child.right.var.lineno})"
                )
        else:
            raise ValueError(
                "circuitgraph cannot parse statements of type "
                f"{type(child)} (line {child.lineno})"
            )

    return c


def parse_io(c, ci, outputs):
    if ci.width:
        cis = [
            f"{ci.name}[{i}]"
            for i in range(int(ci.width.lsb.value), int(ci.width.msb.value) + 1)
        ]
    else:
        cis = [ci.name]
    if type(ci) == ast_types.Input:
        for i in cis:
            c.add(i, "input")
    elif type(ci) == ast_types.Output:
        outputs.update(set(cis))


def parse_argument(argname, circuit):
    if type(argname) == ast_types.Pointer:
        return f"{argname.var}[{argname.ptr}]"
    elif type(argname) == ast_types.IntConst:
        circuit.add(argname.value, argname.value)
        return argname.value
    elif issubclass(type(argname), ast_types.Concat):
        raise ValueError(
            "circuitgraph cannot parse concatenations " f"(line {argname.lineno})"
        )
    elif type(argname) == ast_types.Partselect:
        raise ValueError(
            "circuitgrpah cannot parse part select "
            f"statements (line {argname.lineno})"
        )
    return argname.name


def parse_operator(operator, circuit, outputs, dest=None):
    if type(operator) == ast_types.IntConst:
        circuit.add(operator.value, operator.value)
        return operator.value
    elif not issubclass(type(operator), ast_types.Operator):
        return parse_argument(operator, circuit)
    fanin = [parse_operator(o, circuit, outputs) for o in operator.children()]
    op = str(operator)[1:].split()[0].lower()
    if dest is None:
        dest = f"{op}_{'_'.join(fanin)}"
    circuit.add(dest, op, fanin=fanin, output=dest in outputs)
    return dest


def to_file(c, path, seq_types=None):
    """
    Writes a `Circuit` to a verilog file.

    Parameters
    ----------
    c: Circut
            the circuit
    path: str
            the path to the file to read from.
    seq_types: list of dicts of str:str
            the types of sequential elements in the file.
    """
    with open(path, "w") as f:
        f.write(circuit_to_verilog(c, seq_types))


def circuit_to_verilog(c, seq_types=None):
    """
    Generates a str of verilog code from a `CircuitGraph`.

    Parameters
    ----------
    c: Circuit
            the circuit to turn into verilog.
    seq_types: list of dicts of str:str
            the sequential element types.

    Returns
    -------
    str
        verilog code.
    """
    inputs = []
    outputs = []
    insts = []
    wires = []
    defs = set()

    if seq_types is None:
        seq_types = default_seq_types

    for n in c.nodes():
        if c.type(n) in ["xor", "xnor", "buf", "not", "nor", "or", "and", "nand"]:
            fanin = ",".join(p for p in c.fanin(n))
            insts.append(f"{c.type(n)} g_{n} ({n},{fanin})")
            wires.append(n)
        elif c.type(n) in ["0", "1"]:
            insts.append(f"assign {n} = 1'b{c.type(n)}")
        elif c.type(n) in ["input"]:
            inputs.append(n)
            wires.append(n)
        elif c.type(n) in ["ff", "lat"]:
            wires.append(n)

            # get template
            for s in seq_types:
                if s.seq_type == c.type(n):
                    seq = s
                    defs.add(s.code_def)
                    break

            # connect
            io = []
            if c.d(n):
                d = c.d(n)
                io.append(f".{seq['io']['d']}({d})")
            if c.r(n):
                r = c.r(n)
                io.append(f".{seq['io']['r']}({r})")
            if c.s(n):
                s = c.s(n)
                io.append(f".{seq['io']['s']}({s})")
            if c.clk(n):
                clk = c.clk(n)
                io.append(f".{seq['io']['clk']}({clk})")
            io.append(f".{seq['io']['q']}({n})")
            insts.append(f"{s['name']} g_{n} ({','.join(io)})")

        else:
            print(f"unknown gate type: {c.type(n)}")
            return

        if c.output(n):
            outputs.append(n)

    verilog = f"module {c.name} (" + ",".join(inputs + outputs) + ");\n"
    verilog += "".join(f"input {inp};\n" for inp in inputs)
    verilog += "".join(f"output {out};\n" for out in outputs)
    verilog += "".join(f"wire {wire};\n" for wire in wires)
    verilog += "".join(f"{inst};\n" for inst in insts)
    verilog += "endmodule\n"
    verilog += "\n".join(defs)

    return verilog
