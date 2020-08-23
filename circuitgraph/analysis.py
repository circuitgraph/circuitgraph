from circuitgraph.transform import sensitivity, influence
from circuitgraph.sat import sat, approx_model_count, model_count
from circuitgraph.utils import clog2, int_to_bin


def avg_sensitivity(c, n, approx=True, e=0.9, d=0.1):
    """
    Calculates the average sensitivity (equal to total influence)
    of node n with respect to its startpoints.

    Parameters
    ----------
    c: Circuit
            Circuit to compute average sensitivy for.
    n : str
            Node to compute average sensitivity for.
    approx : bool
            Use approximate solver
    e : float (>0)
            epsilon of approxmc
    d : float (0-1)
            delta of approxmc

    Returns
    -------
    float
            Average sensitivity of node n.
    """
    sp = c.startpoints(n)

    avg_sen = 0
    for s in sp:
        # create influence circuit
        i = influence(c, n, s)

        # compute influence
        if approx:
            mc = approx_model_count(i, {"sat": True}, e=e, d=d)
        else:
            mc = model_count(i, {"sat": True})
        infl = mc / (2 ** len(sp))
        avg_sen += infl

    return avg_sen


def sensitivity(c, n):
    """
    Calculates the sensitivity of node n with respect
    to its startpoints.

    Parameters
    ----------
    c: Circuit
            Circuit to compute sensitivity for
    n : str
            Node to compute sensitivity for.

    Returns
    -------
    int
            Sensitivity of node n.
    """
    sp = c.startpoints(n)

    sen = len(sp)
    s = sensitivity(c, n)
    vs = int_to_bin(sen, clog2(len(sp)), True)
    while not sat(s, {f"out_{i}": v for i, v in enumerate(vs)}):
        sen -= 1
        vs = int_to_bin(sen, clog2(len(sp)), True)

    return sen
