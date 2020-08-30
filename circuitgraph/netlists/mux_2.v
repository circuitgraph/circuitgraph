module mux_2(in_0,in_1,out,sel);
  input in_0,in_1;
  input sel;
  output out;
  wire in_0,in_1;
  wire sel,sel_b;
  wire n_0,n_1;
  wire out;
  or OR (out, n_0, n_1);
  and AND0 (n_0, in_0, sel_b);
  and AND1 (n_1, in_1, sel);
  not NOT0 (sel_b, sel);
endmodule
