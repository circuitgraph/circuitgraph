"""Holds a graphical representation of a circuit"""
from circuitgraph.utils import parse_verilog


class CircuitGraph:

    def __init__(self, file_path):
        """Create a new CircuitGraph from a verilog file"""
        self.graph, self.outputs = parse_verilog(file_path)
    
    def upstream(self, node):
        """Get all gates upstream of a gate (until a memory element)"""
        gates = set()
        for predecessor in self.graph.predecessors(node):
            gates.add(predecessor)
            if self.graph.nodes[predecessor]['gate'] not in ['ff','lat']:
                gates |= self.upstream(predecessor)
        return gates

    def downstream(self, node):
        """Get all gates downstream of a gate (until a memory element)"""
        gates = set()
        for successor in self.graph.successors(node):
            gates.add(successor)
            if self.graph.nodes[successor]['gate'] not in ['ff','lat']:
                gates |= self.downstream(successor)
        return gates

    def fanin(self, node):
        """Returns an iterable of the gates driving a node"""
        return self.graph.predecessors(node)

    def fanout(self, node):
        """Returns an iterable of the gates a node is driving"""
        return self.graph.successors(node)
