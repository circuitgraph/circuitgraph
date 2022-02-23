"""Utilities for parsing netlists."""
from circuitgraph.parsing.fast_verilog import fast_parse_verilog_netlist
from circuitgraph.parsing.verilog import (
    parse_verilog_netlist,
    VerilogParsingWarning,
    VerilogParsingError,
)
