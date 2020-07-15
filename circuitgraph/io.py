"""Functions for reading/writing CircuitGraphs"""

import networkx as nx
import re
from circuitgraph import Circuit

def from_file(path,name=None,seqTypes=None):
	"""Creates a new CircuitGraph from a verilog file.
	If the name of the module to create a graph from is different than the
	file name, specify it using the `name` argument"""
	if name is None:
		name = path.split('/')[-1].replace('.v', '')
	if seqTypes is None:
		seqTypes = [{'name':'fflopd','type':'ff','io':{'d':'D','q':'Q','clk':'CK'}},
				{'name':'latchdrs','type':'lat','io':{'d':'D','q':'Q','clk':'ENA','r':'R','s':'S'}}]
	with open(path, 'r') as f:
		verilog = f.read()
	return verilog_to_circuit(verilog,name,seqTypes)


def verilog_to_circuit(verilog, name, seqTypes):
	"""Creates a new Circuit from a verilog string."""

	# extract module
	regex = rf"module\s+{name}\s*\(.*?\);(.*?)endmodule"
	m = re.search(regex,verilog,re.DOTALL)
	module = m.group(1)

	# create circuit
	c = Circuit(name=name)

	# handle gates
	regex = "(or|nor|and|nand|not|xor|xnor)\s+\S+\s*\((.+?)\);"
	for gate, net_str in re.findall(regex,module,re.DOTALL):
		# parse all nets
		nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
		c.add(nets[0],gate,fanin=nets[1:])

	# handle seq
	for st in seqTypes:
		# find matching insts
		regex = f"{st['name']}\s+[^\s(]+\s*\((.+?)\);"
		for io in re.findall(regex,module,re.DOTALL):
			# find matching pins
			pins = {}
			for typ,name in st['io'].items():
				regex = f".{name}\s*\((.+?)\)"
				n = re.findall(regex,io,re.DOTALL)[0]
				pins[typ] = n

			c.add(pins.get('q',None),st['type'],fanin=pins.get('d',None),clk=pins.get('clk',None),
					r=pins.get('r',None),s=pins.get('s',None))


	# handle assigns
	assign_regex = "assign\s+(.+?)\s*=\s*(.+?);"
	for n0, n1 in re.findall(assign_regex,module):
		c.add(n0.replace(' ',''),'buf',fanin=n1.replace(' ',''))

	for n in c:
		if 'type' not in c.graph.nodes[n]:
			if n == "1'b0":
				c.add(n,'0')
			elif n == "1'b1":
				c.add(n,'1')
			else:
				c.add(n,'input')

	# get outputs
	out_regex = "output\s(.+?);"
	for net_str in re.findall(out_regex,module,re.DOTALL):
		nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
		for n in nets:
			c.add(n,'output',fanin=n)

	return c


def circuit_to_verilog(c):
	inputs = []
	outputs = []
	insts = []
	wires = []

	for n in c.nodes():
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

