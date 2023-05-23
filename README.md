<img src="https://raw.githubusercontent.com/circuitgraph/circuitgraph/master/docs/circuitgraph.png" width="300">

# CircuitGraph

[![Python package](https://github.com/circuitgraph/circuitgraph/actions/workflows/python-package.yml/badge.svg)](https://github.com/circuitgraph/circuitgraph/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/circuitgraph/circuitgraph/branch/master/graph/badge.svg?token=26ZX0HILB2)](https://codecov.io/gh/circuitgraph/circuitgraph)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

[**CircuitGraph**](https://circuitgraph.github.io/circuitgraph/) is a library for working with hardware designs as graphs. CircuitGraph provides an interface to do this built on [NetworkX](https://networkx.github.io), along with integrations with other useful tools such as sat solvers and the [Yosys](http://www.clifford.at/yosys/) synthesis tool, and input/output to verilog.

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

## Installation

CircuitGraph requires Python3.7 or greater
The easiest way to install is via PyPi:
```shell
pip install circuitgraph
```
To install from the release, download and:
```shell
pip install circuitgraph-<release>.tar.gz
```

Finally, to install in-place with the source, use:
```shell
cd <install location>
git clone https://github.com/circuitgraph/circuitgraph.git
cd circuitgraph
pip install -r requirements.txt
pip install -e .
```
### Optional Packages

In addition to the packages enumerated in `requirements.txt`, there are a few tools you can install to enable additional functionality.

If you would like to use the satisfiability functionality, install [PySAT](https://pysathq.github.io).

Open source synthesis can be perofmred by installing [Yosys](http://www.clifford.at/yosys/) and adding it to your path.
Alternatively, Genus or DesignCompiler can be used by providing the path to a generic library to use by setting the `CIRCUITGRAPH_GENUS_LIBRARY_PATH` and `CIRCUITGRAPH_DC_LIBRARY_PATH` environment variables.

## Contributing

If you have ideas on how to improve this library we'd love to hear your suggestions. Please open an issue.
If you want to develop the improvement yourself, please consider the information below.

Coverage is computed using [Codecov](https://codecov.io).
 If you would like to generate coverage information locally, install coverage and codecov.
```shell
pip install coverage codecov
make coverage
```

Documentation is built using pdoc3.
```shell
pip install pdoc3
make doc
```

Tests are run using the builtin unittest framework. Some basic linting is performed using flake8.
```shell
pip instsall flake8
make test
```

Code should be formatted using [black](https://black.readthedocs.io/en/stable/).
[Pre-commit](https://pre-commit.com) is used to automatically run black on commit.
```shell
pip install black pre-commit
pre-commit install
```
Pre-commit also runs a few other hooks, including a docstring formatter and linter. Docs follow the `numpy` documentation convention.

## Citation

If you use this software for your research, we ask you cite this publication:
https://joss.theoj.org/papers/10.21105/joss.02646

```
@article{sweeney2020circuitgraph,
  title={CircuitGraph: A Python package for Boolean circuits},
  author={Sweeney, Joseph and Purdy, Ruben and Blanton, Ronald D and Pileggi, Lawrence},
  journal={Journal of Open Source Software},
  volume={5},
  number={56},
  pages={2646},
  year={2020}
}
```

## Acknowledgements

Circuitgraph icon designed by [ncasti](https://github.com/ncasti).
