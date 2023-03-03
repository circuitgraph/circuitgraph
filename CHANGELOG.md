# Changelog
All notable changes to this project will be documented in this file.

## [0.2.1] -
### Fixed
- Approximate model counting subprocess newlines and encoding
- `set_type` docstring
- `props.influence` docstring
- Ternary transform for circuits with xor/xnor gates

### Added
- Generic flop bloackbox
- `insert_registers` transform
- `limit_fanout` transform
- `levelize` function


## [0.2.0] - 2022-04-22
### Fixed
- Visualization with BlackBoxes.

### Added
- Supergate construction functionality.

### Changed
- `output` is no longer a node type but an extra property. It can be accessed using `Circuit.is_output` and `Circuit.set_output`. Any node with a primitive gate type can also be marked as an output.
- Import structure has changed. Most functions should now be referrenced based on their parent module, e.g., `cg.tx.syn` instead of `cg.syn`.
- Most module names have been shortened for ease of use with new import structure.
- Renamed `sat` function to `solve`.
- Removed `copy` from `tx`. Copying a circuit can be done using `Circuit.copy`.


## [0.1.3] - 2021-09-24
### Added
- More robust checks for incorrect circuit construction
- More robust parsing, including faster parsing using regex
- Simple circuit visualization
- `x` type for nodes (similar to `0`, and `1`)
- Sequential unroll transform

## [0.1.2] - 2021-01-24
### Fixed
- Synthesis now works with python3.6 again

### Added
- DesignCompiler synthesis

## [0.1.1] - 2021-01-22
### Fixed
- Parsing is now being included correctly

### Added
- Lark based verilog parsing to vastly speed up reading verilog netlists

### Changed
- Replaced memory elements with a more general blackbox-based scheme

## [0.0.3] - 2020-09-08
### Fixed
- Image link in README is external so that it will appear in pypi

## [0.0.2] - 2020-09-08
### Fixed
- Constant valued nodes are now written to verilog
- README installation documentation to point to the pypi repo

### Removed
- pyverilator support, because it breaks installation on python distributions built without tkinter
- pyeda dependency because it is no longer needed for parsing

## [0.0.1] - 2020-08-30
Initial release
