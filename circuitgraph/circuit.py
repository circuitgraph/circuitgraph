"""Class for circuit graphs

The Circuit class can be constructed from a generic verilog file or
existing graph. Each node in the graph represents a logic gate and has
an associated name and gate type. The supported types are:

- Standard input-order-independent gates:
    ['and','nand','or','nor','not','buf','xor','xnor']
- Inputs and Constant values:
    ['input','1','0']
- Sequential elements:
    ['ff','lat']

Additionally, nodes have the following attributes:
- Labeling node as an output
    ['output']
- Tracking sequential element connections
    ['clk','r','s']

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
            self.name = "circuit"

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
            self.graph.nodes[n]["type"] = t

    def type(self, ns):
        """
        Returns node(s) type(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node.

        Returns
        -------
        str or list of str
                Type of node or a list of node types.

        Raises
        ------
        KeyError
                If type of queried node is not defined.

        Examples
        --------
        Create a with several gate types.

        >>> c = cg.Circuit()
        >>> for i,g in enumerate(['xor','or','xor','ff']): c.add(f'g{i}', g)

        Calling `type` for a single gate returns a single type

        >>> c.type('g0')
        {'xor'}

        Calling `type` on an iterable returns a set of types

        >>> c.type(c.nodes())
        ['xor', 'or', 'xor', 'ff']

        """
        if isinstance(ns, str):
            try:
                return self.graph.nodes[ns]["type"]
            except KeyError:
                raise KeyError(f"Node {ns} does not have a type defined.")
        return [self.type(n) for n in ns]

    def set_output(self, ns, value=True):
        """
        Sets node(s) as output.

        Parameters
        ----------
        ns : str or iterable of str
                Node.
        value : bool
                Output value.
        """
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            self.graph.nodes[n]["output"] = value

    def output(self, ns):
        """
        Returns node(s) output value.

        Parameters
        ----------
        ns : str or iterable of str
                Node.

        Returns
        -------
        str or list of str
                Type of node or a list of node output values.

        Raises
        ------
        KeyError
                If type of queried node is not defined.

        """
        if isinstance(ns, str):
            try:
                return self.graph.nodes[ns]["output"]
            except KeyError:
                raise KeyError(f"Node {ns} does not have a output defined.")
        return [self.output(n) for n in ns]

    def nodes(self, types=None, output=None):
        """
        Returns circuit nodes, optionally filtering by type

        Parameters
        ----------
        types : str or iterable of str
                Type(s) to filter in.
        output : str or iterable of str
                Attributes(s) to filter in.

        Returns
        -------
        set of str
                Nodes

        Examples
        --------
        Create a circuit with several gate types.

        >>> c = cg.Circuit()
        >>> for i,g in enumerate(['xor','or','xor','ff']): c.add(f'g{i}',g)

        Calling `nodes` with no argument returns all nodes in the circuit

        >>> c.nodes()
        {'g0', 'g1', 'g2', 'g3'}

        Passing a node type, we can selectively return nodes.

        >>> c.nodes('xor')
        {'g2', 'g0'}

        """
        if isinstance(types, str):
            types = [types]

        if types is None and output is None:
            return set(self.graph.nodes)
            # return set(n for n in self.graph.nodes)
        elif types is None:
            return set(n for n in self.nodes() if self.output(n) == output)
        elif output is None:
            return set(n for n in self.nodes() if self.type(n) in types)
        else:
            return set(
                n
                for n in self.nodes()
                if self.type(n) in types and self.output(n) == output
            )

    def is_cyclic(self):
        """
        Checks for combinational loops in circuit

        Returns
        -------
        Bool
                Existence of cycle

        """
        g = self.graph.copy()
        g.remove_edges_from(
            (e, s) for s in self.startpoints() for e in self.endpoints()
        )
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

    def add(
        self, n, type, fanin=None, fanout=None, clk=None, r=None, s=None, output=False
    ):
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
                Clock connection of sequential element
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

        # raise error for invalid inputs
        if len(fanin) > 1 and type in ["ff", "lat", "buf", "not"]:
            raise ValueError(f"{type} cannot have more than one fanin")
        if fanin and type in ["0", "1", "input"]:
            raise ValueError(f"{type} cannot have fanin")

        # add node
        self.graph.add_node(n, type=type, r=r, s=s, clk=clk, output=output)

        # connect
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
        for o in self.outputs():
            g.nodes[o]["output"] = False
        for i in self.inputs():
            g.nodes[i]["type"] = "buf"

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
        return Circuit(graph=nx.relabel_nodes(self.graph, mapping), name=self.name)

    def transitive_fanout(
        self, ns, stopatTypes=["ff", "lat"], stopatNodes=[], gates=None
    ):
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
                    if self.type(s) not in stopatTypes and s not in stopatNodes:
                        self.transitive_fanout(s, stopatTypes, stopatNodes, gates)
        return gates

    def transitive_fanin(
        self, ns, stopatTypes=["ff", "lat"], stopatNodes=[], gates=None
    ):
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
                    if self.type(p) not in stopatTypes and p not in stopatNodes:
                        self.transitive_fanin(p, stopatTypes, stopatNodes, gates)
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

        Returns
        -------
        int
                Depth.

        """
        # select comparison function
        comp = min if shortest else max

        # find depth of a group
        if not isinstance(ns, str):
            return comp(self.fanin_comb_depth(n, shortest) for n in ns)
        else:
            n = ns

        if visited is None:
            visited = set()

        depths = set()
        depth += 1

        visited.add(n)
        for f in self.fanin(n):
            if self.type(f) in ["ff", "lat", "input"] or f in visited:
                depths.add(depth)
            else:
                depths.add(self.fanin_comb_depth(f, shortest, visited.copy(), depth))

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

        Returns
        -------
        int
                Depth.

        """
        # select comparison function
        comp = min if shortest else max

        # find depth of a group
        if not isinstance(ns, str):
            return comp(self.fanout_comb_depth(n, shortest) for n in ns)
        else:
            n = ns

        if visited is None:
            visited = set()

        depths = set()
        if self.output(n):
            depths.add(depth)

        visited.add(n)
        for f in self.fanout(n):
            if self.type(f) in ["ff", "lat"] or f in visited:
                depths.add(depth)
            else:
                depths.add(
                    self.fanout_comb_depth(f, shortest, visited.copy(), depth + 1)
                )

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
        return self.nodes("lat")

    def ffs(self):
        """
        Returns the circuit's flip-flops

        Returns
        -------
        set of str
                Flip-flop nodes in circuit.

        """
        return self.nodes("ff")

    def seq(self):
        """
        Returns the circuit's sequential nodes

        Returns
        -------
        set of str
                Sequential nodes in circuit.

        """
        return self.nodes(["ff", "lat"])

    def r(self, ns):
        """
        Returns sequential element's reset connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to return reset for.

        Returns
        -------
        set of str
                Reset nodes.

        """
        if isinstance(ns, str):
            try:
                return self.graph.nodes[ns]["r"]
            except KeyError:
                raise KeyError(f"Node {ns} does not have a reset defined.")
        return [self.r(n) for n in ns]

    def s(self, ns):
        """
        Returns sequential element's set connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to return set for.

        Returns
        -------
        set of str
                Set nodes.

        """
        if isinstance(ns, str):
            try:
                return self.graph.nodes[ns]["s"]
            except KeyError:
                raise KeyError(f"Node {ns} does not have a set defined.")
        return [self.s(n) for n in ns]

    def clk(self, ns):
        """
        Returns sequential element's clk connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to return clk for.

        Returns
        -------
        set of str
                Clk nodes.

        """
        if isinstance(ns, str):
            try:
                return self.graph.nodes[ns]["clk"]
            except KeyError:
                raise KeyError(f"Node {ns} does not have a clk defined.")
        return [self.clk(n) for n in ns]

    def d(self, ns):
        """
        Returns sequential element's d connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to return d for.

        Returns
        -------
        set of str
                D nodes.

        """
        if isinstance(ns, str):
            try:
                return self.fanin(ns).pop()
            except KeyError:
                raise KeyError(f"Node {ns} does not have a d defined.")
        return [self.d(n) for n in ns]

    def inputs(self):
        """
        Returns the circuit's inputs

        Returns
        -------
        set of str
                Input nodes in circuit.

        """
        return self.nodes("input")

    def outputs(self):
        """
        Returns the circuit's outputs

        Returns
        -------
        set of str
                Output nodes in circuit.

        """
        return self.nodes(output=True)

    def io(self):
        """
        Returns the circuit's io

        Returns
        -------
        set of str
                Output and input nodes in circuit.

        """
        return self.nodes("input") | self.nodes(output=True)

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
        circuit_startpoints = self.inputs() | self.seq()
        if ns:
            return self.transitive_fanin(ns) & circuit_startpoints
        else:
            return circuit_startpoints

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
        circuit_endpoints = self.outputs() | self.seq()
        if ns:
            return self.transitive_fanout(ns) & circuit_endpoints
        else:
            return circuit_endpoints

    def comb(self):
        """
        Creates a copy of the circuit where sequential elements are removed
        from the circuit by making thier d ports outputs of the circuits and
        their q ports inputs to the circuit

        Returns
        -------
        Circuit
            The combinational circuit.
        """
        c = self.copy()
        for i in c.seq():
            c.remove(i)
            c.add(i, "input")
            c.set_output(self.fanin(i).pop())

        return c

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

    def avg_sensitivity(self,n,approx=True,e=0.9,d=0.1):
        """
        Calculates the average sensitivity (equal to total influence)
        of node n with respect to its startpoints.

        Parameters
        ----------
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
        from circuitgraph.transform import influence
        from circuitgraph.sat import approx_model_count,model_count

        sp = self.startpoints(n)

        avg_sen = 0
        for s in sp:
            # create influence circuit
            i = influence(self, n, s)

            # compute influence
            if approx:
                mc = approx_model_count(i,{'sat':True},e,d)
            else:
                mc = model_count(i,{'sat':True})
            infl = mc/(2**len(sp))
            avg_sen += infl

        return avg_sen

    def sensitivity(self,n):
        """
        Calculates the sensitivity of node n with respect
        to its startpoints.

        Parameters
        ----------
        n : str
                Node to compute sensitivity for.

        Returns
        -------
        int
                Sensitivity of node n.

        """
        from circuitgraph.transform import sensitivity
        from circuitgraph.sat import sat

        sp = self.startpoints(n)

        sen = len(sp)
        s = sensitivity(c,n)
        vs = int_to_bin(sen, clog2(len(sp)))
        while not sat(s, {f"out_{i}": v for i, v in enumerate(vs)}):
            sen -= 1
            vs = int_to_bin(sen, clog2(len(sp)))

        return sen


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


def int_to_bin(i, w):
    return tuple(v == "1" for v in bin(i)[2:].zfill(w))
