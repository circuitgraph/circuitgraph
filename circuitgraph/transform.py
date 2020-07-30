"""Functions for transforming circuits"""
# TODO: this file name could change

import math
import code
from subprocess import PIPE, Popen
import subprocess
from tempfile import NamedTemporaryFile
from random import sample
import os

import networkx as nx

from circuitgraph import Circuit,clog2
from circuitgraph.io import verilog_to_circuit, circuit_to_verilog
from circuitgraph.logic import popcount


def syn(c, engine, print_output=False):
    """
    Synthesizes the circuit using Genus.

    Parameters
    ----------
    c : Circuit
            Circuit to synthesize.
    engine : str
            Synthesis tool to use ('Genus' or 'Yosys')
    print_output : bool
            Option to print synthesis log

    Returns
    -------
    Circuit
            Synthesized circuit.
    """
    verilog = circuit_to_verilog(c)

    # probably should write output to the tmp file
    with NamedTemporaryFile() as tmp:
        tmp.write(bytes(verilog, 'ascii'))
        tmp.flush()
        if engine == 'Genus':
            cmd = ['genus', '-no_gui', '-execute',
                   'set_db / .library '
                   f"{os.environ['CIRCUITGRAPH_GENUS_LIBRARY_PATH']};\n"
                   f'read_hdl -sv {tmp.name};\n'
                   'elaborate;\n'
                   'set_db syn_generic_effort high;\n'
                   'syn_generic;\n'
                   'syn_map;\n'
                   'syn_opt;\n'
                   'write_hdl -generic;\n'
                   'exit;']
            process = Popen(cmd, stdout=PIPE, stderr=PIPE,
                            universal_newlines=True)
            output = ''
            while True:
                line = process.stdout.readline()
                if line == '' and process.poll() is not None:
                    break
                if line:
                    if print_output:
                        print(line.strip())
                    output += line

        elif engine == 'Yosys':
            with NamedTemporaryFile() as tmpo:
                cmd = ['yosys', '-p',
                       f'read_verilog {tmp.name}; '
                       'proc; opt; fsm; opt; memory; opt; clean; '
                       f'write_verilog -noattr {tmpo.name}']
                subprocess.run(cmd)
                output = tmpo.read().decode('utf-8')
                if print_output:
                    print(output)

        else:
            raise ValueError('synthesis engine must be Yosys or Genus')


    return verilog_to_circuit(output, c.name)


