"""Functions for executing SAT, #SAT, and approx-#SAT on circuits"""

import tempfile
import re
import code
from subprocess import PIPE, run

from pysat.formula import CNF, IDPool
from pysat.solvers import Cadical


def interrupt(s):
    s.interrupt()


def add_assumptions(formula, variables, assumptions):
    for n, val in assumptions.items():
        if val:
            formula.append([variables.id(n)])
        else:
            formula.append([-variables.id(n)])


def remap(clauses, offset):
    new_clauses = [[v + offset if v > 0 else v - offset for v in c] for c in clauses]
    return new_clauses


def construct_solver(c, assumptions=None):
    """
    Constructs a SAT solver instance with the given circuit and assumptions

    Parameters
    ----------
    c : Circuit
            circuit to encode
    assumptions : dict of str:int
            Assumptions to add to solver

    Returns
    -------
    solver : pysat.Cadical
            SAT solver instance
    variables : pysat.IDPool
            solver variable mapping
    """
    formula, variables = cnf(c)
    if assumptions:
        add_assumptions(formula, variables, assumptions)
    solver = Cadical(bootstrap_with=formula)
    return solver, variables


def cnf(c):
    """
    Converts circuit to CNF using the Tseitin transformation

    Parameters
    ----------
    c : Circuit
            circuit to transform

    Returns
    -------
    variables : pysat.IDPool
            formula variable mapping
    formula : pysat.CNF
            CNF formula
    """
    variables = IDPool()
    formula = CNF()

    for n in c.nodes():
        variables.id(n)
        if c.type(n) == "and":
            for f in c.fanin(n):
                formula.append([-variables.id(n), variables.id(f)])
            formula.append([variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
        elif c.type(n) == "nand":
            for f in c.fanin(n):
                formula.append([variables.id(n), variables.id(f)])
            formula.append([-variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
        elif c.type(n) == "or":
            for f in c.fanin(n):
                formula.append([variables.id(n), -variables.id(f)])
            formula.append([-variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
        elif c.type(n) == "nor":
            for f in c.fanin(n):
                formula.append([-variables.id(n), -variables.id(f)])
            formula.append([variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
        elif c.type(n) == "not":
            if c.fanin(n):
                f = c.fanin(n).pop()
                formula.append([variables.id(n), variables.id(f)])
                formula.append([-variables.id(n), -variables.id(f)])
        elif c.type(n) in ["buf", "output", "bb_input"]:
            if c.fanin(n):
                f = c.fanin(n).pop()
                formula.append([variables.id(n), -variables.id(f)])
                formula.append([-variables.id(n), variables.id(f)])
        elif c.type(n) in ["xor", "xnor"]:
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
            if c.type(n) == "xor":
                xorClauses(nets[-2], nets[-1], n)
            else:
                # invert xor
                variables.id(f"xor_inv_{n}")
                xorClauses(nets[-2], nets[-1], f"xor_inv_{n}")
                formula.append([variables.id(n), variables.id(f"xor_inv_{n}")])
                formula.append([-variables.id(n), -variables.id(f"xor_inv_{n}")])
        elif c.type(n) == "0":
            formula.append([-variables.id(n)])
        elif c.type(n) == "1":
            formula.append([variables.id(n)])
        elif c.type(n) in ["bb_output", "input"]:
            formula.append([variables.id(n), -variables.id(n)])
        else:
            print(f"unknown gate type: {c.type(n)}")
            code.interact(local=dict(globals(), **locals()))

    return formula, variables


def sat(c, assumptions=None):
    """
    Trys to find satisfying assignment, with optional assumptions

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
    >>> c = cg.from_file('rtl/s27.v')
    >>> cg.sat(c)
    {'G17': True, 'n_20': False, 'n_12': True, 'n_11': False,
     'G0': True, 'n_9': True, 'n_10': True, 'n_7': False, 'n_8': False,
     'n_1': False, 'G7': True, 'n_4': True, 'n_5': True, 'n_6': True,
     'G2': False, 'n_3': False, 'n_2': False, 'G6': True, 'G3': True,
     'n_0': False, 'G1': True, 'G5': True, 'n_21': False, 'd[G5]': True,
     'r[G5]': True, 'clk[G5]': True, 'clk': True, 'd[G6]': False,
     'r[G6]': True, 'clk[G6]': True, 'd[G7]': True, 'r[G7]': True,
     'clk[G7]': True, 'output[G17]': True}
    >>> cg.sat(c,assumptions={'G17':True,'n_20':True,'G6':False})
    False

    """
    solver, variables = construct_solver(c, assumptions)
    if solver.solve():
        model = solver.get_model()
        return {n: model[variables.id(n) - 1] > 0 for n in c.nodes()}
    else:
        return False


def approx_model_count(c, assumptions=None, startpoints=None, e=0.9, d=0.1):
    """
    Approximates the number of solutions to circuit

    Parameters
    ----------
    c : Circuit
            Input circuit.
    assumptions : dict of str:int
            Nodes to assume True or False.
    startpoints : iter of str
            Startpoints to use for approxmc
    e : float (>0)
            epsilon of approxmc
    d : float (0-1)
            delta of approxmc

    Returns
    -------
    int
            Estimate.
    """

    if startpoints is None:
        startpoints = c.startpoints()

    formula, variables = cnf(c)
    add_assumptions(formula, variables, assumptions)

    # specify sampling set
    enc_inps = " ".join([str(variables.id(n)) for n in startpoints])

    # write dimacs to tmp
    with tempfile.NamedTemporaryFile() as tmp:
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
        result = run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)

    # parse results
    # approxmc version < 4
    m = re.search(r"Number of solutions is: (\d+) x 2\^(\d+)", result.stdout)
    # approxmc version 4
    if not m:
        m = re.search(r"Number of solutions is: (\d+)\*2\*\*(\d+)", result.stdout)
    if not m:
        return None
    return int(m.group(1)) * (2 ** int(m.group(2)))


def model_count(c, assumptions=None):
    """
    Determines the number of solutions to circuit

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
