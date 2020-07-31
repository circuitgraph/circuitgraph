"""Functions for reading/writing CircuitGraphs"""

import re
import os

from pyeda.parsing import boolexpr

from circuitgraph import Circuit


# Because there are no standards for sequential elements in Verilog, it may be
# necessary to define custom sequential types that differ from these
# TODO: We should probably make a class for this to make it easier to define
#       custom types
default_seq_types = [
    {
        "name": "fflopd",
        "type": "ff",
        "io": {"d": "D", "q": "Q", "clk": "CK"},
        "def": "module fflopd(CK, D, Q);"
        "input CK, D;"
        "output Q;"
        "wire CK, D;"
        "wire Q;"
        "wire next_state;"
        "reg  qi;"
        "assign #1 Q = qi;"
        "assign next_state = D;"
        "always"
        "  @(posedge CK)"
        "    qi <= next_state;"
        "initial"
        "  qi <= 1'b0;"
        "endmodule",
    },
    {
        "name": "latchdrs",
        "type": "lat",
        "io": {"d": "D", "q": "Q", "clk": "ENA", "r": "R", "s": "S"},
        "def": "",
    },
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
    if name is None:
        name = path.split("/")[-1].replace(".v", "")
    with open(path, "r") as f:
        verilog = f.read()
    return verilog_to_circuit(verilog, name, seq_types)


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
    path = f"{os.path.dirname(__file__)}/../netlists/{circuit}.v"
    return from_file(path, name)


def verilog_to_circuit(verilog, name, seq_types=None):
    """
    Creates a new Circuit from a verilog string.

    Parameters
    ----------
    verilog: str
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

    # extract module
    regex = rf"module\s+{name}\s*\(.*?\);(.*?)endmodule"
    m = re.search(regex, verilog, re.DOTALL)
    module = m.group(1)

    # create circuit
    c = Circuit(name=name)

    # handle gates
    regex = r"(or|nor|and|nand|not|xor|xnor)\s+\S+\s*\((.+?)\);"
    for gate, net_str in re.findall(regex, module, re.DOTALL):
        # parse all nets
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        c.add(nets[0], gate, fanin=nets[1:])

    # handle seq
    for st in seq_types:
        # find matching insts
        regex = rf"{st['name']}\s+[^\s(]+\s*\((.+?)\);"
        for io in re.findall(regex, module, re.DOTALL):
            # find matching pins
            pins = {}
            for typ, name in st["io"].items():
                regex = rf".{name}\s*\((.+?)\)"
                n = re.findall(regex, io, re.DOTALL)[0]
                pins[typ] = n

            c.add(
                pins.get("q", None),
                st["type"],
                fanin=pins.get("d", None),
                clk=pins.get("clk", None),
                r=pins.get("r", None),
                s=pins.get("s", None),
            )

    # handle assign statements (with help from pyeda)
    assign_regex = r"assign\s+(.+?)\s*=\s*(.+?);"
    for dest, expr in re.findall(assign_regex, module, re.DOTALL):
        parse_ast(boolexpr.parse(expr), c, dest)

    for n in c:
        if "type" not in c.graph.nodes[n]:
            if n == "1'b0":
                c.add(n, "0")
            elif n == "1'b1":
                c.add(n, "1")
            else:
                c.add(n, "input")

    # get outputs
    out_regex = r"output\s(.+?);"
    for net_str in re.findall(out_regex, module, re.DOTALL):
        nets = net_str.replace(" ", "").replace("\n", "").replace("\t", "").split(",")
        for n in nets:
            c.add(n, "output", fanin=n)

    return c


def parse_ast(ast, g, dest, level=0):
    if ast[0] == "var":
        return ast[1][0]
    else:
        if level == 0:
            fanin = [parse_ast(a, g, dest, level + 1) for a in ast[1:]]
            g.add(dest, ast[0], fanin=fanin)
        else:
            fanin = [parse_ast(a, g, dest, level + 1) for a in ast[1:]]
            name = f"{ast[0]}_{'_'.join(fanin)}"
            g.add(name, ast[0], fanin=fanin)
            return name


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
        elif c.type(n) in ["output"]:
            name = n.replace("output[", "")[:-1]
            if c.fanin(n).pop() != name:
                insts.append(f"assign {name} = {c.fanin(n).pop()}")
            outputs.append(name)
        elif c.type(n) in ["ff", "lat"]:
            wires.append(n)

            # get template
            for s in seq_types:
                if s["type"] == c.type(n):
                    seq = s
                    defs.add(s["def"])
                    break

            # connect
            io = []
            if f"d[{n}]" in c:
                d = c.fanin(f"d[{n}]").pop()
                io.append(f".{seq['io']['d']}({d})")
            if f"r[{n}]" in c:
                r = c.fanin(f"r[{n}]").pop()
                io.append(f".{seq['io']['r']}({r})")
            if f"s[{n}]" in c:
                s = c.fanin(f"s[{n}]").pop()
                io.append(f".{seq['io']['s']}({s})")
            if f"clk[{n}]" in c:
                clk = c.fanin(f"clk[{n}]").pop()
                io.append(f".{seq['io']['clk']}({clk})")
            io.append(f".{seq['io']['q']}({n})")
            insts.append(f"{s['name']} g_{n} ({','.join(io)})")

        elif c.type(n) in ["clk", "d", "r", "s"]:
            pass
        else:
            print(f"unknown gate type: {c.type(n)}")
            return

    verilog = f"module {c.name} (" + ",".join(inputs + outputs) + ");\n"
    verilog += "".join(f"input {inp};\n" for inp in inputs)
    verilog += "".join(f"output {out};\n" for out in outputs)
    verilog += "".join(f"wire {wire};\n" for wire in wires)
    verilog += "".join(f"{inst};\n" for inst in insts)
    verilog += "endmodule\n"
    verilog += "\n".join(defs)

    return verilog
