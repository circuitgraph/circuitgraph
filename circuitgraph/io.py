"""Functions for reading/writing CircuitGraphs"""
import networkx as nx

import re


def verilog_to_graph(verilog, module):
    G = nx.DiGraph(name=module)

    # handle gates
    regex = r"(or|nor|and|nand|not|xor|xnor)\s+\S+\s*\((.+?)\);"
    for gate, net_str in re.findall(regex, verilog, re.DOTALL):

        # parse all nets
        net_str = net_str.replace(" ", "").replace("\n", "").replace("\t", "")
        nets = net_str.split(",")
        output = nets[0]
        inputs = nets[1:]
        # add to graph
        G.add_edges_from((net, output) for net in inputs)
        G.nodes[output]['gate'] = gate

    # handle ffs
    regex = r"fflopd\s+\S+\s*\(\.CK\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((."
    regex += r"+?)\)\);"
    for clk, d, q in re.findall(regex, verilog, re.DOTALL):

        # add to graph
        G.add_edge(d, q)
        G.nodes[q]['gate'] = 'ff'
        G.nodes[q]['clk'] = clk

    # handle lats
    regex = r"latchdrs\s+\S+\s*\(\s*\.R\s*\((.+?)\),\s*\.S\s*\((.+?)\),\s*\."
    regex += r"ENA\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((.+?)\)\s*\);"
    for r, s, c, d, q in re.findall(regex, verilog, re.DOTALL):

        # add to graph
        G.add_edge(d, q)
        G.nodes[q]['gate'] = 'lat'
        G.nodes[q]['clk'] = c
        G.nodes[q]['rst'] = r

    # handle assigns
    assign_regex = r"assign\s+(.+?)\s*=\s*(.+?);"
    for n0, n1 in re.findall(assign_regex, verilog):
        output = n0.replace(' ', '')
        inpt = n1.replace(' ', '')
        G.add_edge(inpt, output)
        G.nodes[output]['gate'] = 'buf'

    for n in G.nodes():
        if 'gate' not in G.nodes[n]:
            if n == "1'b0":
                G.nodes[n]['gate'] = '0'
            elif n == "1'b1":
                G.nodes[n]['gate'] = '1'
            else:
                G.nodes[n]['gate'] = 'input'

    # get outputs
    out_regex = r"output\s(.+?);"
    for net_str in re.findall(out_regex, verilog, re.DOTALL):
        net_str = net_str.replace(" ", "").replace("\n", "").replace("\t", "")
        nets = net_str.split(",")
        for net in nets:
            G.add_edge(net, f'{net}_out')
            G.nodes[f'{net}_out']['gate'] = 'output'

    # replace buses with underscores
    G = nx.relabel_nodes(G, lambda n: n.replace('[', '_').replace(']', '_'))
    return G


def graph_to_verilog(graph):
    inputs = []
    outputs = []
    insts = []
    wires = []

    for n in graph.nodes:
        if graph.nodes[n]['gate'] not in ['ff', 'lat', '0', '1', 'input']:
            fanin = ','.join(p for p in graph.predecessors(n))
            insts.append(f"{graph.nodes[n]['gate']} g_{n} ({n},{fanin})")
            wires.append(n)
            if graph.nodes[n]['gate'] == 'output':
                outputs.append(n)
        elif graph.nodes[n]['gate'] in ['0', '1']:
            # insts.append(f"assign {n} = 1'b{c.nodes[n]['gate']};")
            pass
        elif graph.nodes[n]['gate'] in ['input']:
            inputs.append(n)
            wires.append(n)
        elif graph.nodes[n]['gate'] in ['ff']:
            d = list(graph.predecessors(n))[0]
            clk = graph.nodes[n]['clk']
            insts.append(f"fflopd g_{n} (.CK({clk}),.D({d}),.Q({n}))")
        elif graph.nodes[n]['gate'] in ['lat']:
            d = list(graph.predecessors(n))[0]
            r = graph.nodes[n]['rst']
            clk = graph.nodes[n]['clk']
            insts.append(
                f"latchdrs g_{n} (.ENA({clk}),.D({d}),.R({r}),.S(1'b1),"
                ".Q({n}))")
        else:
            print(f"unknown gate type: {graph.nodes[n]['gate']}")
            return

    verilog = f"module {graph.graph['name']} ("+','.join(inputs+outputs)+');\n'
    verilog += ''.join(f'input {inp};\n' for inp in inputs)
    verilog += ''.join(f'output {out};\n' for out in outputs)
    verilog += ''.join(f'wire {wire};\n' for wire in wires)
    verilog += ''.join(f'{inst};\n' for inst in insts)
    verilog += 'endmodule\n'

    return verilog
