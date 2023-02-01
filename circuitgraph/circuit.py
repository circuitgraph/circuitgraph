"""
Class for circuit graphs.

The Circuit class can be constructed from a generic gate-level Verilog file or
existing graph. Each node in the graph represents a logic gate and has an associated
name and gate type. The supported types are:

- Standard input-order-independent gates:
    ['and', 'nand', 'or', 'nor', 'not', 'buf', 'xor', 'xnor']
- IO and Constant values:
    ['input', '1', '0', 'x']
- Blackbox IO (must be added through `add_blackbox`)
    ['bb_output', 'bb_input']

Additionally, a node can be marked as an output node.

Examples
--------
Create an empty circuit.

>>> import circuitgraph as cg
>>> c = cg.Circuit()

Add circuit inputs

>>> c.add('i0', 'input')
'i0'
>>> c.add('i1', 'input')
'i1'

Add an AND gate named 'g0'.

>>> c.add('g0', 'and')
'g0'

Connect the inputs to the AND gate.

>>> c.connect('i0', 'g0')
>>> c.connect('i1', 'g0')
>>> c.fanin('g0') == {'i0', 'i1'}
True

Or, make connections when adding nodes.

>>> c.add('g1', 'or', fanin=['i0', 'i1'])
'g1'

Nodes can marked as outputs.

>>> c.set_output('g1')
>>> c.add('g2', 'nor', fanin=['g0', 'g1'], output=True)
'g2'
>>> c.outputs() == {'g1', 'g2'}
True

Another way to create the circuit is through a file.

>>> c = cg.from_file('path/to/circuit.v') # doctest: +SKIP

Non-primitve gates can be added using blackboxes. References to blackboxes
are stored in `Circuit` objects and are represented in the circuit graph
through `bb_input` and `bb_output` types. `bb_input` nodes are like buffers:
they can be driven by a single driver. Each `bb_output` must be connected to a
single `buf` node.

>>> c = cg.Circuit()
>>> c.add("i0", "input")
'i0'
>>> c.add("i1", "input")
'i1'
>>> c.add("s", "input")
's'
>>> c.add("o", "buf", output=True)
'o'

Define the blackboxes for a mux.

>>> bb = cg.BlackBox("mux", inputs=["in_0", "in_1", "sel_0"], outputs=["out"])

Add the blackbox to the circuit. Specify how blackbox inputs/outputs connect
to circuit nodes.

>>> c.add_blackbox(bb, "mux_i", {"in_0": "i0", "in_1": "i1", "sel_0": "s", "out": "o"})
>>> set(c.blackboxes)
{'mux_i'}

`bb_input` and `bb_output` nodes get added to the graph and connected.

>>> c.type("mux_i.in_0")
'bb_input'
>>> c.type("mux_i.out")
'bb_output'
>>> c.fanin("mux_i.in_0")
{'i0'}
>>> c.fanout("mux_i.out")
{'o'}

Blackboxes can then be replaced with `Circuit` objects.

>>> m = cg.Circuit("mux")
>>> inputs = [m.add("in_0", "input"), m.add("in_1", "input")]
>>> sels = [m.add("sel_0", "input"), m.add("not_sel_0", "not", fanin="sel_0")]
>>> ands = [
...     m.add("and_0", "and", fanin=[sels[0], inputs[0]]),
...     m.add("and_1", "and", fanin=[sels[1], inputs[1]])
... ]
>>> m.add("out", "or", output=True, fanin=ands)
'out'
>>> c.fill_blackbox("mux_i", m)

Mux nodes get added to the circuit

>>> c.type("mux_i_sel_0")
'buf'
>>> c.type("mux_i_and_0")
'and'
>>> c.fanout("mux_i_out")
{'o'}

Blackboxes can also be used for sequential elements.

>>> flop = BlackBox("flop", ["clk", "d"], ["q"])

Files containing instanations of flops can still be parsed as long as the
instantiations use dot notation for ports, e.g.,
`flop flop_i(.clk(clk), .d(data_in), .q(data_out));`
by passing the blackbox into `from_file`
>>> c = cg.from_file("/path/to/file.v", blackboxes=[flop]) # doctest: +SKIP

"""
from functools import reduce
from itertools import combinations, product

