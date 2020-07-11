"""
Python package `circuitgraph` provides a data structure
for the generation, manipulation, and evaluation of
Boolean circuits. The circuits are represented in a graph
format based on the `networkx` package.
"""

import code
import networkx as nx

class Circuit:
	"""Class for representing circuits"""

	def __init__(self,graph=None,name=None):
		"""
		Parameters
		----------
		name : str
			Name of circuit.
		graph : networkx.DiGraph
			Graph data structure to be used in new instance.

		"""

		if name:
			self.name = name
		else:
			self.name = 'circuit'

		if graph:
			self.graph = graph
		else:
			self.graph = nx.DiGraph()

	def __contains__(self,n):
		return self.graph.__contains__(n)

	def __len__(self):
		return self.graph.__len__()

	def __iter__(self):
		return self.graph.__iter__()

	def type(self,n):
		"""
		Returns node type

		Parameters
		----------
		n : str
			Node.

		Returns
		-------
		str
			Type of node.

		"""
		return self.graph.nodes[n]['type']

	def nodes(self,types=None):
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

		"""
		if types is None:
			return self.graph.nodes
		else:
			if isinstance(types,str): types = [types]
			return set(n for n in self.nodes() if self.type(n) in types)

	def edges(self):
		"""
		Returns circuit edges

		Returns
		-------
		networkx.EdgeView
			Edges in circuit

		"""
		return self.graph.edges

	def add(self,n,type,fanin=None,fanout=None):
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

		"""
		if fanin is None: fanin=[]
		if fanout is None: fanout=[]
		self.graph.add_node(n,type=type)
		self.graph.add_edges_from((f,n) for f in fanin)
		self.graph.add_edges_from((n,f) for f in fanout)

	def extend(self,c):
		"""
		Adds nodes from another circuit

		Parameters
		----------
		c : Circuit
			Other circuit
		"""
		self.graph.update(c.graph)

	def connect(self,us,vs):
		"""
		Adds connections to the graph

		Parameters
		----------
		us : str or iterable of str
			Head node(s)
		vs : str or iterable of str
			Tail node(s)

		"""
		if isinstance(us,str): us = [us]
		if isinstance(vs,str): vs = [vs]
		self.graph.add_edges_from((u,v) for u in us for v in vs)

	def transitiveFanout(self,ns,stopat=['d'],gates=None):
		"""
		Computes the transitive fanout of a node.

		Parameters
		----------
		ns : str or iterable of str
			Node(s) to compute transitive fanout for.
		stopat : iterable of str
			Node types to stop recursion at.
		gates : set of str
			Visited nodes.

		Returns
		-------
		set of str
			Nodes in transitive fanout.

		"""

		if gates is None: gates=set()
		if isinstance(ns,str): ns = [ns]
		for n in ns:
			for s in self.graph.successors(n):
				if s not in gates:
					gates.add(s)
					if self.type(s) not in stopat:
						self.transitiveFanout(s,stopat,gates)
		return gates

	def transitiveFanin(self,ns,stopat=['ff','lat'],gates=None):
		"""
		Computes the transitive fanin of a node.

		Parameters
		----------
		ns : str or iterable of str
			Node(s) to compute transitive fanin for.
		stopat : iterable of str
			Node types to stop recursion at.
		gates : set of str
			Visited nodes.

		Returns
		-------
		set of str
			Nodes in transitive fanin.

		"""

		if gates is None: gates=set()
		if isinstance(ns,str): ns = [ns]
		for n in ns:
			for p in self.graph.predecessors(n):
				if p not in gates:
					gates.add(p)
					if self.type(p) not in stopat:
						self.transitiveFanin(p,stopat,gates)
		return gates

	def fanout(self,ns):
		"""
		Computes the fanout of a node.

		Parameters
		----------
		ns : str or iterable of str
			Node(s) to compute fanout for.
		gates : set of str
			Visited nodes.

		Returns
		-------
		set of str
			Nodes in fanout.

		"""

		gates = set()
		if isinstance(ns,str): ns = [ns]
		for n in ns:
			gates |= set(self.graph.successors(n))
		return gates

	def fanin(self,ns):
		"""
		Computes the fanin of a node.

		Parameters
		----------
		ns : str or iterable of str
			Node(s) to compute fanin for.
		gates : set of str
			Visited nodes.

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
		if isinstance(ns,str): ns = [ns]
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
		return self.nodes(['ff','lat'])

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
		return self.nodes(['output','input'])

	def startpoints(self,ns=None):
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
			return set(n for n in self.transitiveFanin(ns) if self.type(n) in ['ff','lat','input'])
		else:
			return set(n for n in self.graph if self.type(n) in ['ff','lat','input'])

	def endpoints(self,ns=None):
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
			return set(n for n in self.transitiveFanout(ns) if self.type(n) in ['d','output'])
		else:
			return set(n for n in self.graph if self.type(n) in ['d','output'])


def from_file(path,name=None):
	"""Creates a new CircuitGraph from a verilog file.
	If the name of the module to create a graph from is different than the
	file name, specify it using the `name` argument"""
	if name is None:
		name = file_path.split('/')[-1].replace('.v', '')
	with open(path, 'r') as f:
		data = f.read()
		regex = rf"module\s+{top}\s*\(.*?\);(.*?)endmodule"
		m = re.search(regex, data, re.DOTALL)
	return Circuit(verilog_to_graph(m.group(1), name))

def from_verilog(verilog,name=None):
	"""Creates a new CircuitGraph from a verilog string.
	If the name of the module to create a graph from is different than the
	file name, specify it using the `name` argument"""
	if name is None:
		name = 'circuit'
	return Circuit(verilog_to_graph(verilog, name))

def to_verilog(circuit):
	"""Converts a CircuitGraph to a string of verilog code"""
	return graph_to_verilog(circuit.graph)


if __name__=='__main__':
	# test class

	verilog = """
