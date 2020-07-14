"""Functions for simulating circuits using Verilator"""

import tempfile
import pyverilator
from circuitgraph.io import verilog_to_circuit,circuit_to_verilog
from tempfile import NamedTemporaryFile

def construct_simulator(c):
	"""
	Constructs a PyVerilator instance.

	Parameters
	----------
	c : Circuit
		Circuit to simulate

	Returns
	-------
	PyVerilator
		Simulation instance
	"""

	verilog = circuit_to_verilog(c)

	with NamedTemporaryFile(suffix='.v') as tmp:
		tmp.write(bytes(verilog,'ascii'))
		tmp.flush()
		sim = pyverilator.PyVerilator.build(tmp.name)

	return sim

def sim(c,values):
	"""
	Simulates circuit with given values

	Parameters
	----------
	c : Circuit
		Circuit to simulate
	values : dict of str:bool
		Values to simulate

	Returns
	-------
	dict of str:bool
		Output values.
	"""
	sim = construct_simulator(c)

	for n,v in values.items():
		setattr(sim.io,n,v)

	return {n:getattr(sim.io,n) for n in c}

