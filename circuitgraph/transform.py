"""Functions for transforming circuits"""

from circuitgraph import Circuit
from circuitgraph.io import verilog_to_circuit
from subprocess import PIPE,Popen
from tempfile import NamedTemporaryFile


def syn(c,engine='Genus',printOutput=False):
	"""
	Synthesizes the circuit using Genus.

	Parameters
	----------
	c : Circuit
		Circuit to synthesize.
	engine : string
		Synthesis tool to use ('Genus' or 'Yosys')
	printOutput : bool
		Option to print synthesis log

	Returns
	-------
	Circuit
		Synthesized circuit.

	"""
	verilog = c.verilog()

	# probably should write output to the tmp file
	with NamedTemporaryFile() as tmp:
		if engine=='Genus':
			cmd = ['genus','-execute',f"""set_db / .library $env(GENUS_DIR)/share/synth/tutorials/tech/tutorial.lib;
					read_hdl -sv {tmp.name};
					elaborate;
					set_db syn_generic_effort high
					syn_generic;
					syn_map;
					syn_opt;
					write_hdl -generic;
					exit;"""]
		else:
			print('not implemented')
		tmp.write(bytes(verilog,'ascii'))
		tmp.flush()

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

	return verilog_to_circuit(output,name)

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
	t = copy(c)

	# add dual nodes
	for n in c:
		if c.type(n) in ['and','nand']:
			t.add_node(f'{n}_x',gate='and',output=c.nodes[n]['output'])
			t.add_node(f'{n}_x_in_fi',gate='or',output=False)
			t.add_node(f'{n}_0_not_in_fi',gate='nor',output=False)
			t.add_edges_from([(f'{n}_x_in_fi',f'{n}_x'),(f'{n}_0_not_in_fi',f'{n}_x')])
			t.add_edges_from((f'{p}_x',f'{n}_x_in_fi') for p in c.predecessors(n))
			for p in c.predecessors(n):
				t.add_node(f'{p}_is_0',gate='nor',output=False)
				t.add_edge(f'{p}_is_0',f'{n}_0_not_in_fi')
				t.add_edge(f'{p}_x',f'{p}_is_0')
				t.add_edge(p,f'{p}_is_0')

		elif c.type(n) in ['or','nor']:
			t.add_node(f'{n}_x',gate='and',output=c.nodes[n]['output'])
			t.add_node(f'{n}_x_in_fi',gate='or',output=False)
			t.add_node(f'{n}_1_not_in_fi',gate='nor',output=False)
			t.add_edges_from([(f'{n}_x_in_fi',f'{n}_x'),(f'{n}_1_not_in_fi',f'{n}_x')])
			t.add_edges_from((f'{p}_x',f'{n}_x_in_fi') for p in c.predecessors(n))
			for p in c.predecessors(n):
				t.add_node(f'{p}_is_1',gate='and',output=False)
				t.add_edge(f'{p}_is_1',f'{n}_1_not_in_fi')
				t.add_node(f'{p}_not_x',gate='not',output=False)
				t.add_edge(f'{p}_x',f'{p}_not_x')
				t.add_edge(f'{p}_not_x',f'{p}_is_1')
				t.add_edge(p,f'{p}_is_1')

		elif c.type(n) in ['buf','not']:
			t.add_node(f'{n}_x',gate='buf',output=c.nodes[n]['output'])
			p = list(c.predecessors(n))[0]
			t.add_edge(f'{p}_x',f'{n}_x')

		elif c.type(n) in ['xor','xnor']:
			t.add_node(f'{n}_x',gate='or',output=c.nodes[n]['output'])
			t.add_edges_from((f'{p}_x',f'{n}_x') for p in c.predecessors(n))

		elif c.type(n) in ['0','1']:
			t.add_node(f'{n}_x',gate='0',output=c.nodes[n]['output'])

		elif c.type(n) in ['input']:
			t.add_node(f'{n}_x',gate='input',output=c.nodes[n]['output'])

		elif c.type(n) in ['dff']:
			t.add_node(f'{n}_x',gate='dff',output=c.nodes[n]['output'],clk=c.nodes[n]['clk'])
			p = list(c.predecessors(n))[0]
			d.add_edge(f'{p}_x',f'{n}_x')

		elif c.type(n) in ['lat']:
			t.add_node(f'{n}_x',gate='lat',output=c.nodes[n]['output'],clk=c.nodes[n]['clk'],rst=c.nodes[n]['rst'])
			p = list(c.predecessors(n))[0]
			t.add_edge(f'{p}_x',f'{n}_x')

		else:
			print(f"unknown gate type: {c.nodes[n]['type']}")
			code.interact(local=locals())

	for n in t:
		if 'type' not in t.nodes[n]:
			print(f"empty gate type: {n}")
			code.interact(local=locals())

	return t

def miter(c0,c1=None,startpoints=None,endpoints=None):
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
	pass

def sensitivity(c,endpoint):
	"""
	Creates a circuit to compute sensitivity.

	Parameters
	----------
	c : Circuit
		Sequential circuit to unroll.
	endpoint : str
		Node to compute sensitivity at.

	Returns
	-------
	Circuit
		Sensitivity circuit.

	"""
	pass

def sensitize(c,n):
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
	pass

def mphf(c,n):
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
	pass
	#def runXorTreeSat(w,x):
	#	o = max(1,math.ceil(math.log2(w)))
	#	print(o)

	#	xors = '&'.join(
	#			'('+'|'.join(
	#				'('+'^'.join(
	#					f'in[{j}]' for j in random.sample(set(range(w+1)),2)
	#				)+')' for k in range(o)
	#			)+')' for i in range(x)
	#		)