def ternary(c):
    """
    Encodes the circuit with ternary values

    Parameters
    ----------
    c : Circuit
            Circuit to encode.

    Returns
    -------
    Circuit
            Encoded circuit.

    """
    t = c.copy()

    # add dual nodes
    for n in c:
        if c.type(n) in ['and', 'nand']:
            t.add_node(f'{n}_x', gate='and', output=c.nodes[n]['output'])
            t.add_node(f'{n}_x_in_fi', gate='or', output=False)
            t.add_node(f'{n}_0_not_in_fi', gate='nor', output=False)
            t.add_edges_from([(f'{n}_x_in_fi', f'{n}_x'),
                              (f'{n}_0_not_in_fi', f'{n}_x')])
            t.add_edges_from((f'{p}_x', f'{n}_x_in_fi')
                             for p in c.predecessors(n))
            for p in c.predecessors(n):
                t.add_node(f'{p}_is_0', gate='nor', output=False)
                t.add_edge(f'{p}_is_0', f'{n}_0_not_in_fi')
                t.add_edge(f'{p}_x', f'{p}_is_0')
                t.add_edge(p, f'{p}_is_0')

        elif c.type(n) in ['or', 'nor']:
            t.add_node(f'{n}_x', gate='and', output=c.nodes[n]['output'])
            t.add_node(f'{n}_x_in_fi', gate='or', output=False)
            t.add_node(f'{n}_1_not_in_fi', gate='nor', output=False)
            t.add_edges_from([(f'{n}_x_in_fi', f'{n}_x'),
                              (f'{n}_1_not_in_fi', f'{n}_x')])
            t.add_edges_from((f'{p}_x', f'{n}_x_in_fi')
                             for p in c.predecessors(n))
            for p in c.predecessors(n):
                t.add_node(f'{p}_is_1', gate='and', output=False)
                t.add_edge(f'{p}_is_1', f'{n}_1_not_in_fi')
                t.add_node(f'{p}_not_x', gate='not', output=False)
                t.add_edge(f'{p}_x', f'{p}_not_x')
                t.add_edge(f'{p}_not_x', f'{p}_is_1')
                t.add_edge(p, f'{p}_is_1')

        elif c.type(n) in ['buf', 'not']:
            t.add_node(f'{n}_x', gate='buf', output=c.nodes[n]['output'])
            p = list(c.predecessors(n))[0]
            t.add_edge(f'{p}_x', f'{n}_x')

        elif c.type(n) in ['xor', 'xnor']:
            t.add_node(f'{n}_x', gate='or', output=c.nodes[n]['output'])
            t.add_edges_from((f'{p}_x', f'{n}_x') for p in c.predecessors(n))

        elif c.type(n) in ['0', '1']:
            t.add_node(f'{n}_x', gate='0', output=c.nodes[n]['output'])

        elif c.type(n) in ['input']:
            t.add_node(f'{n}_x', gate='input', output=c.nodes[n]['output'])

        elif c.type(n) in ['dff']:
            t.add_node(f'{n}_x', gate='dff',
                       output=c.nodes[n]['output'], clk=c.nodes[n]['clk'])
            p = list(c.predecessors(n))[0]
            t.add_edge(f'{p}_x', f'{n}_x')

        elif c.type(n) in ['lat']:
            t.add_node(
                f'{n}_x', gate='lat', output=c.nodes[n]['output'],
                clk=c.nodes[n]['clk'], rst=c.nodes[n]['rst'])
            p = list(c.predecessors(n))[0]
            t.add_edge(f'{p}_x', f'{n}_x')

        else:
            print(f"unknown gate type: {c.nodes[n]['type']}")
            code.interact(local=dict(globals(), **locals()))

    for n in t:
        if 'type' not in t.nodes[n]:
            print(f"empty gate type: {n}")
            code.interact(local=dict(globals(), **locals()))

    return t


def miter(c0, c1=None, startpoints=None, endpoints=None):
    """
    Creates a miter circuit

    Parameters
    ----------
    c0 : Circuit
            First circuit.
    c1 : Circuit
            Optional second circuit, if None c0 is mitered with itself.
    startpoints : iterable of str
            Nodes to be tied together, must exist in both circuits.
    endpoints : iterable of str
            Nodes to be compared, must exist in both circuits.

    Returns
    -------
    Circuit
            Miter circuit.

    """
    if not c1:
        c1 = c0
    if not startpoints:
        startpoints = c0.startpoints() & c1.startpoints()
    if not endpoints:
        endpoints = c0.endpoints() & c1.endpoints()

    # create miter, relabel to avoid overlap except for common startpoints
    m = c0.relabel({n: f'c0_{n}' for n in c0.nodes()-startpoints})
    m.extend(c1.relabel({n: f'c1_{n}' for n in c1.nodes()-startpoints}))

    # compare outputs
    m.add('sat', 'or')
    for o in endpoints:
        m.add(f'miter_{o}', 'xor', fanin=[
              f'c0_{o}', f'c1_{o}'], fanout=['sat'])

    return m


