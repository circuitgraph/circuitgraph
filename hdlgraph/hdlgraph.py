"""Holds a graphical representation of a circuit"""
from hdlgraph.utils import parse_verilog


class HDLGraph:

    def __init__(self, file_path):
        self.graph = parse_verilog(file_path) 
