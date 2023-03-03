"""
Functions for analysis of Boolean and circuit properties.

Examples
--------
>>> import circuitgraph as cg
>>> c = cg.Circuit()
>>> c.add("i0", "input")
'i0'
>>> c.add("i1", "input")
'i1'
>>> c.add("g0", "or", fanin=["i0", "i1"])
'g0'
>>> c.add("g1", "not", fanin=["g0"])
'g1'
>>> cg.props.signal_probability(c, "g0", approx=False)
0.75
>>> cg.props.signal_probability(c, "g1", approx=False)
0.25

"""
from pathlib import Path

import circuitgraph as cg


def influence(c, ns, supergates=False, approx=True, log_dir=None, **kwargs):
    """
    Compute the influences at node(s).

    Parameters
    ----------
    c : Circuit
            Circuit to compute influence for.
    ns : str or list of str
            Node(s) to compute influence for.
    supergates : bool
            If True, break computation into supergates.
    approx : bool
            Compute approximate model count using approxmc.
    log_dir: str or pathlib.Path
            Directory to store approxmc logs in.
    kwargs: Keyword arguments
            Keyword arguments to pass into `approx_model_count`.

    Returns
    -------
    dict of str:float or dict of dict of str:float
            The influence each startpoint has on the node. If multiple nodes
            are specified, a dict mapping each output to its influences.

    """
    if isinstance(ns, str):
        ns = [ns]

    if supergates:
        # Keep track of influences already computed for a given supergate
        # Mapping of supergate outputs to dict mapping inputs to influences
        sg_influences = {}

    all_influences = {}
    for n in ns:
        sp = c.startpoints(n)

        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(exist_ok=True)

        def mc(circuit, startpoint, endpoints=None):
            i = cg.tx.sensitization_transform(circuit, startpoint, endpoints)
            if approx:
                log_file = None
                if log_dir:
                    log_file = log_dir / f"{s}.approxmc.log"
                    count = cg.sat.approx_model_count(
                        i,
                        {"sat": True},
                        log_file=log_file,
                        **kwargs,
                    )
                else:
                    count = cg.sat.approx_model_count(
                        i,
                        {"sat": True},
                        **kwargs,
                    )
            else:
                count = cg.sat.model_count(i, {"sat": True})
            return count

        influences = {}

        if supergates:
            # Mapping of circuit inputs to the supergates they belong to
            input_map = {}
            c_n = cg.tx.subcircuit(c, c.transitive_fanin(n) | {n})
            c_n.set_output(c_n.outputs(), False)
            c_n.set_output(n)
            supergates = cg.tx.supergates(c_n)
            for sg in supergates:
                # Mapping of supergate inputs to influence on supergate output
                (sg_out,) = sg.outputs()
                if sg_out not in sg_influences:
                    curr_influences = {}
                    for s in sg.startpoints():
                        input_map[s] = sg_out
                        curr_influences[s] = mc(sg, s) / (2 ** len(sg.startpoints()))
                    sg_influences[sg_out] = curr_influences
                else:
                    for s in sg.startpoints():
                        input_map[s] = sg_out

            # Multiply influences along each path
            for s in sp:
                infl = 1
                curr_node = s
                while curr_node != n:
                    sg_out = input_map[curr_node]
                    infl *= sg_influences[sg_out][curr_node]
                    curr_node = sg_out
                influences[s] = infl
        else:
            for s in sp:
                # create influence circuit
                influences[s] = mc(c, s, n) / (2 ** len(sp))

        all_influences[n] = influences

    if len(all_influences) == 1:
        (all_influences,) = all_influences.values()
    return all_influences


def avg_sensitivity(c, ns, supergates=False, approx=True, log_dir=None, **kwargs):
    """
    Calculate the average sensitivity node(s) `ns`.

    Return the average sensitivity (equal to total influence) of node(s) with
    respect to startpoints.

    Parameters
    ----------
    c: Circuit
            Circuit to compute average sensitivity for.
    ns : str or list of str
            Node(s) to compute average sensitivity for.
    supergates: bool
            If True, break the sensitivity computation up into supergates.
    approx : bool
            Compute approximate model count using approxmc.
    log_dir: str or pathlib.Path
            Directory to store approxmc logs in.
    kwargs: Keyword arguments
            Keyword arguments to pass into `approx_model_count`.

    Returns
    -------
    float or dict of str:float
            Average sensitivity of node `ns` or dict mapping nodes in set `ns`
            to average sensitivities.

    """
    all_influences = influence(
        c, ns, supergates=supergates, approx=approx, log_dir=log_dir, **kwargs
    )

    if isinstance(ns, str):
        return sum(all_influences.values())

    total_influences = {}
    for k, v in all_influences.items():
        total_influences[k] = sum(v.values())
    return total_influences


def sensitivity(c, n):
    """
    Calculate the sensitivity of node `n` with respect to its startpoints.

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
    Find an input that sensitizes `n` to an endpoint under assumptions.

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


def signal_probability(c, n, approx=True, **kwargs):
    """
    Determine the (approximate) probability of node `n` being true.

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
    kwargs: Keyword arguments
            Keyword arguments to pass into `approx_model_count`.

    Returns
    -------
    float
            Probability.

    """
    # get subcircuit ending at node
    subc = cg.tx.subcircuit(c, {n} | c.transitive_fanin(n))

    # get count with node true and other inputs fixed
    if approx:
        count = cg.sat.approx_model_count(subc, {n: True}, **kwargs)
    else:
        count = cg.sat.model_count(subc, {n: True})

    return count / (2 ** len(subc.startpoints()))


def levelize(c):
    """
    Levelize a circuit.

    Compute the logical level of each gate in the circuit.

    Parameters
    ----------
    c: Circuit
            Input circuit.

    Returns
    -------
    dict of str:int
            Mapping of gate names to levels.
    """
    if c.is_cyclic():
        raise ValueError("Cannot levelize cyclic circuit")

    levels = {n: 0 for n in c.inputs() | c.filter_type(("0", "1", "x"))}
    for n in c.topo_sort():
        if n in levels:
            continue
        levels[n] = max(levels[fi] for fi in c.fanin(n)) + 1
    return levels
