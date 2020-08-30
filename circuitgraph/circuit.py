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

    def edges(self):
        """
        Returns circuit edges

        Returns
        -------
        networkx.EdgeView
                Edges in circuit

        """
        return set(self.graph.edges)

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
        if n[0] in "0123456789":
            raise ValueError(f"cannot add node starting with int: {n}")

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

    def extend(self, c, mapping=None):
        """
        Adds nodes from another circuit

        Parameters
        ----------
        c : Circuit
                Other circuit
        """
        if mapping is None:
            self.graph.update(c.graph)
        else:
            import circuitgraph.transform as tr

            cr = tr.relabel(c, mapping)
            self.graph.update(cr.graph)

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

    def transitive_fanin(
        self, ns, stopat_types=["ff", "lat"], stopat_nodes=[], gates=None
    ):
        """
        Computes the transitive fanin of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanin for.
        stopat_types : iterable of str
                Node types to stop recursion at.
        stopat_nodes : iterable of str
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
                    if self.type(p) not in stopat_types and p not in stopat_nodes:
                        self.transitive_fanin(p, stopat_types, stopat_nodes, gates)
        return gates

    def transitive_fanout(
        self, ns, stopat_types=["ff", "lat"], stopat_nodes=[], gates=None
    ):
        """
        Computes the transitive fanout of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanout for.
        stopat_types : iterable of str
                Node types to stop recursion at.
        stopat_nodes : iterable of str
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
                    if self.type(s) not in stopat_types and s not in stopat_nodes:
                        self.transitive_fanout(s, stopat_types, stopat_nodes, gates)
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
        if self.output(n) or not self.fanout(n):
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

    def set_r(self, ns, r):
        """
        Sets sequential element's reset connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to set reset for.
        r : str
                Node(s) to use as reset.
        """
        if isinstance(ns, str):
            self.graph.nodes[ns]["r"] = r
        else:
            for n in ns:
                self.set_r(n, r)

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

    def set_s(self, ns, s):
        """
        Sets sequential element's set connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to set set for.
        s : str
                Node(s) to use as set.
        """
        if isinstance(ns, str):
            self.graph.nodes[ns]["s"] = s
        else:
            for n in ns:
                self.set_s(n, s)

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

    def set_clk(self, ns, clk):
        """
        Sets sequential element's clk connection

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to set clk for.
        clk : str
                Node(s) to use as clk.
        """
        if isinstance(ns, str):
            self.graph.nodes[ns]["clk"] = clk
        else:
            for n in ns:
                self.set_clk(n, clk)

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
        if isinstance(ns, str):
            ns = [ns]

        circuit_startpoints = self.inputs() | self.seq()
        if ns:
            non_start = set(ns) - circuit_startpoints
            return (set(ns) | self.transitive_fanin(non_start)) & circuit_startpoints
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
        if isinstance(ns, str):
            ns = [ns]

        circuit_endpoints = self.outputs() | set(self.d(self.seq()))
        if ns:
            return (set(ns) | self.transitive_fanout(ns)) & circuit_endpoints
        else:
            return circuit_endpoints

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
            nx.find_cycle(g)
            return True
        except NetworkXNoCycle:
            pass
        return False
