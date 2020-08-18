module mix(G1,G16,G17,G2,G3,G4,G5,G18,G19,G20,G21,G22,G23,G24,G25);
  input G1,G2,G3,G4;
  input [2:0] G5;
  output G16,G17,G18,G19,G20;
  output [2:0] G21, G22;
  output [4:0] G23;
  output G24,G25;

  wire G8,G9,G12,G15;

  nand NAND2_0(G8,G1,G3);
  nand NAND2_1(G9,G3,G4);
  nand NAND2_2(G12,G2,G9);
  nand NAND2_3(G15,G9,G5[0]);
  nand NAND2_4(G16,G8,G12);
  nand NAND2_5(G17,G12,G15);

  assign G21[0] = G17 ^ (G1 & G5);
  /* assign G24 = 1'b0; */
  /* assign G25 = G17 | 1'b1; */
  /* assign {G19, G20} = {G8 & G9, G12}; */

  /* assign G21 = {G1, G5[2], G3 ^ G4}; */
  /* assign G22[0] = G1 & G2; */
  /* nor NOR2_1(G22[1], G8, G12); */
  /* assign G22[2] = G22[0]; */
  /* assign G22[2] = G22[0]; */
  /* assign G23[0:2] = {G22[0:1], G12}; */
  /* assign G23[3:4] = G22[1:2]; */

endmodule


module do_not_parse(G2, G3);
    input G2;
    output G3;

    assign G2 = ~G3;
endmodule