import networkx as nx

primitive_gates = [
    "buf",
    "and",
    "or",
    "xor",
    "not",
    "nand",
    "nor",
    "xnor",
]

addable_types = primitive_gates + [
    "0",
    "1",
    "x",
    "input",
]

supported_types = addable_types + ["bb_input", "bb_output"]


class Circuit:
    """Class for representing circuits."""

    def __init__(self, name=None, graph=None, blackboxes=None):
        """
        Create a new `Circuit`.

        Parameters
        ----------
        name : str
                Name of circuit.
        graph : networkx.DiGraph
                Graph data structure to be used in new instance.
        blackboxes : dict of str:BlackBox
                Record of blackboxes, mapping instsance name to BlackBox type

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
        """Check if a node is in the circuit."""
        return self.graph.__contains__(n)

    def __len__(self):
        """Count the number of nodes in the circuit."""
        return self.graph.__len__()

    def __iter__(self):
        """Iterate through the nodes in the circuit."""
        return self.graph.__iter__()

    def copy(self):
        """
        Return a copy of the circuit.

        Returns
        -------
        Circuit:
                Copy of the circuit.

        """
        return Circuit(
            graph=self.graph.copy(), name=self.name, blackboxes=self.blackboxes.copy()
        )

    def set_type(self, ns, t):
        """
        Set the type of a node or nodes.

        Parameters
        ----------
        ns : str or iterable of str
                Node.
        t : str
                Type.

        """
        if t not in addable_types:
            raise ValueError(f"unsupported type {t}")

        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            self.graph.nodes[n]["type"] = t

    def type(self, ns):
        """
        Return node(s) type(s).

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

        >>> import circuitgraph as cg
        >>> c = cg.Circuit()
        >>> c.add(f'g0', 'xor')
        'g0'
        >>> c.add(f'g1', 'or')
        'g1'
        >>> c.add(f'g2', 'xor')
        'g2'


        Calling `type` for a single gate returns a single type

        >>> c.type('g0')
        'xor'

        Calling `type` on an iterable returns a set of types

        >>> c.type(['g0', 'g1', 'g2'])
        ['xor', 'or', 'xor']

        """
        if isinstance(ns, str):
            if ns in self.graph.nodes:
                try:
                    return self.graph.nodes[ns]["type"]
                except KeyError as e:
                    raise KeyError(f"Node {ns} does not have a type defined.") from e
            else:
                raise KeyError(f"Node {ns} does not exist.")

        return [self.type(n) for n in ns]

    def filter_type(self, types):
        """
        Return circuit nodes filtering by type.

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

        >>> import circuitgraph as cg
        >>> c = cg.Circuit()
        >>> c.add(f'g0', 'xor')
        'g0'
        >>> c.add(f'g1', 'or')
        'g1'
        >>> c.add(f'g2', 'xor')
        'g2'

        Calling `nodes` with no argument returns all nodes in the circuit

        >>> c.nodes() == {'g0', 'g1', 'g2'}
        True

        Passing a node type, we can selectively return nodes.

        >>> c.filter_type('xor') == {'g2', 'g0'}
        True

        """
        if isinstance(types, str):
            types = [types]

        for t in types:
            if t not in supported_types:
                raise ValueError(f"type {t} not supported.")

        return {n for n in self.graph.nodes if self.graph.nodes[n]["type"] in types}

    def add_subcircuit(self, sc, name, connections=None, strip_io=True):
        """
        Add a subcircuit to circuit.

        Parameters
        ----------
        sc : Circuit
                Circuit to add.
        name : str
                Instance name.
        connections : dict of str:str
                Optional connections to make, where the keys are subcircuit
                inputs/outputs and the values are circuit nodes.
        strip_io: bool
                If True, subcircuit inputs will be set to buffers, and subcircuit
                outputs will be marked as non-outputs.

        """
        # check if subcircuit bbs exist
        for bb_name in sc.blackboxes:
            if f"{name}_{bb_name}" in self.blackboxes:
                raise ValueError(f"blackbox {name}_{bb_name} already exists.")

        # check for name overlaps
        mapping = {}
        for n in sc:
            if f"{name}_{n}" in self.graph.nodes:
                raise ValueError(f"name {n} overlaps with {name} subcircuit.")
            mapping[n] = f"{name}_{n}"

        # check connections
        sc_inputs = sc.inputs()
        sc_outputs = sc.outputs()
        if connections:
            for sc_n, ns in connections.items():
                if sc_n not in sc_inputs and sc_n not in sc_outputs:
                    raise ValueError(f"node {sc_n} not in {name} io")

        # add sub circuit
        g = nx.relabel_nodes(sc.graph, mapping)
        self.graph.update(g)
        if strip_io:
            for n in sc.inputs():
                self.set_type(f"{name}_{n}", "buf")
            for n in sc.outputs():
                self.set_output(f"{name}_{n}", False)

        # add blackboxes
        for bb_name, bb in sc.blackboxes.items():
            self.blackboxes[f"{name}_{bb_name}"] = bb

        # make connections
        if connections:
            for sc_n, ns in connections.items():
                if sc_n in sc_inputs:
                    self.connect(ns, f"{name}_{sc_n}")
                elif sc_n in sc_outputs:
                    self.connect(f"{name}_{sc_n}", ns)

    def add_blackbox(self, blackbox, name, connections=None):
        """
        Add a blackbox instance to circuit.

        Parameters
        ----------
        blackbox : BlackBox
                Blackbox.
        name : str
                Instance name.
        connections : dict of str:str
                Optional connections to make. Mapping from blackbox
                inputs/outputs to circuit nodes.

        """
        # check if exists
        if name in self.blackboxes:
            raise ValueError(f"blackbox {name} already exists.")

        # save info
        self.blackboxes[name] = blackbox

        # make nodes
        io = []
        for n in blackbox.inputs():
            io += [self.add(f"{name}.{n}", "bb_input")]
        for n in blackbox.outputs():
            io += [self.add(f"{name}.{n}", "bb_output")]

        # make connections
        if connections:
            for bb_n, ns in connections.items():
                if bb_n in blackbox.inputs():
                    self.connect(ns, f"{name}.{bb_n}")
                elif bb_n in blackbox.outputs():
                    self.connect(f"{name}.{bb_n}", ns)
                else:
                    raise ValueError(f"node {bb_n} not defined for blackbox {name}")

    def fill_blackbox(self, name, c):
        """
        Replace a blackbox with a circuit.

        Parameters
        ----------
        name : str
                The name of the blackbox to replace.
        c : Circuit
                The circuit.

        """
        # check if bb exists
        if name not in self.blackboxes:
            raise ValueError(f"blackbox {name} does not exist.")

        # check if subcircuit bbs exist
        for bb_name in c.blackboxes:
            if f"{name}_{bb_name}" in self.blackboxes:
                raise ValueError(f"blackbox {name}_{bb_name} already exists.")

        # check if io match
        if c.inputs() != self.blackboxes[name].inputs():
            raise ValueError(f"circuit inputs do not match {name} blackbox.")
        if c.outputs() != self.blackboxes[name].outputs():
            raise ValueError(f"circuit outputs do not match {name} blackbox.")

        # check for name overlaps
        mapping = {}
        for n in c:
            if f"{name}_{n}" in self.graph.nodes:
                raise ValueError(f"name overlap with {name} blackbox.")
            mapping[n] = f"{name}_{n}"

        # rename blackbox io
        self.relabel({f"{name}.{n}": f"{name}_{n}" for n in self.blackboxes[name].io()})

        # extend circuit
        g = nx.relabel_nodes(c.graph, mapping)
        self.graph.update(g)
        for n in self.blackboxes[name].inputs():
            self.set_type(f"{name}_{n}", "buf")
        for n in self.blackboxes[name].outputs():
            self.set_output(f"{name}_{n}", False)

        # remove blackbox
        self.blackboxes.pop(name)

        # add subcircuit blackboxes
        for bb_name, bb in c.blackboxes.items():
            self.blackboxes[f"{name}_{bb_name}"] = bb

    def nodes(self):
        """
        Return circuit nodes.

        Returns
        -------
        set of str
                Nodes

        """
        return set(self.graph.nodes)

    def edges(self):
        """
        Return circuit edges.

        Returns
        -------
        set of tuple of str, str
                Edges in circuit

        """
        return set(self.graph.edges)

    def add(
        self,
        n,
        node_type,
        fanin=None,
        fanout=None,
        output=False,
        add_connected_nodes=False,
        allow_redefinition=False,
        uid=False,
    ):
        """
        Add a new node to the circuit, optionally connecting it.

        Parameters
        ----------
        n : str
                New node name
        node_type : str
                New node type
        fanin : iterable of str
                Nodes to add to new node's fanin
        fanout : iterable of str
                Nodes to add to new node's fanout
        output: bool
                If True, the node is added as an output
        add_connected_nodes: bool
                If True, nodes in the fanin/fanout will be added to the
                circuit as buffers if not already present. Useful when
                parsing circuits.
        allow_redefinition: bool
                If True, calling add with a node `n` that is already in the circuit
                with `uid` set to False will just update the node type, fanin, fanout,
                and output properties of the node. If False, a ValueError will be
                raised.
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
        >>> c.add('a', 'or')
        'a'

        In the above example the function returns the name of the new node.
        This allows us to quickly generate an AND tree with the following
        syntax.

        >>> c.add('g', 'and', fanin=[c.add(f'i{i}', 'input') for i in range(4)])
        'g'
        >>> c.fanin('g') == {'i0', 'i1', 'i2', 'i3'}
        True

        """
        # clean arguments
        if uid:
            n = self.uid(n)
        elif n in self and not allow_redefinition:
            raise ValueError(f"Node '{n}' already in circuit")
        if fanin is None:
            fanin = []
        elif isinstance(fanin, str):
            fanin = [fanin]
        if fanout is None:
            fanout = []
        elif isinstance(fanout, str):
            fanout = [fanout]

        if node_type not in supported_types:
            raise ValueError(f"Cannot add unknown type '{node_type}'")

        # raise error for invalid inputs
        if len(fanin) > 1 and node_type in ["buf", "not"]:
            raise ValueError(f"{node_type} cannot have more than one fanin")
        if fanin and node_type in ["0", "1", "x", "input"]:
            raise ValueError(f"{node_type} cannot have fanin")
        if n[0] in "0123456789":
            raise ValueError(f"cannot add node starting with int: {n}")

        # add node
        self.graph.add_node(n, type=node_type, output=output)

        # connect
        if add_connected_nodes:
            for f in fanin + fanout:
                if f not in self:
                    self.add(f, "buf")
        self.connect(n, fanout)
        self.connect(fanin, n)

        return n

    def remove(self, ns):
        """
        Remove node(s).

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
        Rename nodes of a circuit in place.

        Parameters
        ----------
        mapping : dict of str:str
                mapping of old to new names

        """
        nx.relabel_nodes(self.graph, mapping, copy=False)

    def connect(self, us, vs):
        """
        Add connections to the graph.

        Parameters
        ----------
        us : str or iterable of str
                Head node(s)
        vs : str or iterable of str
                Tail node(s)

        """
        # clean
        if not us or not vs:
            return

        if isinstance(us, str):
            us = [us]
        if isinstance(vs, str):
            vs = [vs]

        # check existence
        for n in us:
            if n not in self.graph:
                raise ValueError(f"node '{n}' does not exist.")
        for n in vs:
            if n not in self.graph:
                raise ValueError(f"node '{n}' does not exist.")

        # check for illegal connections
        for v in vs:
            t = self.type(v)
            if t in ["input", "0", "1", "x", "bb_output"]:
                raise ValueError(f"cannot connect to {t} '{v}'")
            if t in ["bb_input", "buf", "not"]:
                if len(self.fanin(v)) + len(us) > 1:
                    raise ValueError(f"fanin of {t} '{v}' cannot be greater than 1.")
        for u in us:
            t = self.type(u)
            if t in ["bb_input"]:
                raise ValueError(f"cannot connect from {t} '{u}'.")
            if t in ["bb_output"]:
                for v in vs:
                    if self.type(v) != "buf":
                        raise ValueError(
                            f"cannot connect from {t} '{u}' to non-buf '{v}'"
                        )
                if len(self.fanout(u)) + len(vs) > 1:
                    raise ValueError(f"fanout of {t} '{u}' cannot be greater than 1.")

        # connect
        self.graph.add_edges_from((u, v) for u in us for v in vs)

    def disconnect(self, us, vs):
        """
        Remove connections to the graph.

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
        Compute the fanin of a node.

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
        >>> import circuitgraph as cg
        >>> c = cg.from_lib("c17")
        >>> c.fanin('N23') == {'N16', 'N19'}
        True
        >>> c.fanin(['N10','N19']) == {'N1', 'N3', 'N7', 'N11'}
        True

        """
        gates = set()
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            gates |= set(self.graph.predecessors(n))
        return gates

    def fanout(self, ns):
        """
        Compute the fanout of a node.

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
        Compute the transitive fanin of a node.

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
        Compute the transitive fanout of a node.

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

    def fanout_depth(self, ns, maximum=True):
        """
        Compute the combinational fanout depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.
        maximum: bool
                If True, the maximum depth will be found. If False, the minimum depth
                will be found.

        Returns
        -------
        int
                Depth.

        """

        def visit_node(n, visited, reachable, depth):
            if n in visited:
                visited[n] = (
                    max(visited[n], depth) if maximum else min(visited[n], depth)
                )
            else:
                visited[n] = depth

            # check if all reachable fanin has been visited
            if all(fi in visited for fi in self.fanin(n) & reachable):
                for fo in self.fanout(n):
                    visited = visit_node(fo, visited, reachable, visited[n] + 1)
            return visited

        # is acyclic
        if self.is_cyclic():
            raise ValueError("Cannot compute depth of cyclic circuit")

        depth = 0

        # find reachable group and init visited
        reachable = self.transitive_fanout(ns)

        # set up visited
        if isinstance(ns, str):
            visited = {ns: depth}
        else:
            visited = {n: depth for n in ns}

        # recurse
        for f in self.fanout(ns):
            visited = visit_node(f, visited, reachable, depth + 1)

        return max(visited.values()) if maximum else min(visited.values())

    def fanin_depth(self, ns, maximum=True):
        """
        Compute the combinational fanin depth of a node(s).

        Parameters
        ----------
        ns : str or iterable of str
                Node(s) to compute depth for.
        maximum: bool
                If True, the maximum depth will be found. If False, the minimum depth
                will be found.

        Returns
        -------
        int
                Depth.

        """

        def visit_node(n, visited, reachable, depth):
            if n in visited:
                visited[n] = (
                    max(visited[n], depth) if maximum else min(visited[n], depth)
                )
            else:
                visited[n] = depth

            # check if all reachable fanin has been visited
            if all(fo in visited for fo in self.fanout(n) & reachable):
                for fi in self.fanin(n):
                    visited = visit_node(fi, visited, reachable, visited[n] + 1)
            return visited

        # is acyclic
        if self.is_cyclic():
            raise ValueError("Cannot compute depth of cyclic circuit")

        depth = 0

        # find reachable group and init visited
        reachable = self.transitive_fanin(ns)

        # set up visited
        if isinstance(ns, str):
            visited = {ns: depth}
        else:
            visited = {n: depth for n in ns}

        # recurse
        for f in self.fanin(ns):
            visited = visit_node(f, visited, reachable, depth + 1)

        return max(visited.values()) if maximum else min(visited.values())

    def paths(self, source, target, cutoff=None):
        """
        Get the paths from node u to node v.

        Parameters
        ----------
        source: str
                Source node.
        target: str
                Target node.
        cutoff: int
                Depth to stop search at

        Returns
        -------
        generator of list of str
                The paths from source to target.

        """
        return nx.all_simple_paths(self.graph, source, target, cutoff=cutoff)

    def inputs(self):
        """
        Return the circuit's inputs.

        Returns
        -------
        set of str
                Input nodes in circuit.

        """
        return self.filter_type("input")

    def is_output(self, node):
        """
        Return True if a node is an output.

        Parameters
        ----------
        ns : str
                Node.

        Returns
        -------
        bool
                Wheter or not the node is an output

        Raises
        ------
        KeyError
                If node is not in circuit.

        """
        if node in self.graph.nodes:
            try:
                return self.graph.nodes[node]["output"]
            except KeyError:
                return False
        else:
            raise KeyError(f"Node {node} does not exist.")

    def set_output(self, ns, output=True):
        """
        Set a node or nodes as an output or not an output.

        Parameters
        ----------
        node: str
                Node.
        output: bool
                Whether or not node is an output

        """
        if isinstance(ns, str):
            ns = [ns]
        for n in ns:
            self.graph.nodes[n]["output"] = output

    def outputs(self):
        """
        Return the circuit's outputs.

        Returns
        -------
        set of str
                Output nodes in circuit.

        """
        return {n for n in self.graph.nodes if self.is_output(n)}

    def io(self):
        """
        Return the circuit's io.

        Returns
        -------
        set of str
                Output and input nodes in circuit.

        """
        return self.inputs() | self.outputs()

    def startpoints(self, ns=None):
        """
        Compute the startpoints of a node, nodes, or circuit.

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
        return self.inputs() | self.filter_type("bb_output")

    def endpoints(self, ns=None):
        """
        Compute the endpoints of a node, nodes, or circuit.

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
        return self.outputs() | self.filter_type("bb_input")

    def reconvergent_fanout_nodes(self):
        """
        Get nodes that have fanout that reconverges.

        Returns
        -------
        generator of str
                A generator of nodes that have reconvergent fanout

        """
        for node in self.nodes():
            fo = self.fanout(node)
            if len(fo) > 1:
                for a, b in combinations(fo, 2):
                    if self.transitive_fanout(a) & self.transitive_fanout(b):
                        yield node
                        break

    def has_reconvergent_fanout(self):
        """
        Check if a circuit has any reconvergent fanout present.

        Returns
        -------
        bool
            Whether or not reconvergent fanout is present

        """
        try:
            next(self.reconvergent_fanout_nodes())
            return True
        except StopIteration:
            return False

    def is_cyclic(self):
        """
        Check for combinational loops in circuit.

        Returns
        -------
        bool
                Existence of cycle

        """
        return not nx.is_directed_acyclic_graph(self.graph)

    def uid(self, n, blocked=None):
        """
        Generate a unique net name based on `n`.

        Parameters
        ----------
        n : str
                Name to uniquify
        blocked : set of str
                Addtional names to block

        Returns
        -------
        str
                Unique name

        """
        if blocked is None:
            blocked = []

        if n not in self.graph and n not in blocked:
            return n
        i = 0
        while f"{n}_{i}" in self.graph or f"{n}_{i}" in blocked:
            if i < 10:
                i += 1
            else:
                i *= 7
        return f"{n}_{i}"

    def kcuts(self, n, k, computed=None):
        """
        Generate k-cuts.

        Parameters
        ----------
        n : str
                Node to compute cuts for.
        k : int
                Maximum cut width.

        Returns
        -------
        iter of str
                k-cuts.

        """
        if computed is None:
            computed = {}

        if n in computed:
            return computed[n]

        # helper function
        def merge_cut_sets(a_cuts, b_cuts):
            merged_cuts = []
            for a_cut, b_cut in product(a_cuts, b_cuts):
                merged_cut = a_cut | b_cut
                if len(merged_cut) <= k:
                    merged_cuts.append(merged_cut)
            return merged_cuts

        if self.fanin(n):
            fanin_cut_sets = [self.kcuts(f, k, computed) for f in self.fanin(n)]
            cuts = reduce(merge_cut_sets, fanin_cut_sets) + [{n}]
        else:
            cuts = [{n}]

        # add cuts
        computed[n] = cuts
        return cuts

    def topo_sort(self):
        """
        Return a generator of nodes in topologically sorted order.

        Returns
        -------
        iter of str
                Ordered node names.

        """
        return nx.topological_sort(self.graph)

    def remove_unloaded(self, inputs=False):
        """
        Remove nodes with no load until fixed point.

        Parameters
        ----------
        inputs : bool
                If True, unloaded inputs will be removed too.

        Returns
        -------
        iter of str
                Removed nodes.

        """
        unloaded = [
            n
            for n in self.graph
            if self.type(n) not in ["bb_input"]
            and not self.is_output(n)
            and not self.fanout(n)
        ]
        removed = []
        while unloaded:
            n = unloaded.pop()
            for fi in self.fanin(n):
                if not inputs and self.type(fi) in ["input", "bb_output"]:
                    continue
                if not self.is_output(fi) and len(self.fanout(fi)) == 1:
                    unloaded.append(fi)
            self.remove(n)
            removed.append(n)
        return removed


