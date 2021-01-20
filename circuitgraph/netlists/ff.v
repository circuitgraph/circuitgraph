
module ff(CK, D, Q);
	input CK, D;
	output Q;
	wire CK, D;
	wire Q;
	wire next_state;
	reg  qi;
	assign #1 Q = qi;
	assign next_state = D;
	always
	@(posedge CK)
	qi <= next_state;
	initial
	  qi <= 1'b0;
endmodule