def comb(c):
    """
    Creates combinational version of the circuit.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to make combinational.

    Returns
    -------
    Circuit
            Combinational circuit.

    """
    c_comb = c.copy()
    lat_model = gen_lat_model()
    ff_model = gen_ff_model()

    for lat in c.lats():
        relabeled_model = nx.relabel_nodes(
            lat_model, {n: f'{lat}_{n}' for n in lat_model})
        c_comb.extend(relabeled_model)
        c_comb.add_edges_from((f'{lat}_q', s) for s in c_comb.successors(lat))
        c_comb.add_edges_from((p, f'{lat}_d')
                              for p in c_comb.predecessors(lat))
        c_comb.add_edge(c.nodes[lat]['clk'], f'{lat}_clk')
        c_comb.add_edge(c.nodes[lat]['rst'], f'{lat}_rst')
        c_comb.remove_node(lat)

    for ff in c.ffs():
        relabeled_model = nx.relabel_nodes(
            ff_model, {n: f'{ff}_{n}' for n in ff_model})
        c_comb.extend(relabeled_model)
        c_comb.add_edges_from((f'{ff}_q', s) for s in c_comb.successors(ff))
        c_comb.add_edges_from((p, f'{ff}_d') for p in c_comb.predecessors(ff))
        c_comb.add_edge(c.nodes[ff]['clk'], f'{ff}_clk')
        c_comb.remove_node(ff)

    return c_comb


def gen_lat_model():
    lm = nx.DiGraph()
    # inputs
    lm.add_node('si', gate='buf', output=False)
    lm.add_node('d', gate='buf', output=False)
    lm.add_node('clk', gate='buf', output=False)
    lm.add_node('rst', gate='buf', output=False)
    lm.add_node('mux_out', gate='or', output=False)
    lm.add_node('mux_a0', gate='and', output=False)
    lm.add_node('mux_a1', gate='and', output=False)
    lm.add_node('clk_b', gate='not', output=False)

    # outputs
    lm.add_node('q', gate='and', output=False)
    lm.add_node('so', gate='buf', output=False)

    # cons
    lm.add_edge('q', 'so')
    lm.add_edge('rst', 'q')
    lm.add_edge('mux_out', 'q')
    lm.add_edge('mux_out', 'q')
    lm.add_edge('mux_a0', 'mux_out')
    lm.add_edge('mux_a1', 'mux_out')
    lm.add_edge('clk', 'clk_b')
    lm.add_edge('clk_b', 'mux_a0')
    lm.add_edge('clk', 'mux_a1')
    lm.add_edge('d', 'mux_a0')
    lm.add_edge('si', 'mux_a1')

    return lm


def gen_ff_model():
    fm = nx.DiGraph()
    # inputs
    fm.add_node('si', gate='buf', output=False)
    fm.add_node('d', gate='buf', output=False)
    fm.add_node('clk', gate='buf', output=False)
    fm.add_node('mux_a0', gate='and', output=False)
    fm.add_node('mux_a1', gate='and', output=False)
    fm.add_node('clk_b', gate='not', output=False)

    # outputs
    fm.add_node('q', gate='and', output=False)
    fm.add_node('so', gate='or', output=False)

    # cons
    fm.add_edge('si', 'q')
    fm.add_edge('mux_a0', 'so')
    fm.add_edge('mux_a1', 'so')
    fm.add_edge('clk', 'clk_b')
    fm.add_edge('clk_b', 'mux_a0')
    fm.add_edge('clk', 'mux_a1')
    fm.add_edge('d', 'mux_a0')
    fm.add_edge('si', 'mux_a1')

    return fm


def unroll(c, cycles):
    """
    Creates combinational unrolling of the circuit.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    cycles : int
            Number of cycles to unroll

    Returns
    -------
    Circuit
            Unrolled circuit.

    """
    u = nx.DiGraph()
    c_comb = comb(c)
    for i in range(cycles):
        c_comb_i = nx.relabel_nodes(c_comb, {n: f'{n}_{i}' for n in c_comb})
        u.extend(c_comb_i)
        if i == 0:
            # convert si to inputs
            for n in c:
                if c.nodes[n]['gate'] in ['lat', 'dff']:
                    u.nodes[f'{n}_si_{i}']['gate'] = 'input'

        else:
            # connect prev si
            for n in c:
                if c.nodes[n]['gate'] in ['lat', 'dff']:
                    u.add_edge(f'{n}_si_{i-1}', f'{n}_si_{i}')
        for n in u:
            if 'gate' not in u.nodes[n]:
                print(n)

    return u


