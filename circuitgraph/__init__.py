"""
Python package `circuitgraph` provides a data structure
for the generation, manipulation, and evaluation of
Boolean circuits. The circuits are represented in a graph
format based on the `networkx` package.
"""

from circuitgraph.circuit import Circuit
from circuitgraph.io import *
from circuitgraph.sat import *
from circuitgraph.transform import *
