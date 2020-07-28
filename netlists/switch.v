module SWITCH(in_0,in_1,out_0,out_1,key);
  input in_0,in_1;
  input key;
  output out_0,out_1;
  wire in_0,in_1;
  wire key;
  wire out_0,out_1;
  wire k_b,n_0,n_1,n_2,n_3;
  not NOT (k_b, key);
  or OR_0 (out_0, n_0, n_1);
  and AND0_0 (n_0, in_0, k_b);
  and AND1_0 (n_1, in_1, key);
  or OR_1 (out_1, n_2, n_3);
  and AND0_1 (n_2, in_0, key);
  and AND1_1 (n_3, in_1, k_b);
endmodule
