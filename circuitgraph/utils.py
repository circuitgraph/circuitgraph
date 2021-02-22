"""Various circuit related utilities"""
from pathlib import Path
from tempfile import NamedTemporaryFile
import subprocess

from circuitgraph import supported_types
from circuitgraph.io import circuit_to_verilog


def visualize(c, output_file):
    """
    Visualize a circuit using Yosys.

    Parameters
    ----------
    c: Circuit
            Circuit to visualize.
    output_file: str
            Where to write the image to.
    """
    verilog = circuit_to_verilog(c)
    output_file = Path(output_file)
    fmt = output_file.suffix[1:]
    prefix = output_file.with_suffix("")
    with NamedTemporaryFile(
        prefix="circuitgraph_synthesis_input", suffix=".v"
    ) as tmp_in:
        tmp_in.write(bytes(verilog, "ascii"))
        tmp_in.flush()
        cmd = [
            "yosys",
            "-p",
            f"read_verilog {tmp_in.name}; " f"show -format {fmt} -prefix {prefix}",
        ]
        subprocess.run(cmd)


def clog2(num: int) -> int:
    r"""Return the ceiling log base two of an integer :math:`\ge 1`.
    This function tells you the minimum dimension of a Boolean space with at
    least N points.
    For example, here are the values of ``clog2(N)`` for :math:`1 \le N < 18`:
        >>> [clog2(n) for n in range(1, 18)]
    [0, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5]
    This function is undefined for non-positive integers:
        >>> clog2(0)
    Traceback (most recent call last):
        ...
    ValueError: expected num >= 1
    """
    if num < 1:
        raise ValueError("expected num >= 1")
    accum, shifter = 0, 1
    while num > shifter:
        shifter <<= 1
        accum += 1
    return accum


def int_to_bin(i, w, lend=False):
    """
    Converts integer to binary tuple.

    Parameters
    ----------
    i : int
            Integer to convert.
    w : int
            Width of conversion
    lend : bool
            Endianness of returned tuple, helpful for iterating.

    Returns
    -------
    tuple of bool
            Binary tuple.

    """

    if not lend:
        return tuple(v == "1" for v in bin(i)[2:].zfill(w))
    else:
        return tuple(reversed(tuple(v == "1" for v in bin(i)[2:].zfill(w))))


def bin_to_int(b, lend=False):
    """
    Converts binary number to integer.

    Parameters
    ----------
    b : tuple of bool
            Binary tuple.
    lend : bool
            Endianness of tuple.

    Returns
    -------
    int
            Value as integer.

    """

    if not lend:
        s = "".join("1" if v else "0" for v in b)
    else:
        s = "".join("1" if v else "0" for v in reversed(b))

    return int(s, 2)


def lint(c, exhaustive=False, unloaded=False, undriven=True):
    """
    Checks circuit for missing connections.

    Parameters
    ----------
    c: Circuit
            The Circuit to lint.
    """
    errors = []

    def handle(s):
        if exhaustive:
            errors.append(s)
        else:
            raise ValueError(s)

    # node types
    for g in c.nodes():
        if "type" not in c.graph.nodes[g]:
            handle(f"no type for node {g}")
        t = c.graph.nodes[g]["type"]
        if t not in supported_types:
            handle(f"node {g} has unsupported type {t}")
        if "." in g and g.split(".")[0] not in c.blackboxes:
            handle(f"node {g} has blackbox syntax with no instance")

    # incorrect connections
    for g in c.filter_type(["input", "0", "1", "bb_output"]):
        if len(c.fanin(g)) > 0:
            handle(f"{c.type(g)} {g} has fanin")
    for g in c.filter_type(["buf", "not", "output", "bb_input"]):
        if len(c.fanin(g)) > 1:
            handle(f"{c.type(g)} {g} has fanin count > 1")

    # dangling connections
    if undriven:
        for g in c.filter_type(
            [
                "buf",
                "not",
                "output",
                "bb_input",
                "and",
                "nand",
                "or",
                "nor",
                "xor",
                "xnor",
            ]
        ):
            if len(c.fanin(g)) < 1:
                handle(f"{c.type(g)} {g} has no fanin")

    if unloaded:
        for g in c.nodes() - c.outputs():
            if not c.fanout(g):
                handle(f"{c.type(g)} {g} has no fanout")

    # blackboxes
    for name, bb in c.blackboxes.items():
        for g in bb.inputs():
            if f"{name}.{g}" not in c.graph.nodes:
                handle(f"missing blackbox pin {name}.{g}")
            else:
                t = c.graph.nodes[f"{name}.{g}"]["type"]
                if t != "bb_input":
                    handle(f"blackbox pin {name}.{g} has incorrect type {t}")

        for g in bb.outputs():
            if f"{name}.{g}" not in c.graph.nodes:
                handle(f"missing blackbox pin {name}.{g}")
            else:
                t = c.graph.nodes[f"{name}.{g}"]["type"]
                if t != "bb_output":
                    handle(f"blackbox pin {name}.{g} has incorrect type {t}")

    if errors:
        raise ValueError("\n".join(errors))
