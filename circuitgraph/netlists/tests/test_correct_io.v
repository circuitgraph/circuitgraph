module do_not_parse_0(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule

/* Comments Outside
Of a Module
*/
module test_correct_io(G1,G2,G3,G4,G5_0,G5_1,G17,G18,G19,G20,G21,G22_0,G22_1);
  // Comments Inside Module
  input G1,G2,G3,G4;
  /* Comments Inside Module */
  input G5_0,G5_1;
  output G17, G18,G19,G20,G21;
  output G22_0,
	  G22_1;

  wire G8_0,G8_1;

  nand NAND2_0 (G8_0,G1,G3);
  nor  NOR2_0( G17,G8_1,1'b1);
  and  AND2_0(G18,  G2,G5_0);
  xor  XOR2_0(G22_0,G5_1 ,G4);

  assign G8_1 = 1'b1;
  assign G19 = G1 & G2 & (G3 ^ G4);
  assign G20 = G17 ^ (G8_0 & G5_0);
  assign G22_1 = G1 & (~G2 | 1'b1);
  assign G21 = 1'b0;

endmodule

module do_not_parse_1(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule

module test_module_bb(clk, G0, G1, G2_0, G2_1, G18_0, G18_1);
    input clk, G0, G1;
    input G2_0,G2_1;
    output G18_0,G18_1;
    wire G3, G4, G5;

    ff DFF_0(.CK (clk), .D (G3), .Q (G4));
    and AND2_0(G3, G0, G1);
    and AND2_1(G18_1, G5, G2_1);
    ff DFF_1(.CK (clk), .D(G2_0), .Q(G5));
    ff DFF_2(.CK (clk), .D(G5), .Q(G18_0));
endmodule

