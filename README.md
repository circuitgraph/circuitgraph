![CircuitGraph Logo](https://github.com/circuitgraph/circuitgraph/blob/master/docs/circuitgraph.png)

# CircuitGraph

[![Build Status](https://travis-ci.com/circuitgraph/circuitgraph.svg?branch=master)](https://travis-ci.com/circuitgraph/circuitgraph)
[![codecov](https://codecov.io/gh/circuitgraph/circuitgraph/branch/master/graph/badge.svg)](https://codecov.io/gh/circuitgraph/circuitgraph)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

[**CircuitGraph**](https://circuitgraph.github.io/circuitgraph/) is a library for working with hardware designs as graphs. It was born out of the observation that many circuit analysis and transformation techniques are easier to implement when cirucits are represented as digraphs. CircuitGraph provides an interface to do this, along with integrations with other useful tools such as sat solvers and the [Yosys](http://www.clifford.at/yosys/) synthesis tool, and input/output to verilog.

## Installation

CircuitGraph requires Python3. CircuitGraph is still in the pre-release stage, so for now installation must be done by cloning this repository as such:

```shell
cd <install location>
git clone https://github.com/circuitgraph/circuitgraph.git
pip install -r requirements.txt
pip install .
```
### Optional Packages

In addition to the packages enumerated in `requirements.txt`, there are a few tools you can install to enable additional functionality.

If you would like to perform simulation you can install [Verilator](https://www.veripool.org/wiki/verilator) which is interfaced with using [PyVerilator](https://github.com/maltanar/pyverilator). Note that PyVerilator is a little finicky, and we are looking into better solutions for simulation.

If you would like to perform synthesis you can install either Cadence Genus or [Yosys](http://www.clifford.at/yosys/). If you're going to use Genus, you must provide the path to a synthesis library to use by setting the `CIRCUITGRAPH_GENUS_LIBRARY_PATH` variable. 

## Overview

The `Circuit` class is at the core of the library and it is essentially a wrapper around a [NetworkX](https://networkx.github.io) graph object. This graph is accessable through the `graph` member variable of `Circuit` and can be used as an entrypoint to the robust NetworkX API.

Here's a simple example of reading in a verilog file, adding a node to the graph, and writing back to a new file.

```python
import circuitgraph as cg

c = cg.from_file('/path/to/circuit.v')
# Add an AND gate to the circuit that takes as input nets o0, o1, o2, o3
c.add('g', 'and', fanin=[f'o{i}' for i in range(4)])
cg.to_file(c, '/path/to/output/circuit.v')
```

The documentation can be found [here](https://circuitgraph.github.io/circuitgraph/).

## Developing

CI Testing and coverage is setup using [Travis CI](https://travis-ci.org/) and [Codecov](https://codecov.io). Documentation is built using pdoc3, which you can install using `pip install pdoc3`. If you would like to generate coverage information locally, install coverage and codecov.

```shell
pip install coverage codecov
```

Tests are run using the builtin unittest framework.

Code should be formatted using [black](https://black.readthedocs.io/en/stable/) which can be installed by running `pip install black`. [Pre-commit](https://pre-commit.com) is used to automatically run black on commit. This can be installed by running `pip install pre-commit` and `pre-commit install` in the project directory.

## Citation

Please check back soon.