def sensitivity(c, n):
    """
    Creates a circuit to compute sensitivity.

    Parameters
    ----------
    c : Circuit
            Sequential circuit to unroll.
    n : str
            Node to compute sensitivity at.

    Returns
    -------
    Circuit
            Sensitivity circuit.

    """

    # get fanin cone of node
    if n in c.startpoints():
        raise ValueError(f'{n} is in startpoints')

    fiNodes = c.transitive_fanin(n) | set([n])
    startpoints = c.startpoints(n)
    subCircuit = Circuit(c.graph.subgraph(fiNodes).copy())

    # convert outputs to buffers
    for o in subCircuit.outputs():
        subCircuit.graph.nodes[o]['type'] = 'buf'

    # convert startpoints to inputs
    for s in subCircuit.startpoints():
        subCircuit.graph.nodes[s]['type'] = 'input'
        subCircuit.graph.remove_edges_from(
            (p, s) for p in list(subCircuit.graph.predecessors(s)))

    # create sensitivity circuit and add first copy of subcircuit
    sensitivityCircuit = Circuit()
    sensitivityCircuit.extend(subCircuit)

    # instantiate population count

    p = popcount(len(startpoints)).strip_io()
    p = p.relabel({g:f'pop_{g}' for g in p})
    sensitivityCircuit.extend(p)
    for o in range(clog2(len(startpoints))):
        sensitivityCircuit.add(f'out_{o}', 'output',
                               fanin=f'pop_out_{o}')

    # stamp out a copies of the circuit with s inverted
    for i,s in enumerate(startpoints):
        mapping = {
            g: f'sen_{s}_{g}' for g in subCircuit
            if g not in startpoints-set([s])}
        relabeledSubCircuit = subCircuit.relabel(mapping)
        sensitivityCircuit.extend(relabeledSubCircuit)

        # connect inverted input
        sensitivityCircuit.graph.nodes[f'sen_{s}_{s}']['type'] = 'not'
        sensitivityCircuit.graph.add_edge(s, f'sen_{s}_{s}')

        # compare to first copy
        sensitivityCircuit.add(
            f'difference_{s}', 'xor', fanin=[n, f'sen_{s}_{n}'],
            fanout = f'pop_in_{i}'
        )
        sensitivityCircuit.add(
            f'difference_{s}', 'output', fanin=f'difference_{s}')

    return sensitivityCircuit


def sensitize(c, n):
    """
    Creates a circuit to sensitize a node to an endpoint.

    Parameters
    ----------
    c : Circuit
            Input circuit.
    n : str
            Node to sensitize.

    Returns
    -------
    Circuit
            Output circuit.

    """
    # get fanin/out cone of node
    nodes = c.transitive_fanin(n) | c.transitive_fanout(n) | set([n])
    subCircuit = Circuit(c.graph.subgraph(nodes).copy())

    # create miter
    m = miter(subCircuit)

    # cut and invert n in one side of miter
    m.graph.nodes[f'c1_{n}']['type'] = 'not'
    m.graph.remove_edges_from((f, f'c1_{n}') for f in m.fanin(f'c1_{n}'))
    m.graph.add_edge(f'c0_{n}', f'c1_{n}')

    return m


def mphf(w=30, n=800):
    """
    Creates a SAT-hard circuit based on the structure of minimum perfect hash
    functions.

    Parameters
    ----------
    w : int
            Input width.
    n : int
            Number of constraints.

    Returns
    -------
    Circuit
            Output circuit.

    """
    o = max(1, math.ceil(math.log2(w)))
    c = Circuit()

    # add inputs
    inputs = [c.add(f'in_{i}', 'input') for i in range(w)]

    # add constraints
    ors = []
    for ni in range(n):
        xors = [c.add(f'xor_{ni}_{oi}', 'xor', fanin=sample(inputs, 2))
                for oi in range(o)]
        ors.append(c.add(f'or_{ni}', 'or', fanin=xors))
    c.add('sat', 'and', fanin=ors)
    c.add('sat', 'output', fanin='sat')

    return c
