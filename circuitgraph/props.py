"""Functions for analysis of Boolean and circuit properties."""
from pathlib import Path

import circuitgraph as cg


def avg_sensitivity(
    c,
    n,
    supergates=False,
    approx=True,
    e=0.9,
    d=0.1,
    seed=None,
    use_xor_clauses=False,
    log_dir=None,
):
    """
    Calculates the average sensitivity (equal to total influence) of node n
    with respect to its startpoints.

    Parameters
    ----------
    c: Circuit
            Circuit to compute average sensitivity for.
    n : str
            Node to compute average sensitivity for.
    supergates: bool
            If True, break the sensitivity computation up into supergates.
    approx : bool
            Compute approximate model count using approxmc.
    e : float (>0)
            epsilon of approxmc.
    d : float (0-1)
            delta of approxmc.
    seed: int
            Seed for approxmc.
    use_xor_clauses: bool
            Use xor clauses variable for approxmc.
    log_dir: str
            Directory to store approxmc logs in.

    Returns
    -------
    float
            Average sensitivity of node n.

    """
    sp = c.startpoints(n)

    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(exist_ok=True)
    else:
        log_file = None

    def mc(circuit, startpoint, endpoints=None):
        i = cg.tx.sensitization_transform(circuit, startpoint, endpoints)
        if approx:
            log_file = None
            if log_dir:
                log_file = log_dir / f"{s}.approxmc.log"
            count = cg.sat.approx_model_count(
                i,
                {"sat": True},
                e=e,
                d=d,
                seed=seed,
                use_xor_clauses=use_xor_clauses,
                log_file=log_file,
            )
        else:
            count = cg.sat.model_count(i, {"sat": True})
        return count

    if supergates:
        # Mapping of circuit inputs to the supergates they belong to
        input_map = {}
        # Mapping of supergates to supergate influences
        influences = {}
        c_n = cg.tx.subcircuit(c, c.transitive_fanin(n) | {n})
        supergates = cg.tx.supergates(c_n)
        for sg in supergates:
            # Mapping of supergate inputs to influence on supergate output
            sg_influences = {}
            for s in sg.startpoints():
                input_map[s] = sg
                sg_influences[s] = mc(sg, s) / (2 ** len(sg.startpoints()))
            influences[sg] = sg_influences

        # Multiply influences along each path
        for i in sp:
            infl = 1
            curr_node = i
            while curr_node != n:
                sg = input_map[curr_node]
                infl *= influences[sg][curr_node]
                curr_node = sg.outputs().pop()
            print(i, infl)

        return

    avg_sen = 0
    for s in sp:
        # create influence circuit
        i = cg.tx.sensitization_transform(c, s, n)

        # compute influence
        if approx:
            if log_dir:
                log_file = log_dir / f"{s}.approxmc.log"
            mc = cg.sat.approx_model_count(
                i,
                {"sat": True},
                e=e,
                d=d,
                seed=seed,
                use_xor_clauses=use_xor_clauses,
                log_file=log_file,
            )
        else:
            mc = cg.sat.model_count(i, {"sat": True})
        infl = mc / (2 ** len(sp))
        avg_sen += infl

    return avg_sen


def sensitivity(c, n):
    """
    Calculates the sensitivity of node n with respect to its startpoints.

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
    s = cg.tx.sensitivity_transform(c, n)
    vs = cg.utils.int_to_bin(sen, cg.utils.clog2(len(sp)), True)
    while not cg.sat.solve(s, {f"sen_out_{i}": v for i, v in enumerate(vs)}):
        sen -= 1
        vs = cg.utils.int_to_bin(sen, cg.utils.clog2(len(sp)), True)

    return sen


def sensitize(c, n, assumptions=None):
    """
    Finds an input that sensitizes n to an endpoint under assumptions.

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
    s = cg.tx.sensitization_transform(c, n)

    if not assumptions:
        assumptions = {}

    # find a sensitizing input
    result = cg.sat.solve(s, {"sat": True, **assumptions})
    if not result:
        return None
    return {g: result[g] for g in s.startpoints()}


def signal_probability(
    c, n, approx=True, e=0.9, d=0.1, seed=None, use_xor_clauses=False, log_file=None
):
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
    seed: int
            seed for approxmc.
    use_xor_clauses: bool
            Use xor clauses variable for approxmc.
    log_file: str
            Log file for approxmc.

    Returns
    -------
    float
            Probability.

    """
    # get subcircuit ending at node
    subc = cg.tx.subcircuit(c, {n} | c.transitive_fanin(n))

    # get count with node true and other inputs fixed
    if approx:
        count = cg.sat.approx_model_count(
            subc,
            {n: True},
            e=e,
            d=d,
            seed=seed,
            use_xor_clauses=use_xor_clauses,
            log_file=log_file,
        )
    else:
        count = cg.sat.model_count(subc, {n: True})

    return count / (2 ** len(subc.startpoints()))
