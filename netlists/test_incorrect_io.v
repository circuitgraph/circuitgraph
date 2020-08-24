module test_part_select_inst_0(G1, G2);
  input [3:0] G1;
  output G2;

  and AND2(G2, G1[1:0], G1);
endmodule

module test_part_select_inst_1(G1, G2);
  input G1;
  output [3:0] G2;

  and AND2(G2[1:0], G1, G1);
endmodule

module test_part_select_assign_0(G1, G2);
  input [3:0] G1;
  output G2;

  assign G2 = G1[1:0] & G1;
endmodule

module test_part_select_assign_1(G1, G2);
  input G1;
  output [3:0] G2;

  assign G2[1:0] =  G1 & G1;
endmodule

module test_parameter_0 #(parameter test = 0) (G1, G2);
  input G1;
  output G2;

  assign G2 = G1;
endmodule

module test_parameter_1(G1, G2);
  input G1;
  output G2;

  parameter test = 0;

  assign G2 = G1;
endmodule

module test_concat_0(G1, G2);
  input G1;
  output [1:0] G2;

  assign G2 = {G1, G1};
endmodule

module test_concat_1(G1, G2, G3);
  input [1:0] G1;
  output G2, G3;

  assign {G2, G3} = G1;
endmodule

module test_instance(G1);
  input G1;

  fake_module i(G1);
endmodule

module test_seq(clk, G1, G2);
  input clk, G1;
  output G2;

  fflopd DFF_0_Q_reg(clk, G3, G4);
endmodule

module test_always(clk, G1, G2);
  input clk, G1;
  output G2;

  always@(posedge clk) begin
    G1 = G2;
  end
endmodule

module test_logical_operator(clk, G1, G2);
  input G1, G2;
  output G3;

  assign G3 = G1 && G2;
endmodule

module fflopd(CK, D, Q);
  input CK, D;
  output Q;
  wire CK, D;
  wire Q;
  wire next_state;
  reg  qi;
  assign #1 Q = qi;
  assign next_state = D;
  always
    @(posedge CK)
      qi <= next_state;
  initial
    qi <= 1'b0;
endmodule
