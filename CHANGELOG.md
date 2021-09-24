# Changelog
All notable changes to this project will be documented in this file.

## [0.1.3] - 2021-09-24
### Added
- More robust checks for incorrect circuit construction
- More robust parsing, including faster parsing using regex
- Simple circuit visualization
- `X` type for nodes (similar to `0`, and `1`)
- Sequential unroll transform

## [0.1.2] - 2021-01-24
### FIXED
- Synthesis now works with python3.6 again

### Added
- DesignCompiler synthesis

## [0.1.1] - 2021-01-22
### FIXED
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
