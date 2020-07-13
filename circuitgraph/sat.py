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

	Example
	-------
	>>> import circuitgraph as cg
	>>> c = cg.from_file('rtl/s27.v')
	>>> cg.sat(c)
	{'G17': True, 'n_20': False, 'n_12': True, 'n_11': False, 'G0': True, 'n_9': True, 'n_10': True, 'n_7': False, 'n_8': False, 'n_1': False, 'G7': True, 'n_4': True, 'n_5': True, 'n_6': True, 'G2': False, 'n_3': False, 'n_2': False, 'G6': True, 'G3': True, 'n_0': False, 'G1': True, 'G5': True, 'n_21': False, 'd[G5]': True, 'r[G5]': True, 'clk[G5]': True, 'clk': True, 'd[G6]': False, 'r[G6]': True, 'clk[G6]': True, 'd[G7]': True, 'r[G7]': True, 'clk[G7]': True, 'output[G17]':
			True}
	>>> cg.sat(c,true=['G17','n_20'],false=['G6'])
	False

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

def signalProbability(c,n):
	"""
	Determines the probability of the output being true overall startpoint combinations

	Parameters
	----------
	c : Circuit
		Input circuit.
	n : str
		Nodes to determine probability for.

	Returns
	-------
	float
		Probability.
	"""
	# get startpoints not in node fanin
	non_fanin_startpoints = c.startpoints()-c.startpoints(n)

	# get approximate count with node true and other inputs fixed
	count = approxModelCount(c,true=non_fanin_startpoints|set([n]))

	return count/(2**len(c.startpoints(n)))