class BlackBox:
    """
    Class for representing blackboxes.

    Blackboxes can be used to represent arbitrary sub-modules such as
    sequential elements. `Circuit` objects hold references to all added
    `BlackBox` objects. They connect with the rest of the circuit as
    nodes with `bb_input` and `bb_output` types. These are the ports to
    the blackbox. `bb_input` nodes are like `buf` types: they can be
    driven by a single driver. Each `bb_output` node must be connected
    to a single `buf` node.

    """

    def __init__(self, name=None, inputs=None, outputs=None):
        """
        Create a new `BlackBox`.

        Parameters
        ----------
        name : str
                Name of blackbox.
        inputs : seq of str
                Blackbox inputs.
        outputs : seq of str
                Blackbox outputs.

        Examples
        --------
        Define a BlackBox for a flop

        >>> import circuitgraph as cg
        >>> dff = cg.BlackBox("dff", ["D", "CK"], ["Q"])

        This corresponds to a verilog module with the header:
        `module dff(input D, input CK, output Q);`

        Create an example circuit

        >>> c = cg.Circuit()
        >>> c.add("i0", "input")
        'i0'
        >>> c.add("i1", "input")
        'i1'
        >>> c.add("a", "and", fanin=["i0", "i1"])
        'a'
        >>> c.add("clock", "input")
        'clock'
        >>> c.add("data_out", "buf", output=True)
        'data_out'

        Add the BlackBox to a circuit

        >>> c.add_blackbox(dff, "dff0", {"D": "a", "CK": "clock", "Q": "data_out"})

        This corresnponds to instantiating the verilog module as such:
        `dff dff0(.D(a), .CK(clock), .Q(data_out));`

        This will add the bb_input nodes `dff0.D` and `dff0.CK`, driven by `a` and
        `clock`, and bb_output node `dff0.Q`, which drives `data_out`.

        """
        self.name = name
        self.input_set = set(inputs)
        self.output_set = set(outputs)

    def inputs(self):
        """
        Return the blackbox's inputs.

        Returns
        -------
        set of str
                Input nodes in blackbox.

        """
        return self.input_set

    def outputs(self):
        """
        Return the blackbox's outputs.

        Returns
        -------
        set of str
                Output nodes in blackbox.

        """
        return self.output_set

    def io(self):
        """
        Return the blackbox's inputs and outputs.

        Returns
        -------
        set of str
                IO nodes in blackbox.

        """
        return self.output_set | self.input_set