// Generated by Cadence Genus(TM) Synthesis Solution 16.22-s033_1
// Generated on: Jun 19 2020 15:25:45 EDT (Jun 19 2020 19:25:45 UTC)

// Verification Directory fv/s27

module s27(clk, G0, G1, G17, G2, G3);
  input clk, G0, G1, G2, G3;
  output G17;
  wire clk, G0, G1, G2, G3;
  wire G17;
  wire G5, G6, G7, n_0, n_1, n_2, n_3, n_4;
  wire n_5, n_6, n_7, n_8, n_9, n_10, n_11, n_12;
  wire n_20, n_21;
  fflopd DFF_0_Q_reg(.CK (clk), .D (n_12), .Q (G5));
  fflopd DFF_1_Q_reg(.CK (clk), .D (n_21), .Q (G6));
  not g543 (G17, n_20);
  not g545 (n_12, n_11);
  nand g546__7837 (n_11, G0, n_9);
  nor g548__7557 (n_10, n_7, n_8);
  nand g549__7654 (n_9, n_1, n_8);
  fflopd DFF_2_Q_reg(.CK (clk), .D (n_6), .Q (G7));
  nor g551__8867 (n_8, G7, n_4);
  not g553 (n_7, n_5);
  nor g550__1377 (n_6, G2, n_3);
  nand g554__3717 (n_5, n_2, G6);
  nand g552__4599 (n_4, G3, n_0);
  nor g555__3779 (n_3, G1, G7);
  not g557 (n_2, G0);
  not g556 (n_1, G5);
  not g558 (n_0, G1);
  nor g562__2007 (n_20, G5, n_10);
  nor g544_dup__1237 (n_21, G5, n_10);
endmodule


module fflopd(CK, D, Q);
  input CK, D;
  output Q;
  wire CK, D;
  wire Q;
  wire next_state;
  reg  qi;
  assign #1 Q = qi;
  assign next_state = D;
  always
    @(posedge CK)
      qi <= next_state;
  initial
    qi <= 1'b0;
endmodule

"""

	# parse circuit
	c = Circuit(verilog=verilog,name='s27')
	print(f'parsed: {c.name}')
	print(f'nodes: {c.nodes()}')
	print(f'edges: {c.edges()}')
	for n in c: print(f'type of {n}: {c.type(n)}')
	print(f'len: {len(c)}')
	print(f"contains: {'G1' in c}")

	# check self equivalence
	m = c.miter()
	live = m.sat()
	print(f'self live: {live}')
	equiv = m.sat(true=['sat'])
	print(f'self equiv: {not equiv}')
	#code.interact(local=dict(globals(), **locals()))

	# synthesize and check equiv
	s = c.syn(True)
	m = c.miter(s)
	live = m.sat()
	print(f'syn live: {live}')
	equiv = m.sat(true=['sat'])
	print(f'syn equiv: {not equiv}')

