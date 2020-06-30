// Benchmark "/storage/rpurdy/benchmarks/ISCAS/bench/c17" written by ABC on Tue Jun 30 14:50:35 2020

module c17 ( 
    G1, G2, G3, G6, G7,
    G22, G23  );
  input  G1, G2, G3, G6, G7;
  output G22, G23;
  wire G10, G11, G16, G19;
  assign G10 = ~G1 | ~G3;
  assign G11 = ~G3 | ~G6;
  assign G16 = ~G2 | ~G11;
  assign G19 = ~G11 | ~G7;
  assign G22 = ~G10 | ~G16;
  assign G23 = ~G16 | ~G19;
endmodule


