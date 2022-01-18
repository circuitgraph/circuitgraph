module test_blackbox_io(clk, i0, i1, o0);

    input clk, i0, i1;
    output o0;

    wire w0, w1;

    xor xor0(w0, i0, i1);
    ff ff0(.D(w0), .CK(clk), .Q(w1));
    not not0(o0, w1);
endmodule
