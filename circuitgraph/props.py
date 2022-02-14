"""Functions for analysis of Boolean and circuit properties"""
from circuitgraph.tx import sensitivity_transform, sensitization_transform, subcircuit
from circuitgraph.sat import solve, approx_model_count, model_count
from circuitgraph.utils import clog2, int_to_bin


def avg_sensitivity(c, n, approx=True, e=0.9, d=0.1):
    """
    Calculates the average sensitivity (equal to total influence)
    of node n with respect to its startpoints.

    Parameters
    ----------
    c: Circuit
            Circuit to compute average sensitivity for.
    n : str
            Node to compute average sensitivity for.
    approx : bool
            Compute approximate model count using approxmc.
    e : float (>0)
            epsilon of approxmc.
    d : float (0-1)
            delta of approxmc.

    Returns
    -------
    float
            Average sensitivity of node n.
    """
    sp = c.startpoints(n)

    avg_sen = 0
    for s in sp:
        # create influence circuit
        i = sensitization_transform(c, s, n)

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
    if n in sp:
        return 1

    sen = len(sp)
    s = sensitivity_transform(c, n)
    vs = int_to_bin(sen, clog2(len(sp)), True)
    while not solve(s, {f"sen_out_{i}": v for i, v in enumerate(vs)}):
        sen -= 1
        vs = int_to_bin(sen, clog2(len(sp)), True)

    return sen


def sensitize(c, n, assumptions={}):
    """
    Finds an input that sensitizes n to an endpoint
    under assumptions.

    Parameters
    ----------
    c: Circuit
            Circuit to compute sensitivity for
    n : str
            Node to compute sensitivity for.
    assumptions : dict of str:bool
            Assumptions for Circuit.

    Returns
    -------
    dict of str:bool
            Input value.
    """
    # setup circuit
    s = sensitization_transform(c, n)

    # find a sensitizing input
    result = solve(s, {"sat": True, **assumptions})
    if not result:
        return None
    return {g: result[g] for g in s.startpoints()}


def signal_probability(c, n, approx=True, e=0.9, d=0.1, log_file=None):
    """
    Determines the (approximate) probability of a node being true over all
    startpoint combinations.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    n : str
            Node to determine probability for.
    approx : bool
            Use approximate model counting through approxmc.
            This is the default behavior, and turned it off
            can make computation time prohibitively expensive.
    e : float (>0)
            epsilon of approxmc.
    d : float (0-1)
            delta of approxmc.
    log_file: str
            Log file for approxmc.

    Returns
    -------
    float
            Probability.
    """
    # get startpoints not in node fanin
    non_fanin_startpoints = c.startpoints() - c.startpoints(n)

    # get subcircuit ending at node
    subc = subcircuit(c, {n} | c.transitive_fanin(n))

    # get count with node true and other inputs fixed
    if approx:
        count = approx_model_count(subc, {n: True}, e=e, d=d, log_file=log_file)
    else:
        count = model_count(subc, {n: True})

    return count / (2 ** len(subc.startpoints()))
