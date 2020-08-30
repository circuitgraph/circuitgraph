module do_not_parse_0(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule

/* Comments Outside
Of a Module 
*/
module test_correct_io(G1,G2,G3,G4,G5,G17,G18,G19,G20,G21,G22);
  // Comments Inside Module
  input G1,G2,G3,G4;
  /* Comments Inside Module */
  input [1:0] G5;
  output G17,G18,G19,G20,G21;
  output [1:0] G22;

  wire [1:0] G8;

  nand NAND2_0(G8[0],G1,G3);
  nor  NOR2_0(G17,G8[1],1'b1);
  and  AND2_0(G18,G2,G5[0]);
  xor  XOR2_0(G22[0],G5[1],G4);

  assign G8[1] = 1'b1;
  assign G19 = G1 & G2 & (G3 ^ G4);
  assign G20 = G17 ^ (G8[0] & G5[0]);
  assign G22[1] = G1 & (~G2 | 1'b1);
  assign G21 = 1'b0;

endmodule

module do_not_parse_1(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule

module test_module_1(
    input G1,
    input G2,
    input G3,
    input G4,
    input [1:0] G5,
    output G17,
    output G18,
    output G19,
    output G20,
    output G21,
    output [1:0] G22);
  
  wire [1:0] G8;

  nand NAND2_0(G8[0],G1,G3);
  nor  NOR2_0(G17,G8[1],1'b1);
  and  AND2_0(G18,G2,G5[0]);
  xor  XOR2_0(G22[0],G5[1],G4);

  assign G8[1] = 1'b1;
  assign G19 = G1 & G2 & (G3 ^ G4);
  assign G20 = G17 ^ (G8[0] & G5[0]);
  assign G22[1] = G1 & (~G2 | 1'b1);
  assign G21 = 1'b0;
endmodule

module test_module_2(clk, G0, G1, G17, G18);
    input clk, G0, G1;
    input [1:0] G2;
    output [1:0] G18;
    wire G3, G4, G5;

    fflopd DFF_0_Q_reg(.CK (clk), .D (G3), .Q (G4));
    and AND2_0(G3, G0, G1);
    and AND2_1(G18[1], G5, G2[1]);
    fflopd DFF_1_Q_reg(.CK (clk), .D(G2[0]), .Q(G5));
    fflopd DFF_2_Q_reg(.CK (clk), .D(G5), .Q(G18[0]));
endmodule

module test_module_3(
    clk,
    I0,
    \G0[0] ,
    \G1[1] ,
    \G2[0] ,
    \G3[0]
);
    input clk, \G0[0] ;
    input [1:0] I0, \G1[1] ;
    output \G2[0] ;
    output [2:0] \G3[0] ;

    wire \I1[0] ;

    buf b(\I1[0] , \I0[0] );
    nand n0(\G2[0] , \G0[0] , \G1[1] [1], I0[1]);
    nand n1(\G3[0] [0], \G0[0] , \G1[1] [0]);

    fflopd(.CK(clk), .D(\I1[0] ), .Q(\G3[0] [2]));

    assign \G3[0] [1] = \G0[0] & ~\G1[1] [1] | I0[0];

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

module test_module_4(
    clk,
    set,
    rst,
    a,
    b
);
    input clk, set, rst, a;
    output b;

    custom_flop(.clock(clk), .data_in(a), .data_out(b), .set(set), .reset(rst));
endmodule

module custom_flop(clock, set, reset, data_in, data_out);
  input clock, set, reset, data_in;
  output reg data_out;
  always@(posedge clock) begin
    if (reset)
      data_out <= 0;
    else if (set)
      data_out <= data_in;
  end
endmodule
