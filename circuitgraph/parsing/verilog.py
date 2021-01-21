import pathlib

from lark import Lark, Transformer, v_args

from circuitgraph import Circuit, supported_types


class Declaration:
    def __init__(self, names, type):
        self.names = names
        assert type in ['input', 'output', 'wire']
        self.type = type


class ModuleInstantiation:
    def __init__(self, instance_type, instances):
        self.type = instance_type
        self.instances = instances


class ModuleInstance:
    def __init__(self, identifier, pins):
        self.identifier = identifier
        self.pins = pins


class ContinuousAssign:
    def __init__(self, assignments):
        self.assignments = assignments


class Assignment:
    def __init__(self, lvalue, cond):
        self.lvalue = lvalue
        self.cond = cond


@v_args(inline=True)
class VerilogCircuitGraphTransformer(Transformer):

    def __init__(self, blackboxes):
        self.c = Circuit()
        self.blackboxes = blackboxes
        self.tie0 = 'tie_0'
        self.tie1 = 'tie_1'
        self.c.add(self.tie0, '0')
        self.c.add(self.tie1, '1')
    
    # Source text
    def start(self, description):
        return description

    def module(self, module_name, list_of_ports, *module_items):
        self.c.name = module_name
        
        io = set()
        for port in list_of_ports:
            io.add(port)

        outputs = []

        for item in module_items:
            if isinstance(item, Declaration):
                if item.type == 'input':
                    for name in item.names:
                        self.c.add(name, item.type)
                elif item.type == 'output':
                    for name in item.names:
                        outputs.append(name)
            elif isinstance(item, ModuleInstantiation):
                if item.type in supported_types:
                    for instance in item.instances:
                        if not isinstance(instance.pins, tuple):
                            raise ValueError('Primitive gates cannot be '
                                             'instantiated with named port '
                                             'connections')
                        output = instance.pins[0]
                        self.c.add(output,
                                   type=item.type,
                                   fanin=instance.pins[1:])
                elif item.type in [bb.name for bb in self.blackboxes]:
                    bb = {bb.name: bb for bb in self.blackboxes}[item.type]
                    for instance in item.instances:
                        if not isinstance(instance.pins, dict):
                            raise ValueError('Blackboxes must be instantiated '
                                             'with named port connections.')
                        for o in bb.outputs:
                            self.c.add(instance.pins[o], type='buf')
                        self.c.add_blackbox(bb,
                                            instance.identifier,
                                            instance.pins)
                else:
                    raise ValueError(f'Module {item.type} not in blackboxes.')
            elif isinstance(item, ContinuousAssign):
                for assignment in item.assignments:
                    # Special case for assign x = 1'b0/1
                    if assignment.cond in [self.tie0, self.tie1]:
                        self.c.add(assignment.lvalue,
                                   self.c.type(assignment.cond))
                    else:
                        self.c.add(assignment.lvalue,
                                   'buf',
                                   fanin=[assignment.cond])

        for o in outputs:
            if o in self.c.nodes():
                o_driver = f'{o}_driver'
                while o_driver in self.c.nodes():
                    o_driver += '_0'
                self.c.relabel({o: o_driver})
                self.c.add(o, 'output')
                self.c.connect(o_driver, o)
            else:
                self.c.add(o, 'output')
        
        return self.c

    def list_of_ports(self, *ports):
        parsed_ports = []
        for port in ports:
            if isinstance(port, str):
                parsed_ports.append(port)
            else:
                raise NotImplementedError()
        return parsed_ports

    # Declarations
    def input_declaration(self, list_of_variables):
        return Declaration(list_of_variables, 'input')

    def output_declaration(self, list_of_variables):
        return Declaration(list_of_variables, 'output')

    def net_declaration(self, list_of_variables):
        return Declaration(list_of_variables, 'wire')

    def continuous_assign(self, list_of_assignments):
        return ContinuousAssign(list_of_assignments)

    def list_of_assignments(self, *assignments):
        return assignments

    def assignment(self, lvalue, cond):
        return Assignment(lvalue, cond)

    def list_of_variables(self, *identifiers):
        return identifiers

    # Module Instantiations
    def module_instantiation(self, identifier, *module_instances):
        return ModuleInstantiation(identifier, module_instances)

    def module_instance(self, identifier, list_of_module_connecetions):
        return ModuleInstance(identifier, list_of_module_connecetions)

    def list_of_module_connections(self, *module_port_connections):
        if isinstance(module_port_connections[0], dict):
            d = dict()
            for m in module_port_connections:
                d.update(m)
            return d
        return module_port_connections

    def module_port_connection(self, expression):
        return expression

    def named_port_connection(self, identifier, expression):
        return {identifier: expression}

    def expression(self, s):
        return s

    def constant_value(self, value):
        return value

    def constant_zero(self):
        return self.tie0
    
    def constant_one(self):
        return self.tie1

    # General
    def identifier(self, s):
        return str(s)

    # Assign Statements
    def lvalue(self, s):
        return s

    def not_gate(self, *items):
        io = "_".join(items)
        return self.c.add(f"not_{io}", "not", fanin=items[0], uid=True)

    def xor_gate(self, *items):
        io = "_".join(items)
        return self.c.add(f"xor_{io}", "xor", fanin=[items[0], items[1]], uid=True)

    def xnor_gate(self, *items):
        io = "_".join(items)
        return self.c.add(f"xnor_{io}", "xnor", fanin=[items[0], items[1]], uid=True)

    def and_gate(self, *items):
        io = "_".join(items)
        return self.c.add(f"and_{io}", "and", fanin=[items[0], items[1]], uid=True)

    def or_gate(self, *items):
        io = "_".join(items)
        return self.c.add(f"or_{io}", "or", fanin=[items[0], items[1]], uid=True)

    def ternary(self, *items):
        io = "_".join(items)
        n = self.c.add(f"mux_n_{io}", "not", fanin=items[0], uid=True)
        a0 = self.c.add(f"mux_a0_{io}", "and", fanin=[n, items[2]], uid=True)
        a1 = self.c.add(f"mux_a1_{io}", "and", fanin=[items[0], items[1]], uid=True)
        return self.c.add(f"mux_o_{io}", "or", fanin=[a0, a1], uid=True)

    def val(self, item):
        if item in ["1'b0", "1'h0"]:
            return self.tie_0
        elif item in ["1'b1", "1'h1"]:
            return self.tie_1
        else:
            return item


def get_verilog_parser(blackboxes):
    transformer = VerilogCircuitGraphTransformer(blackboxes)
    with open(pathlib.Path(__file__).parent.absolute() / 'verilog.lark') as f:
        return Lark(f, parser='lalr', transformer=transformer)