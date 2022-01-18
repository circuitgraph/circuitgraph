module test_blackbox_io(clk, i0, o0);

    input clk, i0;
    output o0;

    ff ff0(.D(i0), .CK(clk), .Q(o0));
endmodule
