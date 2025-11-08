
  1. EX.instr: Shows instruction object string (not binary like test)
  2. EX.is_I_type: Still 0 (needs implementation)
  3. EX.alu_op: Still 00 (needs implementation)
  4. MEM.ALUresult: Using data_address (may not be correct for all instructions)
  5. MEM.Store_data: May not be correct for all cases
  6. WB.Wrt_data: May not be correct for all cases

Compare-Object (Get-Content .\submissions\Data\StateResult_FS.txt) (Get-Content .\submissions\Test\T0\Result\StateResult_FS.txt)

The simulator must be able to deal with two types of hazards.
1. RAW Hazards: RAW hazards are dealt with using either only forwarding (if possible) or, if not,
using stalling + forwarding. Use EX-ID forwarding and MEM-ID forwarding appropriately.
2. Control Flow Hazards: The branch conditions are resolved in the ID/RF stage of the pipeline.

@submissions\Test\T0\Result\StateResult_FS.txt  and @submissions\Data\StateResult_FS.txt
