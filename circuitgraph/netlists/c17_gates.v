module c17_gates(G1,G16,G17,G2,G3,G4,G5);
input G1,G2,G3,G4,G5;
output G16,G17;

  wire G8,G9,G12,G15;

  nand NAND2_0(G8,G1,G3);
  nand NAND2_1(G9,G3,G4);
  nand NAND2_2(G12,G2,G9);
  nand NAND2_3(G15,G9,G5);
  nand NAND2_4(G16,G8,G12);
  nand NAND2_5(G17,G12,G15);

endmodule

