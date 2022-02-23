// Benchmark "/storage/rpurdy/benchmarks/ISCAS/bench/c17" written by ABC on Tue Jun 30 14:50:35 2020

module assign_test (
    G1, G2, G3, G6, G7,
    G22, G23  );
  input  G1, G2, G3, G6, G7;
  output G22, G23;
  assign G22 = (~G1 & G2) | G3 | (G4 ^ ~G6 & (G2 | G3));
  assign G23 = G1 & G22;
endmodule


  // assign G23 = G1 ^ G2 ^ (G4 & G3 & ~G6);
