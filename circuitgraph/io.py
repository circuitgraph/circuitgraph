"""Functions for reading/writing CircuitGraphs"""
import networkx as nx
import re

def verilog_to_graph(verilog, module):
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


def graph_to_verilog(graph):
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

