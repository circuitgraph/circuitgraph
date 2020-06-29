import networkx as nx

import re


def parse_verilog(file_path, top=None):
    """Parses a verilog file into a graph. If top module is not specified, it
    is derived from the name of the file"""
    if top == None:
        top = file_path.split('/')[-1].replace('.v','')
    with open(file_path, 'r') as f:
        data = f.read()
    regex = f"module\s+{top}\s*\(.*?\);(.*?)endmodule"
    m = re.search(regex,data,re.DOTALL)
    return verilog_to_gates(m.group(1), top)

def verilog_to_gates(verilog, module):
    G = nx.DiGraph(name=module)

    # handle gates
    regex = "(or|nor|and|nand|not|xor|xnor)\s+\S+\s*\((.+?)\);"
    for gate, net_str in re.findall(regex,verilog,re.DOTALL):

        # parse all nets
        nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
        output = nets[0]
        inputs = nets[1:]
        # add to graph
        G.add_edges_from((net,output) for net in inputs)
        G.nodes[output]['gate'] = gate

    # handle ffs
    regex = "fflopd\s+\S+\s*\(\.CK\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((.+?)\)\);"
    for clk,d,q in re.findall(regex,verilog,re.DOTALL):

        # add to graph
        G.add_edge(d,q)
        G.nodes[q]['gate'] = 'ff'
        G.nodes[q]['clk'] = clk

    # handle lats
    regex = "latchdrs\s+\S+\s*\(\s*\.R\s*\((.+?)\),\s*\.S\s*\((.+?)\),\s*\.ENA\s*\((.+?)\),\s*.D\s*\((.+?)\),\s*.Q\s*\((.+?)\)\s*\);"
    for r,s,c,d,q in re.findall(regex,verilog,re.DOTALL):

        # add to graph
        G.add_edge(d,q)
        G.nodes[q]['gate'] = 'lat'
        G.nodes[q]['clk'] = c
        G.nodes[q]['rst'] = r

    # handle assigns
    assign_regex = "assign\s+(.+?)\s*=\s*(.+?);"
    for n0, n1 in re.findall(assign_regex,verilog):
        output = n0.replace(' ','')
        inpt = n1.replace(' ','')
        G.add_edge(inpt,output)
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
    out_regex = "output\s(.+?);"
    for net_str in re.findall(out_regex,verilog,re.DOTALL):
        nets = net_str.replace(" ","").replace("\n","").replace("\t","").split(",")
        for net in nets:
            G.add_edge(net,f'{net}_out')
            G.nodes[f'{net}_out']['gate'] = 'output'

    G = nx.relabel_nodes(G, lambda n: n.replace('[','_').replace(']','_'))
    return G
