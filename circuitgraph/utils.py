"""Various circuit related utilities"""


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
            Endianess of returned tuple, helpful for iterating.

    Returns
    -------
    tuple of bool
            Binary tuple.

    """

    if not lend:
        return tuple(v == "1" for v in bin(i)[2:].zfill(w))
    else:
        return tuple(reversed(tuple(v == "1" for v in bin(i)[2:].zfill(w))))


def lint(c):
    """
    Checks circuit for missing connections.

    Parameters
    ----------
    c: Circuit
            The Circuit to lint.
    """
    c.type(c.nodes())
    c.output(c.nodes())
    for g in c.nodes(types=["buf", "not"]):
        if len(c.fanin(g)) != 1:
            raise ValueError(f"buf/not {g} has incorrect fanin count")
    for g in c.nodes(types=["input", "0", "1"]):
        if len(c.fanin(g)) > 0:
            raise ValueError(f"0/1/input {g} has fanin")
    for g in c.nodes(types=["ff", "lat", "and", "nand", "or", "nor", "xor", "xnor"]):
        if len(c.fanin(g)) < 1:
            raise ValueError(f"{g} has no fanin")
    for g in c.nodes():
        if not c.fanout(g) and not c.output(g):
            raise ValueError(f"{g} has no fanout and is not output")