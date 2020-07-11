"""
Python package `circuitgraph` provides a data structure
for the generation, manipulation, and evaluation of
Boolean circuits. The circuits are represented in a graph
format based on the `networkx` package.
"""
import re
import code
import tempfile
import networkx as nx
from pysat.formula import CNF,IDPool
from pysat.solvers import Cadical
from subprocess import PIPE,Popen

class Circuit:
	"""
	Class for representing circuits

	Attributes
	----------
	name : str
		Name of circuit.
	graph : networkx.DiGraph
		Graph data structure.
	"""

	def __init__(self,verilog=None,path=None,name=None,graph=None):
		"""
		Parameters
		----------
		verilog : str
			Verilog string to be parsed.
		path : str
			Path to verilog file to be parsed.
		name : str
			Name of circuit, must match verilog module name.
		graph : networkx.DiGraph
			Graph data structure to be used in new instance.

		"""

		if name:
			self.name = name
		elif path:
			self.name = path.split('/')[-1].replace('.v','')
		else:
			self.name = 'circuit'

		if verilog or path:
			self.graph = self.parseModule(verilog,path)
		elif graph:
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

	def relabel(self,mapping):
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
		return Circuit(graph=nx.relabel_nodes(self.graph,mapping),name=name)

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

	def seqGraph(self):
		"""
		Creates a graph of the circuit's sequential elements

		Returns
		-------
		networkx.DiGraph
			Sequential graph.

		"""
		graph = nx.DiGraph()

		# add nodes
		for n in self.io()|self.seq():
			graph.add_node(n,gate=self.type(n))

		# add edges
		for n in graph.nodes:
			graph.add_edges_from((s,n) for s in self.startpoints(n))

		return graph

	def sat(self,true=None,false=None):
		"""
		Trys to find satisfying assignment, with optional assumptions

		Parameters
		----------
		true : iterable of str
			Nodes to assume True.
		false : iterable of str
			Nodes to assume False.

		Returns
		-------
		False or dict of str:bool
			Result.
		"""
		solver,clauses,variables = self.solver(true,false)
		if solver.solve():
			model = solver.get_model()
			return {n:model[variables.id(n)-1]>0 for n in self.nodes()}
		else:
			return False

	def solver(self,true=None,false=None):
		"""
		Trys to find satisfying assignment, with optional assumptions

		Parameters
		----------
		true : iterable of str
			Nodes to assume True.
		false : iterable of str
			Nodes to assume False.

		Returns
		-------
		False or dict of str:bool
			Result.
		"""
		if true is None: true = set()
		if false is None: false = set()
		clauses,variables = self.cnf()
		for n in true: clauses.append([variables.id(n)])
		for n in false: clauses.append([-variables.id(n)])
		solver = Cadical(bootstrap_with=clauses)
		return solver,clauses,variables

	def cnf(self):
		variables = IDPool()
		clauses = CNF()

		for n in self.nodes():
			variables.id(n)
			if self.type(n) == 'and':
				for f in self.fanin(n):
					clauses.append([-variables.id(n),variables.id(f)])
				clauses.append([variables.id(n)] + [-variables.id(f) for f in self.fanin(n)])
			elif self.type(n) == 'nand':
				for f in self.fanin(n):
					clauses.append([variables.id(n),variables.id(f)])
				clauses.append([-variables.id(n)] + [-variables.id(f) for f in self.fanin(n)])
			elif self.type(n) == 'or':
				for f in self.fanin(n):
					clauses.append([variables.id(n),-variables.id(f)])
				clauses.append([-variables.id(n)] + [variables.id(f) for f in self.fanin(n)])
			elif self.type(n) == 'nor':
				for f in self.fanin(n):
					clauses.append([-variables.id(n),-variables.id(f)])
				clauses.append([variables.id(n)] + [variables.id(f) for f in self.fanin(n)])
			elif self.type(n) == 'not':
				f = self.fanin(n).pop()
				clauses.append([variables.id(n),variables.id(f)])
				clauses.append([-variables.id(n),-variables.id(f)])
			elif self.type(n) in ['output','d','r','buf','clk']:
				f = self.fanin(n).pop()
				clauses.append([variables.id(n),-variables.id(f)])
				clauses.append([-variables.id(n),variables.id(f)])
			elif self.type(n) in ['xor','xnor']:
				# break into heirarchical xors
				nets = list(self.fanin(n))

				# xor gen
				def xorClauses(a,b,c):
					clauses.append([-variables.id(c),-variables.id(b),-variables.id(a)])
					clauses.append([-variables.id(c),variables.id(b),variables.id(a)])
					clauses.append([variables.id(c),-variables.id(b),variables.id(a)])
					clauses.append([variables.id(c),variables.id(b),-variables.id(a)])

				while len(nets)>2:
					#create new net
					new_net = 'xor_'+nets[-2]+'_'+nets[-1]
					variables.id(new_net)

					# add sub xors
					xorClauses(nets[-2],nets[-1],new_net)

					# remove last 2 nets
					nets = nets[:-2]

					# insert before out
					nets.insert(0,new_net)

				# add final xor
				if self.type(n) == 'xor':
					xorClauses(nets[-2],nets[-1],n)
				else:
					# invert xor
					variables.id(f'xor_inv_{n}')
					xorClauses(nets[-2],nets[-1],f'xor_inv_{n}')
					clauses.append([variables.id(n),variables.id(f'xor_inv_{n}')])
					clauses.append([-variables.id(n),-variables.id(f'xor_inv_{n}')])
			elif self.type(n) == '0':
				clauses.append([-variables.id(n)])
			elif self.type(n) == '1':
				clauses.append([variables.id(n)])
			elif self.type(n) in ['ff','lat','input']:
				pass
			else:
				print(f"unknown gate type: {self.type(n)}")
				code.interact(local=dict(globals(), **locals()))

		return clauses,variables

	def verilog(self):
		inputs = []
		outputs = []
		insts = []
		wires = []

		for n in self.nodes():
			if c.type(n) in ['xor','xnor','buf','not','nor','or','and','nand']:
				fanin = ','.join(p for p in c.fanin(n))
				insts.append(f"{c.type(n)} g_{n} ({n},{fanin})")
				wires.append(n)
			elif c.type(n) in ['0','1']:
				insts.append(f"assign {n} = 1'b{c.type()}")
			elif c.type(n) in ['input']:
				inputs.append(n)
				wires.append(n)
			elif c.type(n) in ['output']:
				outputs.append(n.replace('output[','')[:-1])
			elif c.type(n) in ['ff']:
				d = c.fanin(f'd[{n}]').pop()
				clk = c.fanin(f'clk[{n}]').pop()
				insts.append(f"fflopd g_{n} (.CK({clk}),.D({d}),.Q({n}))")
			elif c.type(n) in ['lat']:
				d = c.fanin(f'd[{n}]').pop()
				clk = c.fanin(f'clk[{n}]').pop()
				r = c.fanin(f'r[{n}]').pop()
				insts.append(f"latchdrs g_{n} (.ENA({clk}),.D({d}),.R({r}),.S(1'b1),.Q({n}))")
			elif c.type(n) in ['clk','d','r']:
				pass
			else:
				print(f"unknown gate type: {c.type(n)}")
				return

		verilog = f"module {c.name} ("+','.join(inputs+outputs)+');\n'
		verilog += ''.join(f'input {inp};\n' for inp in inputs)
		verilog += ''.join(f'output {out};\n' for out in outputs)
		verilog += ''.join(f'wire {wire};\n' for wire in wires)
		verilog += ''.join(f'{inst};\n' for inst in insts)
		verilog += 'endmodule\n'

		return verilog

	def syn(self,printOutput=False):
		verilog = self.verilog()

		with tempfile.NamedTemporaryFile() as tmp:
			cmd = ['genus','-execute',f"""set_db / .library $env(GENUS_DIR)/share/synth/tutorials/tech/tutorial.lib;
					read_hdl -sv {tmp.name};
					elaborate;
					set_db syn_generic_effort high
					syn_generic;
					syn_map;
					syn_opt;
					write_hdl -generic;
					exit;"""]
			tmp.write(bytes(verilog,'ascii'))
			tmp.flush()
			#code.interact(local=dict(globals(), **locals()))

			process = Popen(cmd,stdout=PIPE,stderr=PIPE,universal_newlines=True)
			output = ''
			while True:
				line = process.stdout.readline()
				if line == '' and process.poll() is not None:
					break
				if line:
					if printOutput:
						print(line.strip())
					output += line

		regex = "(module.*endmodule)"
		m = re.search(regex,output,re.DOTALL)
		syn_verilog = m.group(1)

		c = Circuit(verilog=syn_verilog,name=self.name)
		c.name = f'{self.name}_syn'
		return c

	def two_input(self):
		two_inp_c = nx.DiGraph()

		# create nodes
		for n in self.nodes():
			two_inp_c.add_node(n)
			for a,v in c.nodes[n].items():
				two_inp_c.nodes[n][a] = v

		# connect nodes
		for n in self.nodes():
			# handle fanin
			pred = list(c.predecessors(n))

			# select new gate type
			if c.nodes[n]['type'] in ['and','nand']:
				t = 'and'
			elif c.nodes[n]['type'] in ['or','nor']:
				t = 'or'
			elif c.nodes[n]['type'] in ['xor','xnor']:
				t = 'xor'

			while len(pred)>2:
				# create new, connect
				two_inp_c.add_node(f'{n}_add_{len(pred)}',output=False,gate=t)
				two_inp_c.add_edges_from((p,f'{n}_add_{len(pred)}') for p in pred[0:2])

				# update list
				pred.append(f'{n}_add_{len(pred)}')
				pred = pred[2:]

			# add final input connections
			two_inp_c.add_edges_from((p,n) for p in pred)

			# ensure all are two inputs
			for n in two_inp_c.nodes():
				if two_inp_c.in_degree(n)>2:
					print(f"gate with more than 2 inputs")
					code.interact(local=dict(globals(), **locals()))

		return two_inp_c

	def ternary(self):
		d = deepcopy(c)

		# add dual nodes
		for n in c:
			if c.nodes[n]['type'] in ['and','nand']:
				d.add_node(f'{n}_x',gate='and',output=c.nodes[n]['output'])
				d.add_node(f'{n}_x_in_fi',gate='or',output=False)
				d.add_node(f'{n}_0_not_in_fi',gate='nor',output=False)
				d.add_edges_from([(f'{n}_x_in_fi',f'{n}_x'),(f'{n}_0_not_in_fi',f'{n}_x')])
				d.add_edges_from((f'{p}_x',f'{n}_x_in_fi') for p in c.predecessors(n))
				for p in c.predecessors(n):
					d.add_node(f'{p}_is_0',gate='nor',output=False)
					d.add_edge(f'{p}_is_0',f'{n}_0_not_in_fi')
					d.add_edge(f'{p}_x',f'{p}_is_0')
					d.add_edge(p,f'{p}_is_0')

			elif c.nodes[n]['type'] in ['or','nor']:
				d.add_node(f'{n}_x',gate='and',output=c.nodes[n]['output'])
				d.add_node(f'{n}_x_in_fi',gate='or',output=False)
				d.add_node(f'{n}_1_not_in_fi',gate='nor',output=False)
				d.add_edges_from([(f'{n}_x_in_fi',f'{n}_x'),(f'{n}_1_not_in_fi',f'{n}_x')])
				d.add_edges_from((f'{p}_x',f'{n}_x_in_fi') for p in c.predecessors(n))
				for p in c.predecessors(n):
					d.add_node(f'{p}_is_1',gate='and',output=False)
					d.add_edge(f'{p}_is_1',f'{n}_1_not_in_fi')
					d.add_node(f'{p}_not_x',gate='not',output=False)
					d.add_edge(f'{p}_x',f'{p}_not_x')
					d.add_edge(f'{p}_not_x',f'{p}_is_1')
					d.add_edge(p,f'{p}_is_1')

			elif c.nodes[n]['type'] in ['buf','not']:
				d.add_node(f'{n}_x',gate='buf',output=c.nodes[n]['output'])
				p = list(c.predecessors(n))[0]
				d.add_edge(f'{p}_x',f'{n}_x')

			elif c.nodes[n]['type'] in ['xor','xnor']:
				d.add_node(f'{n}_x',gate='or',output=c.nodes[n]['output'])
				d.add_edges_from((f'{p}_x',f'{n}_x') for p in c.predecessors(n))

			elif c.nodes[n]['type'] in ['0','1']:
				d.add_node(f'{n}_x',gate='0',output=c.nodes[n]['output'])

			elif c.nodes[n]['type'] in ['input']:
				d.add_node(f'{n}_x',gate='input',output=c.nodes[n]['output'])

			elif c.nodes[n]['type'] in ['dff']:
				d.add_node(f'{n}_x',gate='dff',output=c.nodes[n]['output'],clk=c.nodes[n]['clk'])
				p = list(c.predecessors(n))[0]
				d.add_edge(f'{p}_x',f'{n}_x')

			elif c.nodes[n]['type'] in ['lat']:
				d.add_node(f'{n}_x',gate='lat',output=c.nodes[n]['output'],clk=c.nodes[n]['clk'],rst=c.nodes[n]['rst'])
				p = list(c.predecessors(n))[0]
				d.add_edge(f'{p}_x',f'{n}_x')

			else:
				print(f"unknown gate type: {c.nodes[n]['type']}")
				code.interact(local=locals())

		for n in d:
			if 'type' not in d.nodes[n]:
				print(f"empty gate type: {n}")
				code.interact(local=locals())

		return d

	def parseModule(self,verilog,path):
		# read verilog
		if path:
			with open(path, 'r') as f:
				verilog = f.read()

		# find module
		regex = f"module\s+{self.name}\s*\(.*?\);(.*?)endmodule"
		m = re.search(regex,verilog,re.DOTALL)
		module =  m.group(1)

		# create graph
		G = nx.DiGraph()

		# handle gates
		regex = "(or|nor|and|nand|not|xor|xnor)\s+\S+\s*\((.+?)\);"
		for gate, net_str in re.findall(regex,module,re.DOTALL):

			# parse all nets
			nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
			output = nets[0]
			inputs = nets[1:]

			# add to graph
			G.add_edges_from((net,output) for net in inputs)
			G.nodes[output]['type'] = gate

		# handle ffs
		regex = "fflopd\s+\S+\s*\(\.CK\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((.+?)\)\);"
		for clk,d,q in re.findall(regex,module,re.DOTALL):

			# add to graph
			G.add_node(q,type='ff')

			G.add_edge(d,f'd[{q}]')
			G.nodes[f'd[{q}]']['type'] = 'd'
			G.add_edge(f'd[{q}]',q)

			G.add_edge(clk,f'clk[{q}]')
			G.nodes[f'clk[{q}]']['type'] = 'clk'
			G.add_edge(f'clk[{q}]',q)

		# handle lats
		regex = "latchdrs\s+\S+\s*\(\s*\.R\s*\((.+?)\),\s*\.S\s*\((.+?)\),\s*\.ENA\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((.+?)\)\s*\);"
		for r,s,c,d,q in re.findall(regex,module,re.DOTALL):

			# add to graph
			G.add_node(q,type='lat')

			G.add_edge(d,f'd[{q}]')
			G.nodes[f'd[{q}]']['type'] = 'd'
			G.add_edge(f'd[{q}]',q)

			G.add_edge(clk,f'clk[{q}]')
			G.nodes[f'clk[{q}]']['type'] = 'clk'
			G.add_edge(f'clk[{q}]',q)

			G.add_edge(d,f'r[{q}]')
			G.nodes[f'r[{q}]']['type'] = 'r'
			G.add_edge(f'r[{q}]',q)

		# handle assigns
		assign_regex = "assign\s+(.+?)\s*=\s*(.+?);"
		for n0, n1 in re.findall(assign_regex,module):
			output = n0.replace(' ','')
			inpt = n1.replace(' ','')
			G.add_edge(inpt,output)
			G.nodes[output]['type'] = 'buf'

		for n in G.nodes():
			if 'type' not in G.nodes[n]:
				if n == "1'b0":
					G.nodes[n]['type'] = '0'
				elif n == "1'b1":
					G.nodes[n]['type'] = '1'
				else:
					G.nodes[n]['type'] = 'input'

		# get outputs
		out_regex = "output\s(.+?);"
		for net_str in re.findall(out_regex,module,re.DOTALL):
			nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
			for net in nets:
				G.add_edge(net,f'output[{net}]')
				G.nodes[f'output[{net}]']['type'] = 'output'

		return G

	def miter(self,c=None,inputs=None,outputs=None):
		if not c:
			c = self
		if not inputs:
			inputs = self.startpoints()
		if not outputs:
			outputs = self.endpoints()

		# get inputs to be used in miter
		common_inputs = self.startpoints()&inputs
		common_outputs = self.endpoints()&outputs

		# create miter
		m = c.relabel({n:f'c0_{n}' for n in c.nodes()-common_inputs})
		m.extend(self.relabel({n:f'c1_{n}' for n in c.nodes()-common_inputs}))

		# compare outputs
		m.add('sat','or')
		for o in common_outputs:
			m.add(f'miter_{o}','xor',fanin=[f'c0_{o}',f'c1_{o}'],fanout=['sat'])

		return m

	def unroll(self,cycles):
		pass


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

