"""Holds a graphical representation of a circuit"""
import re

from circuitgraph.io import verilog_to_graph, graph_to_verilog


class CircuitGraph:

    def __init__(self, graph):
        """Create a new CircuitGraph with the given grpah"""
        self.graph = graph

    def upstream(self, node):
        """Get all gates upstream of a gate (until a memory element)"""
        gates = set()
        for predecessor in self.graph.predecessors(node):
            gates.add(predecessor)
            if self.graph.nodes[predecessor]['gate'] not in ['ff', 'lat']:
                gates |= self.upstream(predecessor)
        return gates

    def downstream(self, node):
        """Get all gates downstream of a gate (until a memory element)"""
        gates = set()
        for successor in self.graph.successors(node):
            gates.add(successor)
            if self.graph.nodes[successor]['gate'] not in ['ff', 'lat']:
                gates |= self.downstream(successor)
        return gates

    def fanin(self, node):
        """Returns an iterable of the gates driving a node"""
        return self.graph.predecessors(node)

    def fanout(self, node):
        """Returns an iterable of the gates a node is driving"""
        return self.graph.successors(node)


def from_verilog(file_path, top=None):
    """Creates a new CircuitGraph from a verilog file.

    If the name of the module to create a graph from is different than the
    file name, specify it using the `top` argument"""
    if top is None:
        top = file_path.split('/')[-1].replace('.v', '')
    with open(file_path, 'r') as f:
        data = f.read()
    regex = rf"module\s+{top}\s*\(.*?\);(.*?)endmodule"
    m = re.search(regex, data, re.DOTALL)
    return CircuitGraph(verilog_to_graph(m.group(1), top))


def to_verilog(circuit):
    """Converts a CircuitGraph to a string of verilog code"""
    return graph_to_verilog(circuit.graph)
