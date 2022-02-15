"""Functions for executing SAT, #SAT, and approx-#SAT on circuits"""
import tempfile
import re
import subprocess
import shutil


def add_assumptions(formula, variables, assumptions):
    for n, val in assumptions.items():
        if val:
            formula.append([variables.id(n)])
        else:
            formula.append([-variables.id(n)])


def remap(clauses, offset):
    new_clauses = [[v + offset if v > 0 else v - offset for v in c] for c in clauses]
    return new_clauses


def construct_solver(c, assumptions=None, engine="cadical"):
    """
    Constructs a SAT solver instance with the given circuit and assumptions.

    Parameters
    ----------
    c : Circuit
            circuit to encode.
    assumptions : dict of str:int
            Assumptions to add to solver.

    Returns
    -------
    solver : pysat.Cadical
            SAT solver instance.
    variables : pysat.IDPool
            solver variable mapping.
    """
    try:
        from pysat.solvers import Cadical, Glucose4, Lingeling
    except ImportError:
        raise ImportError("Install 'python-sat' to use satisfiability functionality")

    formula, variables = cnf(c)
    if assumptions:
        for n in assumptions.keys():
            if n not in c:
                raise ValueError(f"Node '{n}' in assumptions is not in circuit")
        add_assumptions(formula, variables, assumptions)

    if engine == "cadical":
        solver = Cadical(bootstrap_with=formula)
    elif engine == "glucose":
        solver = Glucose4(bootstrap_with=formula, incr=True)
    elif engine == "lingeling":
        solver = Lingeling(bootstrap_with=formula)
    else:
        raise ValueError(f"unsupported solver: {engine}")
    return solver, variables


