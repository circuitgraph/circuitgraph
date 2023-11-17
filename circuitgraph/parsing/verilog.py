"""Utils for parsing verilog with Lark."""
from pathlib import Path

from lark import Lark, Transformer

from circuitgraph import Circuit, primitive_gates


def _get_context_window(text, index):
    """
    Find the line containing an index.

    Parameters
    ----------
    text: str
            The text to search in
    index: int
            The index to search around

    Returns
    -------
    str
            The line that `index` is contained in.

    """
    previous_newline = max(0, text.rfind("\n", 0, index))
    next_newline = text.find("\n", index)
    context = text[previous_newline:next_newline]
    context += "\n" + " " * (index - previous_newline - 1) + "^"
    return context


class VerilogParsingError(Exception):
    """Raised if there is an issue parsing the verilog."""

    def __init__(self, message, token, text):
        super().__init__()
        self.message = message
        self.token = token
        self.line = getattr(token, "line", "?")
        self.column = getattr(token, "column", "?")
        index = getattr(token, "pos_in_stream", None)
        if index:
            self.context = _get_context_window(text, index)
        else:
            self.context = "?"

    def __str__(self):
        """Print the line and column of the error."""
        self.message += f" (line {self.line}, column {self.column}):\n"
        self.message += self.context
        return self.message


class VerilogParsingWarning(Exception):
    """Potentially raised if there is a warning parsing verilog."""


