"""Class for circuit graphs

The Circuit class can be constructed from a generic verilog file or
existing graph. Each node in the graph represents a logic gate and has
an associated name and gate type. The supported types are:

- Standard input-order-independent gates:
    ['and','nand','or','nor','not','buf','xor','xnor']
- Inputs and Outputs:
    ['input','output']
- Constant values:
    ['1','0']
- Sequential elements and supporting types:
    ['ff','lat'] and ['d','r','s','clk']
"""

import networkx as nx
from networkx.exception import NetworkXNoCycle


class Circuit:
    """Class for representing circuits"""

    def __init__(self, graph=None, name=None):
        """
        Parameters
        ----------
        name : str
                Name of circuit.
        graph : networkx.DiGraph
                Graph data structure to be used in new instance.

        Examples
        --------
        Create an empty circuit.

        >>> import circuitgraph as cg
        >>> c = cg.Circuit()

        Add an AND gate named 'x'.

        >>> c.add('x','and')

        Add an additional nodes and connect them.

        >>> c.add('y','or',fanout='x')
        >>> c.add('z','xor',fanin=['x','y'])

        Another way to create the circuit is through a file.

        >>> c = cg.from_file('path/circuit.v')

        """
        if name:
            self.name = name
        else:
            self.name = 'circuit'

        if graph:
            self.graph = graph
        else:
            self.graph = nx.DiGraph()

    def __contains__(self, n):
        return self.graph.__contains__(n)

    def copy(self):
        return Circuit(graph=self.graph.copy(), name=self.name)

    def __len__(self):
        return self.graph.__len__()

    def __iter__(self):
        return self.graph.__iter__()

    def set_type(self, ns, t):
        """
        Returns node(s) type(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node.
        t : str
                Type.
        """
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            self.graph.nodes[n]['type'] = t

    def type(self, ns):
        """
        Returns node(s) type(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node.

        Returns
        -------
        str or set of str
                Type of node or a set of node types.

        Examples
        --------
        Create a with several gate types.

        >>> c = cg.Circuit()
        >>> for i,g in enumerate(['xor','or','xor','ff']): c.add(f'g{i}',g)

        Calling `type` for a single gate returns a single type

        >>> c.type('g0')
        {'xor'}

        Calling `type` on an iterable returns a set of types

        >>> c.type(c.nodes())
        {'xor','or','xor','ff'}

        """
        # FIXME: Throw an error if type is not yet defined
        if isinstance(ns, str):
            return self.graph.nodes[ns]['type']
        return set(self.graph.nodes[n]['type'] for n in ns)

    def nodes(self, types=None):
        """
        Returns circuit nodes, optionally filtering by type

        Parameters
        ----------
        types : str or iterable of str
                Type(s) to filter in.

        Returns
        -------
        set of str
                Nodes

        Examples
        --------
        Create a with several gate types.

        >>> c = cg.Circuit()
        >>> for i,g in enumerate(['xor','or','xor','ff']): c.add(f'g{i}',g)

        Calling `nodes` with no argument returns all nodes in the circuit

        >>> c.nodes()
        NodeView(('g0', 'g1', 'g2', 'g3', 'd[g3]', 'r[g3]', 'clk[g3]'))

        Passing a node type, we can selectively return nodes.

        >>> c.nodes('xor')
        {'g2', 'g0'}

        """
        if types is None:
            return self.graph.nodes
        else:
            if isinstance(types, str):
                types = [types]
            return set(n for n in self.nodes() if self.type(n) in types)

    def is_cyclic(self):
        """
        Checks for combinational loops in circuit

        Returns
        -------
        Bool
                Existence of cycle

        """
        g = self.graph.copy()
        g.remove_edges_from((e, s) for s in self.startpoints()
                            for e in self.endpoints())
        try:
            if nx.find_cycle(g):
                return True
        except NetworkXNoCycle:
            pass
        return False

    def edges(self):
        """
        Returns circuit edges

        Returns
        -------
        networkx.EdgeView
                Edges in circuit

        """
        return self.graph.edges

    def add(self, n, type, fanin=None, fanout=None, clk=None, r=None, s=None):
        """
        Adds a new node to the circuit, optionally connecting it

        Parameters
        ----------
        n : str
                New node name
        type : str
                New node type
        fanin : iterable of str
                Nodes to add to new node's fanin
        fanout : iterable of str
                Nodes to add to new node's fanout
        clk : str
                Clock connecttion of sequential element
        r : str
                Reset connection of sequential element
        s : str
                Set connection of sequential element

        Returns
        -------
        str
                New node name.

        Example
        -------
        Add a single node

        >>> import circuitgraph as cg
        >>> c = cg.Circuit()
        >>> c.add('a','or')
        'a'

        In the above example the function returns the name of the new node.
        This allows us to quickly generate an AND tree with the following
        syntax.

        >>> c.add('g','and',fanin=[c.add(f'in_{i}','input') for i in range(4)])
        'g'
        >>> c.fanin('g')
        {'in_1', 'in_0', 'in_3', 'in_2'}

        """
        # clean arguments
        if fanin is None:
            fanin = []
        elif isinstance(fanin, str):
            fanin = [fanin]
        if fanout is None:
            fanout = []
        elif isinstance(fanout, str):
            fanout = [fanout]

        if type in ['ff', 'lat']:
            # add auxillary nodes for sequential element
            self.graph.add_node(n, type=type)
            self.graph.add_node(f'd[{n}]', type='d')
            if r:
                self.graph.add_node(f'r[{n}]', type='r')
            if s:
                self.graph.add_node(f's[{n}]', type='s')
            self.graph.add_node(f'clk[{n}]', type='clk')

            # connect
            self.graph.add_edges_from((n, f) for f in fanout)
            self.graph.add_edge(f'd[{n}]', n)
            if r:
                self.graph.add_edge(f'r[{n}]', n)
            if clk:
                self.graph.add_edge(f'clk[{n}]', n)
            self.graph.add_edges_from(
                (f, f'd[{n}]') for f in fanin)
            if r:
                self.graph.add_edge(r, f'r[{n}]')
            if s:
                self.graph.add_edge(s, f's[{n}]')
            if clk:
                self.graph.add_edge(clk, f'clk[{n}]')
        elif type == 'output':
            self.graph.add_node(f'output[{n}]', type='output')
            self.graph.add_edges_from(
                (f, f'output[{n}]') for f in fanin)
        else:
            self.graph.add_node(n, type=type)
            self.graph.add_edges_from((n, f) for f in fanout)
            self.graph.add_edges_from((f, n) for f in fanin)

        return n

    def remove(self, ns):
        """
        Removes node(s)

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to remove.
        """
        if isinstance(ns, str):
            ns = [ns]
        self.graph.remove_nodes_from(ns)

    def extend(self, c):
        """
        Adds nodes from another circuit

        Parameters
        ----------
        c : Circuit
                Other circuit
        """
        self.graph.update(c.graph)

    def strip_io(self):
        """
        Removes outputs and converts inputs to buffers for easy instantiation.

        Parameters
        ----------
        c : Circuit
                Other circuit
        """
        g = self.graph.copy()
        g.remove_nodes_from(self.outputs())
        for i in self.inputs():
            g.nodes[i]['type'] = 'buf'

        return Circuit(graph=g, name=self.name)

    def connect(self, us, vs):
        """
        Adds connections to the graph

        Parameters
        ----------
        us : str or iterable of str
                Head node(s)
        vs : str or iterable of str
                Tail node(s)

        """
        if isinstance(us, str):
            us = [us]
        if isinstance(vs, str):
            vs = [vs]
        self.graph.add_edges_from((u, v) for u in us for v in vs)

    def disconnect(self, us, vs):
        """
        Removes connections to the graph

        Parameters
        ----------
        us : str or iterable of str
                Head node(s)
        vs : str or iterable of str
                Tail node(s)

        """
        if isinstance(us, str):
            us = [us]
        if isinstance(vs, str):
            vs = [vs]
        self.graph.remove_edges_from((u, v) for u in us for v in vs)

    def relabel(self, mapping):
        """
        Returns renamed copy of circuit.

        Parameters
        ----------
        mapping : dict of str:str
                mapping of old to new names

        Returns
        -------
        Circuit
                Relabeled circuit.

        """
        return Circuit(graph=nx.relabel_nodes(self.graph, mapping),
                       name=self.name)

    def transitive_fanout(self, ns, stopatTypes=['d'], stopatNodes=[],
                         gates=None):
        """
        Computes the transitive fanout of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanout for.
        stopatTypes : iterable of str
                Node types to stop recursion at.
        stopatNodes : iterable of str
                Nodes to stop recursion at.
        gates : set of str
                Visited nodes.

        Returns
        -------
        set of str
                Nodes in transitive fanout.

        """
        if gates is None:
            gates = set()
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            for s in self.graph.successors(n):
                if s not in gates:
                    gates.add(s)
                    if (self.type(s) not in stopatTypes
                            and s not in stopatNodes):
                        self.transitive_fanout(
                            s, stopatTypes, stopatNodes, gates)
        return gates

    def transitive_fanin(self, ns, stopatTypes=['ff', 'lat'], stopatNodes=[],
                        gates=None):
        """
        Computes the transitive fanin of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanin for.
        stopatTypes : iterable of str
                Node types to stop recursion at.
        stopatNodes : iterable of str
                Nodes to stop recursion at.
        gates : set of str
                Visited nodes.

        Returns
        -------
        set of str
                Nodes in transitive fanin.

        """

        if gates is None:
            gates = set()
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            for p in self.graph.predecessors(n):
                if p not in gates:
                    gates.add(p)
                    if (self.type(p) not in stopatTypes
                            and p not in stopatNodes):
                        self.transitive_fanin(
                            p, stopatTypes, stopatNodes, gates)
        return gates

    def fanin_comb_depth(self, ns, shortest=False, visited=None, depth=0):
        """
        Computes the combinational fanin depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.
        shortest : bool
                Selects between finding the shortest and longest paths.
        visited : set of str
                Visited nodes.
        depth : int
                Depth of current path.

        Returns
        -------
        int
                Depth.

        """
        # select between shortest and longest paths
        comp = min if shortest else max

        if not isinstance(ns, str):
            return comp(self.fanin_comb_depth(n, shortest) for n in ns)
        else:
            n = ns

        if visited is None:
            visited = set()

        if self.type(n) in ['ff', 'lat', 'input']:
            return 0

        depth += 1
        depths = set()
        visited.add(n)

        # find depth
        for f in self.fanin(n):
            if self.type(f) not in ['ff', 'lat', 'input'] and f not in visited:
                # continue recursion
                depths.add(self.fanin_comb_depth(
                    f, shortest, visited.copy(), depth))
            else:
                # add depth of endpoint or loop
                depths.add(depth)
        
        return comp(depths)

    def fanout_comb_depth(self, ns, shortest=False, visited=None, depth=0):
        """
        Computes the combinational fanout depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.
        shortest : bool
                Selects between finding the shortest and longest paths.
        visited : set of str
                Visited nodes.
        depth : int
                Depth of current path.

        Returns
        -------
        int
                Depth.

        """
        # select between shortest and longest paths
        comp = min if shortest else max

        if not isinstance(ns, str):
            return comp(self.fanout_comb_depth(n, shortest) for n in ns)
        else:
            n = ns

        if visited is None:
            visited = set()

        depth += 1
        depths = set()
        visited.add(n)
        # find depth
        for f in self.fanout(n):
            if (self.type(f) not in ['d', 'r', 's', 'clk', 'input', 'output']
                    and f not in visited):
                depths.add(self.fanout_comb_depth(
                    f, shortest, visited.copy(), depth))
            else:
                depths.add(depth)
        
        return comp(depths)

    def fanout(self, ns):
        """
        Computes the fanout of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute fanout for.

        Returns
        -------
        set of str
                Nodes in fanout.

        """

        gates = set()
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            gates |= set(self.graph.successors(n))
        return gates

    def fanin(self, ns):
        """
        Computes the fanin of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute fanin for.

        Returns
        -------
        set of str
                Nodes in fanin.

        Example
        -------
        >>> c.fanout('n_20')
        {'G17'}
        >>> c.fanout('n_11')
        {'n_12'}
        >>> c.fanout(['n_11','n_20'])
        {'n_12', 'G17'}

        """
        gates = set()
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            gates |= set(self.graph.predecessors(n))
        return gates

    def lats(self):
        """
        Returns the circuit's latches

        Returns
        -------
        set of str
                Latch nodes in circuit.

        """
        return self.nodes('lat')

    def ffs(self):
        """
        Returns the circuit's flip-flops

        Returns
        -------
        set of str
                Flip-flop nodes in circuit.

        """
        return self.nodes('ff')

    def seq(self):
        """
        Returns the circuit's sequential nodes

        Returns
        -------
        set of str
                Sequential nodes in circuit.

        """
        return self.nodes(['ff', 'lat'])

    def d(self, s):
        """
        Returns the d input of a sequential node

        Returns
        -------
        str
                D input node.

        """
        return [f for f in self.fanin(s) if self.type(f) == 'd'][0]

    def clk(self, s):
        """
        Returns the clk input of a sequential node

        Returns
        -------
        str
                Clk input node.

        """
        return [f for f in self.fanin(s) if self.type(f) == 'clk'][0]

    def r(self, s):
        """
        Returns the reset input of a sequential node

        Returns
        -------
        str
                Reset input node.

        """
        return [f for f in self.fanin(s) if self.type(f) == 'r'][0]

    def s(self, s):
        """
        Returns the set input of a sequential node

        Returns
        -------
        str
                Set input node.

        """
        return [f for f in self.fanin(s) if self.type(f) == 'r'][0]

    def inputs(self):
        """
        Returns the circuit's inputs

        Returns
        -------
        set of str
                Input nodes in circuit.

        """
        return self.nodes('input')

    def outputs(self):
        """
        Returns the circuit's outputs

        Returns
        -------
        set of str
                Output nodes in circuit.

        """
        return self.nodes('output')

    def io(self):
        """
        Returns the circuit's io

        Returns
        -------
        set of str
                Output and input nodes in circuit.

        """
        return self.nodes(['output', 'input'])

    def startpoints(self, ns=None):
        """
        Computes the startpoints of a node, nodes, or circuit.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute startpoints for.

        Returns
        -------
        set of str
                Startpoints of ns.

        """
        if ns:
            return set(n for n in self.transitive_fanin(ns)
                       if self.type(n) in ['ff', 'lat', 'input'])
        else:
            return set(n for n in self.graph
                       if self.type(n) in ['ff', 'lat', 'input'])

    def endpoints(self, ns=None):
        """
        Computes the endpoints of a node, nodes, or circuit.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute endpoints for.

        Returns
        -------
        set of str
                Endpoints of ns.

        """
        if ns:
            return set(n for n in self.transitive_fanout(ns)
                       if self.type(n) in ['d', 'output'])
        else:
            return set(n for n in self.graph
                       if self.type(n) in ['d', 'output'])

    def seq_graph(self):
        """
        Creates a graph of the circuit's sequential elements

        Returns
        -------
        networkx.DiGraph
                Sequential graph.

        """
        graph = nx.DiGraph()

        # add nodes
        for n in self.io() | self.seq():
            graph.add_node(n, gate=self.type(n))

        # add edges
        for n in graph.nodes:
            graph.add_edges_from((s, n) for s in self.startpoints(n))

        return graph


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
