module hd #(
	parameter WINPUT = 32,
	parameter HD = 32
)(in,out,key);

input [WINPUT-1:0] in, key;
output logic out;

assign out = ($countones(in ^ key)==HD);

endmodule

