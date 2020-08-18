module do_not_parse_0(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule

/* Comments Outside
Of a Module 
*/
module test_module_0(G1,G2,G3,G4,G5,G17,G18,G19,G20,G21,G22);
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
  assign G22[1] = G1 & (G2 | 1'b1);
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
  assign G22[1] = G1 & (G2 | 1'b1);
  assign G21 = 1'b0;

endmodule


