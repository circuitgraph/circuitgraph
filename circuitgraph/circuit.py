"""Class for circuit graphs

The Circuit class can be constructed from a generic Verilog file or
existing graph. Each node in the graph represents a logic gate and has
an associated name and gate type. The supported types are:

- Standard input-order-independent gates:
    ['and','nand','or','nor','not','buf','xor','xnor']
- IO and Constant values:
    ['output','input','1','0']
- Blackbox IO (must be added through `add_blackbox`)
    ['bb_output','bb_input']

"""

import networkx as nx
from networkx.exception import NetworkXNoCycle


supported_types = [
    "buf",
    "and",
    "or",
    "xor",
    "not",
    "nand",
    "nor",
    "xnor",
    "0",
    "1",
    "output",
    "input",
]


class Circuit:
    """Class for representing circuits"""

    def __init__(self, name=None, graph=None, blackboxes=None):
        """
        Parameters
        ----------
        name : str
                Name of circuit.
        graph : networkx.DiGraph
                Graph data structure to be used in new instance.
        blackboxes : dict of str
                Record of blackboxes, mapping name to type

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

        if blackboxes:
            self.blackboxes = blackboxes
        else:
            self.blackboxes = {}

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
        if t not in supported_types:
            raise ValueError(f"unsupported type {t}")

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

    def filter_type(self, types):
        """
        Returns circuit nodes filtering by type.

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
        Create a circuit with several gate types.

        >>> c = cg.Circuit()
        >>> for i,g in enumerate(['xor','or','xor','ff']): c.add(f'g{i}',g)

        Calling `nodes` with no argument returns all nodes in the circuit

        >>> c.nodes()
        {'g0', 'g1', 'g2', 'g3'}

        Passing a node type, we can selectively return nodes.

        >>> c.filter_type('xor')
        {'g2', 'g0'}

        """
        if isinstance(types, str):
            types = [types]

        return set(n for n in self.nodes() if self.type(n) in types)

    def add_subcircuit(self, sc, name, connections=None):
        """
        Adds a subcircuit to circuit.

        Parameters
        -------
        type : str
                Circuit name.
        sc : Circuit
                Circuit to add.
        name : str
                Instance name.
        connections : dict of str:str
                Optional connections to make.

        """

        # add sub circuit
        g = nx.relabel_nodes(sc.graph, {n: f"{name}_{n}" for n in sc})
        self.graph.update(g)
        for n in sc.io():
            self.set_type(f"{name}_{n}", "buf")

        # add blackboxes
        for bb_name, bb in sc.blackboxes.items():
            self.blackboxes[f"{name}_{bb_name}"] = bb

        # make connections
        if connections:
            sc_inputs = sc.inputs()
            sc_outputs = sc.outputs()
            for sc_node, node in connections.items():
                if sc_node in sc_inputs:
                    self.connect(node, f"{name}_{sc_node}")
                elif sc_node in sc_outputs:
                    self.connect(f"{name}_{sc_node}", node)
                else:
                    raise ValueError(f"node {sc_node} not in {name} io")

    def add_blackbox(self, blackbox, name, connections=None):
        """
        Adds a blackbox instance to circuit.

        Parameters
        -------
        type : str
                Circuit name.
        blackbox : BlackBox
                Blackbox.
        name : str
                Instance name.
        connections : dict of str:str
                Optional connections to make.

        """
        # make nodes
        io = []
        for n in blackbox.inputs:
            io += [self.add(f"{name}.{n}", "bb_input")]
        for n in blackbox.outputs:
            io += [self.add(f"{name}.{n}", "bb_output")]

        # save info
        self.blackboxes[name] = blackbox

        # make connections
        if connections:
            for bb_node, node in connections.items():
                if bb_node in blackbox.inputs:
                    self.connect(node, f"{name}.{bb_node}")
                elif bb_node in blackbox.outputs:
                    self.connect(f"{name}.{bb_node}", node)
                else:
                    raise ValueError(f"node {bb_node} not defined for blackbox {name}")

    def fill_blackbox(self, c, name):
        """
        Replaces blackbox with circuit.

        Parameters
        -------
        c : Circuit
                Circuit.
        name : str
                Instance name.

        """
        # rename blackbox io
        self.relabel({n: n.replace(".", "_") for n in self.blackboxes[name].io})

        # extend circuit
        g = nx.relabel_nodes(c.graph, {n: f"{name}_{n}" for n in c})
        self.graph.update(g)

    def nodes(self):
        """
        Returns circuit nodes

        Returns
        -------
        set of str
                Nodes

        """
        return set(self.graph.nodes)

    def edges(self):
        """
        Returns circuit edges

        Returns
        -------
        networkx.EdgeView
                Edges in circuit

        """
        return set(self.graph.edges)

    def add(self, n, type, fanin=None, fanout=None, uid=False):
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
        uid: bool
                If True, the node is given a unique name if it already
                exists in the circuit.

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
        if uid:
            n = self.uid(n)
        if fanin is None:
            fanin = []
        elif isinstance(fanin, str):
            fanin = [fanin]
        if fanout is None:
            fanout = []
        elif isinstance(fanout, str):
            fanout = [fanout]

        # raise error for invalid inputs
        if len(fanin) > 1 and type in ["buf", "not"]:
            raise ValueError(f"{type} cannot have more than one fanin")
        if fanin and type in ["0", "1", "input"]:
            raise ValueError(f"{type} cannot have fanin")
        if fanout and type in ["output"]:
            raise ValueError(f"{type} cannot have fanout")
        if n[0] in "0123456789":
            raise ValueError(f"cannot add node starting with int: {n}")

        # add node
        self.graph.add_node(n, type=type)

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

    def relabel(self, mapping):
        """
        Renames nodes of a circuit in-place.

        Parameters
        ----------
        mapping : dict of str:str
                mapping of old to new names

        """
        nx.relabel_nodes(self.graph, mapping, copy=False)

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

    def transitive_fanin(self, ns):
        """
        Computes the transitive fanin of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanin for.

        Returns
        -------
        set of str
                Nodes in transitive fanin.

        """

        if isinstance(ns, str):
            ns = [ns]
        gates = set()
        for n in ns:
            gates |= nx.ancestors(self.graph, n)
        return gates

    def transitive_fanout(self, ns):
        """
        Computes the transitive fanout of a node.

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute transitive fanout for.

        Returns
        -------
        set of str
                Nodes in transitive fanout.

        """
        if isinstance(ns, str):
            ns = [ns]
        gates = set()
        for n in ns:
            gates |= nx.descendants(self.graph, n)
        return gates

    def fanout_depth(self, ns, visited=None, reachable=None, depth=0):
        """
        Computes the combinational fanout depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.

        Returns
        -------
        int
                Depth.
        """
        if visited is None:
            # is acyclic
            if self.is_cyclic():
                raise ValueError(f"Cannot compute depth of cyclic circuit")

            # find reachable group and init visited
            reachable = self.transitive_fanout(ns)

            # set up visited
            if isinstance(ns, str):
                visited = {ns: 0}
            else:
                visited = {n: 0 for n in ns}

            # recurse
            for f in self.fanout(ns):
                self.fanout_depth(f, visited, reachable, depth + 1)

            return max(visited.values())

        else:
            # update node depth
            if ns in visited:
                visited[ns] = max(visited[ns], depth)
            else:
                visited[ns] = depth

            # check if all reachable fanin has been visited
            if all(n in visited for n in self.fanin(ns) & reachable):
                for f in self.fanout(ns):
                    self.fanout_depth(f, visited, reachable, visited[ns] + 1)

    def fanin_depth(self, ns, visited=None, reachable=None, depth=0):
        """
        Computes the combinational fanin depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.

        Returns
        -------
        int
                Depth.

        """
        if visited is None:
            # is acyclic
            if self.is_cyclic():
                raise ValueError(f"Cannot compute depth of cyclic circuit")

            # find reachable group and init visited
            reachable = self.transitive_fanin(ns)

            # set up visited
            if isinstance(ns, str):
                visited = {ns: 0}
            else:
                visited = {n: 0 for n in ns}

            # recurse
            for f in self.fanin(ns):
                self.fanin_depth(f, visited, reachable, depth + 1)

            return max(visited.values())

        else:
            # update node depth
            if ns in visited:
                visited[ns] = max(visited[ns], depth)
            else:
                visited[ns] = depth

            # check if all reachable fanin has been visited
            if all(n in visited for n in self.fanout(ns) & reachable):
                for f in self.fanin(ns):
                    self.fanin_depth(f, visited, reachable, visited[ns] + 1)

    def inputs(self):
        """
        Returns the circuit's inputs

        Returns
        -------
        set of str
                Input nodes in circuit.

        """
        return self.filter_type("input")

    def outputs(self):
        """
        Returns the circuit's outputs

        Returns
        -------
        set of str
                Output nodes in circuit.

        """
        return self.filter_type("output")

    def io(self):
        """
        Returns the circuit's io

        Returns
        -------
        set of str
                Output and input nodes in circuit.

        """
        return self.filter_type(["input", "output"])

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

        if ns:
            return (set(ns) | self.transitive_fanin(ns)) & self.startpoints()
        else:
            return self.inputs() | self.filter_type("bb_output")

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

        if ns:
            return (set(ns) | self.transitive_fanout(ns)) & self.endpoints()
        else:
            return self.outputs() | self.filter_type("bb_input")

    def is_cyclic(self):
        """
        Checks for combinational loops in circuit

        Returns
        -------
        bool
                Existence of cycle

        """
        return not nx.is_directed_acyclic_graph(self.graph)

    def uid(self, n):
        """
        Generates a unique net name based on input

        Returns
        -------
        str
                Unique name

        """
        if n not in self.graph:
            return n
        i = 0
        while f"{n}_{i}" in self.graph:
            i += 1
        return f"{n}_{i}"


class BlackBox:
    """Class for representing blackboxes"""

    def __init__(self, name=None, inputs=None, outputs=None):
        """
        Parameters
        ----------
        name : str
                Name of blackbox.
        inputs : seq of str
                Blackbox inputs.
        outputs : seq of str
                Blackbox outputs.

        """

        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        self.io = inputs + outputs
