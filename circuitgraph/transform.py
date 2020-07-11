"""Functions for transforming circuits"""

import re
from subprocess import PIPE,Popen
from tempfile import NamedTemporaryFile

def relabel(c,mapping):
	"""
	Returns renamed copy of circuit.

	Parameters
	----------
	c : Circuit
		Circuit to relabel.
	mapping : dict of str:str
		mapping of old to new names

	Returns
	-------
	Circuit
		Relabeled circuit.

	"""
	return Circuit(graph=nx.relabel_nodes(c.graph,mapping),name=name)

def syn(c,printOutput=False):
	"""
	Synthesizes the circuit using Genus.

	Parameters
	----------
	c : Circuit
		Circuit to synthesize.
	printOutput : bool
		Option to print synthesis log

	Returns
	-------
	Circuit
		Synthesized circuit.

	"""
	verilog = c.verilog()

	with NamedTemporaryFile() as tmp:
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

	c = Circuit(verilog=syn_verilog,name=c.name)
	c.name = f'{c.name}_syn'
	return c

def two_input(c):
	two_inp_c = nx.DiGraph()

	# create nodes
	for n in c.nodes():
		two_inp_c.add_node(n)
		for a,v in c.nodes[n].items():
			two_inp_c.nodes[n][a] = v

	# connect nodes
	for n in c.nodes():
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

def ternary(c):
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

def miter(c0,c1=None,startpoints=None,endpoints=None):
	if not c1:
		c1 = c0
	if not startpoints:
		startpoints = c0.startpoints()&c1.startpoints()
	if not endpoints:
		endpoints = c0.endpoints()&c1.endpoints()

	# create miter, relabel to avoid overlap except for common startpoints
	m = c0.relabel({n:f'c0_{n}' for n in c0.nodes()-startpoints})
	m.extend(c1.relabel({n:f'c1_{n}' for n in c1.nodes()-startpoints}))

	# compare outputs
	m.add('sat','or')
	for o in common_outputs:
		m.add(f'miter_{o}','xor',fanin=[f'c0_{o}',f'c1_{o}'],fanout=['sat'])

	return m

def unroll(c,cycles):
	pass

def sensitivity(c,endpoint):
	pass

def sensitize(c,ns):
	pass

def seqGraph(c):
	"""
	Creates a graph of the circuit's sequential elements

	Returns
	-------
	networkx.DiGraph
		Sequential graph.

	"""
	graph = nx.DiGraph()

	# add nodes
	for n in c.io()|c.seq():
		graph.add_node(n,gate=c.type(n))

	# add edges
	for n in graph.nodes:
		graph.add_edges_from((s,n) for s in c.startpoints(n))

	return graph

