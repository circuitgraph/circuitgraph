from pysat.formula import CNF,IDPool
from pysat.solvers import Cadical

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