class _VerilogCircuitGraphTransformer(Transformer):
    """A lark.Transformer for parsing a verilog netlist."""

    def __init__(self, text, blackboxes, warnings=False, error_on_warning=False):
        """
        Initialize a new transformer.

        Parameters
        ----------
        text: str
                The netlist that the transformer will be used on, used for
                error messages.
        blackboxes: list of circuitgraph.BlackBox
                The blackboxes present in the netlist that will be parsed.
        warnings: bool
                If True, warnings about unused nets will be printed.
        error_on_warning: bool
                If True, unused nets will cause raise `VerilogParsingWarning`
                exceptions.

        """
        super().__init__()
        self.c = Circuit()
        self.text = text
        self.blackboxes = blackboxes
        self.warnings = warnings
        self.error_on_warning = error_on_warning
        self.tie_0 = self.c.add("tie_0", "0")
        self.tie_1 = self.c.add("tie_1", "1")
        self.tie_x = self.c.add("tie_x", "x")
        self.gate_expressions = set()
        self.io = set()
        self.inputs = set()
        self.outputs = set()
        self.wires = set()

    # Helper functions
    def add_node(self, n, node_type, fanin=None, fanout=None, uid=False):
        """So that nodes are of type `str`, not `lark.Token`."""
        if not fanin:
            fanin = []
        elif type(fanin) not in [list, set]:
            fanin = [fanin]
        if not fanout:
            fanout = []
        elif type(fanout) not in [list, set]:
            fanout = [fanout]

        fanin = [str(i) for i in fanin]
        fanout = [str(i) for i in fanout]
        node_type = str(node_type)

        return self.c.add(
            str(n),
            node_type,
            fanin=fanin,
            fanout=fanout,
            uid=uid,
            add_connected_nodes=True,
            allow_redefinition=True,
        )

    def add_blackbox(self, blackbox, name, connections=None):
        if not connections:
            connections = {}
        formatted_connections = {}
        for key in connections:
            formatted_connections[str(key)] = str(connections[key])
            if str(connections[key]) not in self.c:
                self.c.add(str(connections[key]), "buf")
        self.c.add_blackbox(blackbox, str(name), formatted_connections)

    def warn(self, message):
        if self.error_on_warning:
            raise VerilogParsingWarning(message)
        print(f"Warning: {message}")

    def check_for_warnings(self):
        for wire in self.wires:
            if wire not in self.c.nodes():
                self.warn(f"{wire} declared as wire but isn't connected.")

        for n in self.c.nodes():
            if (
                self.c.type(n) != "bb_input"
                and not self.c.is_output(n)
                and not self.c.fanout(n)
            ):
                self.warn(f"{n} doesn't drive any nets.")
            elif self.c.type(n) not in [
                "input",
                "0",
                "1",
                "bb_output",
            ] and not self.c.fanin(n):
                self.warn(f"{n} doesn't have any drivers.")

    # 1. Source text
    def start(self, description):
        return description

    def module(self, module_name_and_list_of_ports_and_module_items):
        self.c.name = str(module_name_and_list_of_ports_and_module_items[0])

        # Check if ports list matches with inputs and outputs
        if not self.inputs <= self.io:
            i = (self.inputs - self.io).pop()
            raise VerilogParsingError(
                f"{i} declared as output but not in port list", i, self.text
            )
        if not self.outputs <= self.io:
            o = (self.outputs - self.io).pop()
            raise VerilogParsingError(
                f"{o} declared as output but not in port list", o, self.text
            )
        if not self.io <= (self.inputs | self.outputs):
            v = (self.io - (self.inputs | self.outputs)).pop()
            raise VerilogParsingError(
                f"{v} in port list but was not declared as input or output",
                v,
                self.text,
            )

        # Relabel outputs using drivers
        for o in self.outputs:
            self.c.set_output(str(o))

        # Remove tie_0, tie_1 if not used
        if not self.c.fanout(self.tie_0):
            self.c.remove(self.tie_0)
        if not self.c.fanout(self.tie_1):
            self.c.remove(self.tie_1)
        if not self.c.fanout(self.tie_x):
            self.c.remove(self.tie_x)

        # Check for warnings
        if self.warnings:
            self.check_for_warnings()

        return self.c

    def list_of_ports(self, ports):
        for port in ports:
            self.io.add(port)

    # 2. Declarations
    def input_declaration(self, list_of_variables):
        r = list_of_variables[0]
        l=list_of_variables[1]
        if r:
            self.io.remove(l[0])
            list_of_variables = [f'''{l[0]}[{i}]''' for i in range(int(r.children[1]), int(r.children[0]) + 1)]
            self.io.update(list_of_variables)
        else:
            list_of_variables= l
        self.inputs.update(list_of_variables)
        for variable in list_of_variables:
            self.add_node(variable, "input")

    def output_declaration(self, list_of_variables):
        r = list_of_variables[0]
        l = list_of_variables[1]
        if r:
            self.io.remove(l[0])
            list_of_variables = [f'''{l[0]}[{i}]''' for i in range(int(r.children[1]), int(r.children[0]) + 1)]
            self.io.update(list_of_variables)
        else:
            list_of_variables = l
        self.outputs.update(list_of_variables)

    def net_declaration(self, list_of_variables):
        [list_of_variables] = list_of_variables
        self.wires.update(list_of_variables)

    def list_of_variables(self, identifiers):
        return identifiers

    # 3. Primitive Instances
    # These are merged with module isntantiations

    # 4. Module Instantiations
    def module_instantiation(self, name_of_module_and_module_instances):
        name_of_module = name_of_module_and_module_instances[0]
        module_instances = name_of_module_and_module_instances[1:]
        # Check if this is a primitive gate
        if name_of_module in primitive_gates:
            for name, ports in module_instances:
                if isinstance(ports, dict):
                    raise VerilogParsingError(
                        "Primitive gates cannot use named port connections",
                        name,
                        self.text,
                    )
                self.add_node(ports[0], name_of_module, fanin=ports[1:])
        # Otherwise, try to parse as blackbox
        else:
            try:
                bb = {i.name: i for i in self.blackboxes}[name_of_module]
            except KeyError as e:
                raise VerilogParsingError(
                    f"Blackbox {name_of_module} not in list of defined blackboxes.",
                    name_of_module,
                    self.text,
                ) from e
            for name, connections in module_instances:
                if not isinstance(connections, dict):
                    raise VerilogParsingError(
                        "Blackbox instantiations must use named port connections",
                        name,
                        self.text,
                    )
                for output in bb.outputs():
                    if output in connections:
                        self.add_node(connections[output], "buf")
                self.add_blackbox(bb, name, connections)

    def module_instance(self, name_of_instance_and_list_of_module_connecetions):
        (
            name_of_instance,
            list_of_module_connecetions,
        ) = name_of_instance_and_list_of_module_connecetions
        return (name_of_instance, list_of_module_connecetions)

    def list_of_module_connections(self, module_port_connections):
        if isinstance(module_port_connections[0], dict):
            d = {}
            for m in module_port_connections:
                d.update(m)
            return d
        return module_port_connections

    def module_port_connection(self, expression):
        return expression[0]

    def named_port_connection(self, identifier_and_expression):
        [identifier, expression] = identifier_and_expression
        return {identifier: expression}

    # 5. Behavioral Statements
    def assignment(self, lvalue_and_expression):
        [lvalue, expression] = lvalue_and_expression
        if lvalue not in [self.tie_0, self.tie_1, self.tie_x]:
            if expression in self.gate_expressions:
                self.c.relabel({expression: str(lvalue)})
            else:
                self.add_node(lvalue, "buf", fanin=expression)

    # 6. Specify Section

    # 7. Expressions
    def expression(self, s):
        return s[0]

    def constant_zero(self, value):
        return self.tie_0

    def constant_one(self, value):
        return self.tie_1

    def constant_x(self, value):
        return self.tie_x

    def not_gate(self, items):
        io = "_".join(items)
        node = self.add_node(f"not_{io}", "not", fanin=items[0], uid=True)
        self.gate_expressions.add(node)
        return node

    def xor_gate(self, items):
        io = "_".join(items)
        node = self.add_node(f"xor_{io}", "xor", fanin=[items[0], items[1]], uid=True)
        self.gate_expressions.add(node)
        return node

    def xnor_gate(self, items):
        io = "_".join(items)
        node = self.add_node(f"xnor_{io}", "xnor", fanin=[items[0], items[1]], uid=True)
        self.gate_expressions.add(node)
        return node

    def and_gate(self, items):
        io = "_".join(items)
        node = self.add_node(f"and_{io}", "and", fanin=[items[0], items[1]], uid=True)
        self.gate_expressions.add(node)
        return node

    def or_gate(self, items):
        io = "_".join(items)
        node = self.add_node(f"or_{io}", "or", fanin=[items[0], items[1]], uid=True)
        self.gate_expressions.add(node)
        return node

    def ternary(self, items):
        io = "_".join(items)
        n = self.add_node(f"mux_n_{io}", "not", fanin=items[0], uid=True)
        a0 = self.add_node(f"mux_a0_{io}", "and", fanin=[n, items[2]], uid=True)
        a1 = self.add_node(f"mux_a1_{io}", "and", fanin=[items[0], items[1]], uid=True)
        node = self.add_node(f"mux_o_{io}", "or", fanin=[a0, a1], uid=True)
        self.gate_expressions.add(node)
        return node


def parse_verilog_netlist(netlist, blackboxes, warnings=False, error_on_warning=False):
    """
    Parse a verilog netlist into a Circuit.

    Parameters
    ----------
    netlist: str
            The verilog netlist to parse.
    blackboxes: list of circuitgraph.BlackBox
            The blackboxes present in the netlist.
    warnings: bool
            If True, warnings about unused nets will be printed.
    error_on_warning: bool
            If True, unused nets will cause raise `VerilogParsingWarning`
            exceptions.

    Returns
    -------
    circuitgraph.Circuit
            The parsed circuit.

    """
    transformer = _VerilogCircuitGraphTransformer(
        netlist, blackboxes, warnings, error_on_warning
    )
    with open(Path(__file__).parent.absolute() / "verilog.lark") as f:
        parser = Lark(f, parser="lalr", transformer=transformer)
    [c] = parser.parse(netlist)
    return c
