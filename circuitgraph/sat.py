"""Functions for executing SAT, #SAT, and approx-#SAT on circuits"""

import signal
import tempfile
import re
from circuitgraph import Circuit
from subprocess import PIPE,run
from pysat.formula import CNF,IDPool
from pysat.solvers import Cadical

class Timeout:
	"""Class to handle timeout for SAT executions"""
	def __init__(self, seconds=1, error_message='Timeout'):
		self.seconds = seconds
		self.error_message = error_message
	def handle_timeout(self, signum, frame):
		raise TimeoutError(self.error_message)
	def __enter__(self):
		if self.seconds:
			signal.signal(signal.SIGALRM, self.handle_timeout)
			signal.alarm(self.seconds)
	def __exit__(self, type, value, traceback):
		if self.seconds:
			signal.alarm(0)

def add_assumptions(formula,variables,true=None,false=None):
	if true is None: true = set()
	if false is None: false = set()
	for n in true: formula.append([variables.id(n)])
	for n in false: formula.append([-variables.id(n)])

def construct_solver(c,true=None,false=None):
	"""
	Constructs a SAT solver instance with the given circuit and assumptions

	Parameters
	----------
	c : Circuit
		circuit to add to solver
	true : iterable of str
		Nodes to assume True.
	false : iterable of str
		Nodes to assume False.

	Returns
	-------
	solver : pysat.Cadical
		SAT solver instance
	variables : pysat.IDPool
		solver variable mapping
	"""
	formula,variables = cnf(c)
	add_assumptions(formula,variables,true,false)
	solver = Cadical(bootstrap_with=formula)
	return solver,variables

def cnf(c):
	"""
	Converts circuit to CNF using the Tseitin transformation

	Parameters
	----------
	c : Circuit
		circuit to transform

	Returns
	-------
	variables : pysat.IDPool
		formula variable mapping
	formula : pysat.CNF
		CNF formula
	"""
	variables = IDPool()
	formula = CNF()

	for n in c.nodes():
		variables.id(n)
		if c.type(n) == 'and':
			for f in c.fanin(n):
				formula.append([-variables.id(n),variables.id(f)])
			formula.append([variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
		elif c.type(n) == 'nand':
			for f in c.fanin(n):
				formula.append([variables.id(n),variables.id(f)])
			formula.append([-variables.id(n)] + [-variables.id(f) for f in c.fanin(n)])
		elif c.type(n) == 'or':
			for f in c.fanin(n):
				formula.append([variables.id(n),-variables.id(f)])
			formula.append([-variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
		elif c.type(n) == 'nor':
			for f in c.fanin(n):
				formula.append([-variables.id(n),-variables.id(f)])
			formula.append([variables.id(n)] + [variables.id(f) for f in c.fanin(n)])
		elif c.type(n) == 'not':
			if c.fanin(n):
				f = c.fanin(n).pop()
				formula.append([variables.id(n),variables.id(f)])
				formula.append([-variables.id(n),-variables.id(f)])
		elif c.type(n) in ['output','d','r','buf','clk']:
			if c.fanin(n):
				f = c.fanin(n).pop()
				formula.append([variables.id(n),-variables.id(f)])
				formula.append([-variables.id(n),variables.id(f)])
		elif c.type(n) in ['xor','xnor']:
			# break into heirarchical xors
			nets = list(c.fanin(n))

			# xor gen
			def xorClauses(a,b,c):
				formula.append([-variables.id(c),-variables.id(b),-variables.id(a)])
				formula.append([-variables.id(c),variables.id(b),variables.id(a)])
				formula.append([variables.id(c),-variables.id(b),variables.id(a)])
				formula.append([variables.id(c),variables.id(b),-variables.id(a)])

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
			if c.type(n) == 'xor':
				xorClauses(nets[-2],nets[-1],n)
			else:
				# invert xor
				variables.id(f'xor_inv_{n}')
				xorClauses(nets[-2],nets[-1],f'xor_inv_{n}')
				formula.append([variables.id(n),variables.id(f'xor_inv_{n}')])
				formula.append([-variables.id(n),-variables.id(f'xor_inv_{n}')])
		elif c.type(n) == '0':
			formula.append([-variables.id(n)])
		elif c.type(n) == '1':
			formula.append([variables.id(n)])
		elif c.type(n) in ['ff','lat','input']:
			pass
		else:
			print(f"unknown gate type: {c.type(n)}")
			code.interact(local=dict(globals(), **locals()))

	return formula,variables

def sat(c,true=None,false=None,timeout=None):
	"""
	Trys to find satisfying assignment, with optional assumptions

	Parameters
	----------
	c : Circuit
		Input circuit.
	true : iterable of str
		Nodes to assume True.
	false : iterable of str
		Nodes to assume False.
	timeout : int
		Seconds until timeout.

	Returns
	-------
	False or dict of str:bool
		Result.
	"""
	solver,variables = construct_solver(c,true,false)
	with Timeout(seconds=timeout):
		if solver.solve():
			model = solver.get_model()
			return {n:model[variables.id(n)-1]>0 for n in c.nodes()}
		else:
			return False

def approxModelCount(c,true=None,false=None,e=0.9,d=0.1,timeout=None):
	"""
	Approximates the number of solutions to circuit

	Parameters
	----------
	c : Circuit
		Input circuit.
	true : iterable of str
		Nodes to assume True.
	false : iterable of str
		Nodes to assume False.
	e : float (0-1)
		epsilon of approxmc
	d : float (0-1)
		delta of approxmc
	timeout : int
		Seconds until timeout.

	Returns
	-------
	int
		Estimate.
	"""

	formula,variables = cnf(c)
	add_assumptions(formula,variables,true,false)

	# specify sampling set
	enc_inps = ' '.join([str(variables.id(n)) for n in c.startpoints()])

	# write dimacs to tmp
	with tempfile.NamedTemporaryFile() as tmp:
		clause_str = '\n'.join(' '.join(str(v) for v in c)+' 0' for c in formula.clauses)
		dimacs = f'c ind {enc_inps} 0\np cnf {formula.nv} {len(formula.clauses)}\n{clause_str}\n'
		tmp.write(bytes(dimacs,'ascii'))
		tmp.flush()

		# run approxmc
		cmd = f'approxmc --epsilon={e} --delta={d} {tmp.name}'.split()
		with Timeout(seconds=timeout):
			result = run(cmd,stdout=PIPE,stderr=PIPE,universal_newlines=True)

	# parse results
	m = re.search('Number of solutions is: (\d+) x 2\^(\d+)',result.stdout)
	estimate = int(m.group(1))*(2**int(m.group(2)))
	return estimate

def modelCount(c,true=None,false=None,timeout=None):
	"""
	Determines the number of solutions to circuit

	Parameters
	----------
	c : Circuit
		Input circuit.
	true : iterable of str
		Nodes to assume True.
	false : iterable of str
		Nodes to assume False.
	timeout : int
		Seconds until timeout.

	Returns
	-------
	int
		Count.
	"""

	startpoints = c.startpoints()
	solver,variables = construct_solver(c,true,false)
	with Timeout(seconds=timeout):
		count = 0
		while solver.solve():
			model = solver.get_model()
			solver.add_clause([-model[variables.id(n)-1] for n in startpoints])
			count += 1

	return count

