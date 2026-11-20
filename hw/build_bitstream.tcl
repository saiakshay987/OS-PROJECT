# run from repo root: vivado -mode batch -source hw/build_bitstream.tcl -tclargs m0
set m [lindex $argv 0]
file mkdir hw/bit hw/xsa
create_project ids_$m hw/vivado/ids_$m -part xc7z020clg400-1 -force
set_property ip_repo_paths hw/hls/build/$m/proj_$m/sol1/impl/ip [current_project]
update_ip_catalog
create_bd_design "bd"
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 ps7
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR"} [get_bd_cells ps7]
create_bd_cell -type ip -vlnv xilinx.com:hls:qmlp_$m:1.0 qmlp_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk "Auto"} [get_bd_intf_pins qmlp_0/s_axi_ctrl]
assign_bd_address
validate_bd_design
make_wrapper -files [get_files bd.bd] -top -import
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
open_run impl_1
report_utilization -file hw/reports/${m}_impl_util.rpt
report_timing_summary -file hw/reports/${m}_impl_timing.rpt
write_hw_platform -fixed -include_bit -force hw/xsa/ids_$m.xsa
file copy -force hw/vivado/ids_$m/ids_$m.runs/impl_1/bd_wrapper.bit hw/bit/$m.bit