def cnf(c):
    """
    Converts circuit to CNF using the Tseitin transformation.

    Parameters
    ----------
    c : Circuit
            circuit to transform.

    Returns
    -------
    variables : pysat.IDPool
            formula variable mapping.
    formula : pysat.CNF
            CNF formula.
    """
    try:
        from pysat.formula import CNF, IDPool
    except ImportError:
        raise ImportError("Install 'python-sat' to use satisfiability functionality")
    variables = IDPool()
    formula = CNF()

    for n in c.nodes():
        variables.id(n)
        n_type = c.type(n)
        if n_type in ["and", "or", "xor"] and len(c.fanin(n)) == 1:
            n_type = "buf"
        elif n_type in ["nand", "nor", "xnor"] and len(c.fanin(n)) == 1:
            n_type = "not"

        if n_type == "and":
            for f in c.fanin(n):
                formula.append([-variables.id(n), variables.id(f)])
            formula.append([variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
        elif n_type == "nand":
            for f in c.fanin(n):
                formula.append([variables.id(n), variables.id(f)])
            formula.append([-variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
        elif n_type == "or":
            for f in c.fanin(n):
                formula.append([variables.id(n), -variables.id(f)])
            formula.append([-variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
        elif n_type == "nor":
            for f in c.fanin(n):
                formula.append([-variables.id(n), -variables.id(f)])
            formula.append([variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
        elif n_type == "not":
            if c.fanin(n):
                f = c.fanin(n).pop()
                formula.append([variables.id(n), variables.id(f)])
                formula.append([-variables.id(n), -variables.id(f)])
        elif n_type in ["buf", "bb_input"]:
            if c.fanin(n):
                f = c.fanin(n).pop()
                formula.append([variables.id(n), -variables.id(f)])
                formula.append([-variables.id(n), variables.id(f)])
        elif n_type in ["xor", "xnor"]:
            # break into hierarchical xors
            nets = list(c.fanin(n))

            # xor gen
            def xorClauses(a, b, c):
                formula.append([-variables.id(c), -variables.id(b), -variables.id(a)])
                formula.append([-variables.id(c), variables.id(b), variables.id(a)])
                formula.append([variables.id(c), -variables.id(b), variables.id(a)])
                formula.append([variables.id(c), variables.id(b), -variables.id(a)])

            while len(nets) > 2:
                # create new net
                new_net = "xor_" + nets[-2] + "_" + nets[-1]
                variables.id(new_net)

                # add sub xors
                xorClauses(nets[-2], nets[-1], new_net)

                # remove last 2 nets
                nets = nets[:-2]

                # insert before out
                nets.insert(0, new_net)

            # add final xor
            if n_type == "xor":
                xorClauses(nets[-2], nets[-1], n)
            else:
                # invert xor
                variables.id(f"xor_inv_{n}")
                xorClauses(nets[-2], nets[-1], f"xor_inv_{n}")
                formula.append([variables.id(n), variables.id(f"xor_inv_{n}")])
                formula.append([-variables.id(n), -variables.id(f"xor_inv_{n}")])
        elif n_type == "0":
            formula.append([-variables.id(n)])
        elif n_type == "1":
            formula.append([variables.id(n)])
        elif n_type in ["bb_output", "input"]:
            formula.append([variables.id(n), -variables.id(n)])
        else:
            raise ValueError(f"Unknown gate type '{n_type}'")

    return formula, variables


def solve(c, assumptions=None):
    """
    Trys to find satisfying assignment, with optional assumptions.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    assumptions : dict of str:int
            Nodes to assume True or False.

    Returns
    -------
    False or dict of str:bool
            Result.

    Example
    -------
    >>> import circuitgraph as cg
    >>> c = cg.from_lib('s27')
    >>> cg.sat.solve(c)
    {'G17': True, 'n_20': False, 'n_12': True, 'n_11': False,
     'G0': True, 'n_9': True, 'n_10': True, 'n_7': False, 'n_8': False,
     'n_1': False, 'G7': True, 'n_4': True, 'n_5': True, 'n_6': True,
     'G2': False, 'n_3': False, 'n_2': False, 'G6': True, 'G3': True,
     'n_0': False, 'G1': True, 'G5': True, 'n_21': False, 'd[G5]': True,
     'r[G5]': True, 'clk[G5]': True, 'clk': True, 'd[G6]': False,
     'r[G6]': True, 'clk[G6]': True, 'd[G7]': True, 'r[G7]': True,
     'clk[G7]': True, 'output[G17]': True}
    >>> cg.sat.solve(c, assumptions={'G17': True, 'n_20': True, 'G6': False})
    False
    """
    solver, variables = construct_solver(c, assumptions)
    if solver.solve():
        model = solver.get_model()
        return {n: model[variables.id(n) - 1] > 0 for n in c.nodes()}
    else:
        return False


def approx_model_count(
    c, assumptions=None, startpoints=None, e=0.9, d=0.1, log_file=None
):
    """
    Approximates the number of solutions to circuit.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    assumptions : dict of str:int
            Nodes to assume True or False.
    startpoints : iter of str
            Startpoints to use for approxmc.
    e : float (>0)
            epsilon of approxmc.
    d : float (0-1)
            delta of approxmc.
    log_file: str
            If specified, approxmc output will be written to this file.

    Returns
    -------
    int
            Estimate.
    """
    if shutil.which("approxmc") is None:
        raise OSError("Install 'approxmc' to use 'approx_model_count'")
    if startpoints is None:
        startpoints = c.startpoints()

    formula, variables = cnf(c)
    if assumptions:
        for n in assumptions.keys():
            if n not in c:
                raise ValueError(f"Assumption key '{n}' not node in circuit")
        add_assumptions(formula, variables, assumptions)

    # specify sampling set
    enc_inps = " ".join([str(variables.id(n)) for n in startpoints])

    # write dimacs to tmp
    with tempfile.NamedTemporaryFile(
        prefix=f"circuitgraph_approxmc_{c.name}_clauses"
    ) as tmp:
        clause_str = "\n".join(
            " ".join(str(v) for v in c) + " 0" for c in formula.clauses
        )
        dimacs = (
            f"c ind {enc_inps} 0\np cnf {formula.nv} "
            f"{len(formula.clauses)}\n{clause_str}\n"
        )
        tmp.write(bytes(dimacs, "ascii"))
        tmp.flush()

        # run approxmc
        cmd = f"approxmc --epsilon={e} --delta={d} {tmp.name}".split()
        with open(log_file, "w+") if log_file else tempfile.NamedTemporaryFile(
            prefix=f"circuitgraph_approxmc_{c.name}_log", mode="w+"
        ) as f:
            subprocess.run(cmd, stdout=f, stderr=f, check=True, universal_newlines=True)
            f.seek(0)
            result = f.read()

    # parse results
    m = re.search(r"s mc (\d+)", result)
    if not m:
        raise ValueError(f"approxmc produced unexpected result:\n\n{result}")
    return int(m.group(1))


def model_count(c, assumptions=None):
    """
    Determines the number of solutions to circuit.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    assumptions : dict of str:int
            Nodes to assume True or False.

    Returns
    -------
    int
            Count.
    """
    startpoints = c.startpoints()
    solver, variables = construct_solver(c, assumptions)
    count = 0
    while solver.solve():
        model = solver.get_model()
        solver.add_clause([-model[variables.id(n) - 1] for n in startpoints])
        count += 1

    return count
