"""Functions for reading/writing CircuitGraphs"""

import networkx as nx
import re
import os
from circuitgraph import Circuit

defaultSeqTypes = [{'name':'fflopd','type':'ff','io':{'d':'D','q':'Q','clk':'CK'},
'def':"""
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
	},
	{'name':'latchdrs','type':'lat','io':{'d':'D','q':'Q','clk':'ENA','r':'R','s':'S'},
'def':""
}]

def from_file(path,name=None,seqTypes=None):
	"""Creates a new CircuitGraph from a verilog file.
	If the name of the module to create a graph from is different than the
	file name, specify it using the `name` argument"""
	if name is None:
		name = path.split('/')[-1].replace('.v', '')
	with open(path, 'r') as f:
		verilog = f.read()
	return verilog_to_circuit(verilog,name,seqTypes)

def from_lib(circuit,name=None):
	path = f'{os.path.dirname(__file__)}/../netlists/{circuit}.v'
	return from_file(path,name)

def verilog_to_circuit(verilog, name, seqTypes=None):
	"""Creates a new Circuit from a verilog string."""

	if seqTypes is None:
		seqTypes = defaultSeqTypes

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


def circuit_to_verilog(c,seqTypes=None):
	inputs = []
	outputs = []
	insts = []
	wires = []
	defs = set()

	if seqTypes is None:
		seqTypes = defaultSeqTypes

	for n in c.nodes():
		if c.type(n) in ['xor','xnor','buf','not','nor','or','and','nand']:
			fanin = ','.join(p for p in c.fanin(n))
			insts.append(f"{c.type(n)} g_{n} ({n},{fanin})")
			wires.append(n)
		elif c.type(n) in ['0','1']:
			insts.append(f"assign {n} = 1'b{c.type(n)}")
		elif c.type(n) in ['input']:
			inputs.append(n)
			wires.append(n)
		elif c.type(n) in ['output']:
			outputs.append(n.replace('output[','')[:-1])
		elif c.type(n) in ['ff','lat']:
			wires.append(n)

			# get template
			for s in seqTypes:
				if s['type']==c.type(n):
					seq	= s
					defs.add(s['def'])
					break

			# connect
			io = []
			if f'd[{n}]' in c:
				d = c.fanin(f'd[{n}]').pop()
				io.append(f".{seq['io']['d']}({d})")
			if f'r[{n}]' in c:
				r = c.fanin(f'r[{n}]').pop()
				io.append(f".{seq['io']['r']}({r})")
			if f's[{n}]' in c:
				s = c.fanin(f's[{n}]').pop()
				io.append(f".{seq['io']['s']}({s})")
			if f'clk[{n}]' in c:
				clk = c.fanin(f'clk[{n}]').pop()
				io.append(f".{seq['io']['clk']}({clk})")
			io.append(f".{seq['io']['q']}({n})")
			insts.append(f"{s['name']} g_{n} ({','.join(io)})")

		elif c.type(n) in ['clk','d','r','s']:
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
	verilog += '\n'.join(defs)


	return verilog

