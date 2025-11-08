import copy

from riscvmodel.code import decode, MachineDecodeError
from riscvmodel.isa import Instruction

from instructions import get_instruction_class, InstructionBase, ADDERBTYPE, ADDERJTYPE
from models import InsMem, DataMem, RegisterFile, State

# memory size, in reality, the memory size should be 2^32, but for this lab, for the space reason
# we keep it as this large number, but the memory is still 32-bit addressable.
MemSize = 1000


class Core(object):
    def __init__(self, ioDir: str, imem: InsMem, dmem: DataMem):
        self.myRF = RegisterFile(ioDir)
        self.cycle = 0
        self.halted = False
        self.ioDir = ioDir
        self.state = State()
        self.state.nop_init()
        self.nextState = State()
        self.nextState.nop_init()
        self.ext_imem: InsMem = imem
        self.ext_dmem: DataMem = dmem

    def calculate_performance_metrics(self):
        cpi = float(self.cycle) / self.state.IF.instruction_count
        ipc = 1 / cpi

        result_format = f"{self.stages} Core Performance Metrics-----------------------------\n" \
                        f"Number of cycles taken: {self.cycle}\n" \
                        f"Cycles per instruction: {cpi}\n" \
                        f"Instructions per cycle: {ipc}\n"

        write_mode = "w" if self.stages == "Single Stage" else "a"

        with open(self.ioDir[:-3] + "PerformanceMetrics_Result.txt", write_mode) as file:
            file.write(result_format)


class SingleStageCore(Core):
    def __init__(self, io_dir: str, imem: InsMem, dmem: DataMem):
        super(SingleStageCore, self).__init__(io_dir + "/SS_", imem, dmem)
        self.opFilePath = io_dir + "/StateResult_SS.txt"
        self.stages = "Single Stage"

    def step(self):
        # IF
        instruction_bytes = self.ext_imem.read_instr(self.state.IF.PC)
        if instruction_bytes == "1" * 32:
            self.nextState.IF.nop = True
        else:
            self.nextState.IF.PC += 4
            self.nextState.IF.instruction_count = self.nextState.IF.instruction_count + 1

        try:
            # ID
            instruction: Instruction = decode(int(instruction_bytes, 2))
            if instruction.mnemonic in ['beq', 'bne']:
                self.nextState.IF.PC = ADDERBTYPE(instruction, self.state, self.myRF).get_pc()
            elif instruction.mnemonic == 'jal':
                self.nextState.IF.PC = ADDERJTYPE(instruction, self.state, self.myRF).get_pc()
            else:
                instruction_ob: InstructionBase = get_instruction_class(instruction.mnemonic)(instruction,
                                                                                              self.ext_dmem, self.myRF,
                                                                                              self.state,
                                                                                              self.nextState)
                # Ex
                alu_result = instruction_ob.execute()
                # Load/Store (MEM)
                mem_result = instruction_ob.mem(alu_result=alu_result)
                # WB
                wb_result = instruction_ob.wb(mem_result=mem_result, alu_result=alu_result)
        except MachineDecodeError as e:
            if "{:08x}".format(e.word) == 'ffffffff':
                pass
            else:
                raise Exception("Invalid Instruction to Decode")
        # self.halted = True
        if self.state.IF.nop:
            self.nextState.IF.instruction_count = self.nextState.IF.instruction_count + 1
            self.halted = True

        self.myRF.output_rf(self.cycle)  # dump RF
        self.printState(self.nextState, self.cycle)  # print states after executing cycle 0, cycle 1, cycle 2 ...

        # The end of the cycle and updates the current state with the values calculated in this cycle
        self.state = copy.deepcopy(self.nextState)
        # self.nextState = copy.deepcopy(self.nextState)
        self.cycle += 1

    def printState(self, state, cycle):
        printstate = ["-" * 70 + "\n", "State after executing cycle: " + str(cycle) + "\n"]
        printstate.append("IF.PC: " + str(state.IF.PC) + "\n")
        printstate.append("IF.nop: " + str(state.IF.nop) + "\n")

        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.opFilePath, perm, encoding='utf-8') as wf:
            wf.writelines(printstate)


class FiveStageCore(Core):
    def __init__(self, ioDir, imem, dmem):
        super(FiveStageCore, self).__init__(ioDir + "/FS_", imem, dmem)
        self.opFilePath = ioDir + "/StateResult_FS.txt"
        self.stages = "Five Stage"

    def print_current_instruction(self, cycle, stage, instruction):
        if issubclass(type(instruction), Instruction):
            print(f"{cycle}\t{stage}\t{instruction}")
        else:
            if all([x in ["0", "1"] for x in instruction]):
                try:
                    print(f"{cycle}\t{stage}\t{decode(int(instruction, 2))}")
                except MachineDecodeError as e:
                    print(f"{cycle}\t{stage}\tHalt")
            else:
                print(f"{cycle}\t{stage}\t{instruction}")

    def step(self):
        # Your implementation

        # --------------------- WB stage ----------------------
        if not self.state.WB.nop:
            self.print_current_instruction(self.cycle, "WB", self.state.WB.instruction_ob.instruction)

            self.state, self.nextState, self.ext_dmem, self.myRF, _ = self.state.WB.instruction_ob.wb(
                state=self.state,
                nextState=self.nextState,
                registers=self.myRF,
                memory=self.ext_dmem)
        else:
            self.print_current_instruction(self.cycle, "WB", "nop")

        # --------------------- MEM stage ---------------------
        if not self.state.MEM.nop:
            self.print_current_instruction(self.cycle, "MEM", self.state.MEM.instruction_ob.instruction)

            self.state, self.nextState, self.ext_dmem, self.myRF, _ = self.state.MEM.instruction_ob.mem(
                state=self.state,
                nextState=self.nextState,
                registers=self.myRF,
                memory=self.ext_dmem)
        else:
            # MEM nop - retain WB values from previous cycle
            from models import WBState
            wb_state = WBState()
            wb_state.nop = True
            # Retain values from current WB (previous cycle's values)
            wb_state.store_data = self.state.WB.store_data
            wb_state.write_register_addr = self.state.WB.write_register_addr
            wb_state.rs1 = self.state.WB.rs1
            wb_state.rs2 = self.state.WB.rs2
            wb_state.write_back_enable = self.state.WB.write_back_enable
            self.nextState.WB = wb_state
            self.print_current_instruction(self.cycle, "MEM", "nop")

        # --------------------- EX stage ----------------------
        if not self.state.EX.nop:
            self.print_current_instruction(self.cycle, "EX", self.state.EX.instruction_ob.instruction)

            self.state, self.nextState, self.ext_dmem, self.myRF, _ = self.state.EX.instruction_ob.execute(
                state=self.state, nextState=self.nextState, registers=self.myRF, memory=self.ext_dmem)
        else:
            # NOP in EX: retain MEM control signals from previous cycle
            from models import MEMState
            mem_state = MEMState()
            mem_state.nop = True
            # Retain control signals from current MEM (previous cycle's values)
            mem_state.write_register_addr = self.state.MEM.write_register_addr
            mem_state.rs1 = self.state.MEM.rs1
            mem_state.rs2 = self.state.MEM.rs2
            mem_state.read_data_mem = self.state.MEM.read_data_mem
            mem_state.write_data_mem = self.state.MEM.write_data_mem
            mem_state.write_back_enable = self.state.MEM.write_back_enable
            # Data fields retain previous values too
            mem_state.alu_result = self.state.MEM.alu_result
            mem_state.store_data = self.state.MEM.store_data
            mem_state.data_address = self.state.MEM.data_address
            self.nextState.MEM = mem_state
            self.print_current_instruction(self.cycle, "EX", "nop")

        # --------------------- ID stage ----------------------
        # Always decode if there's a valid instruction, even if ID.nop is True
        # This allows instructions to continue flowing through pipeline after HALT
        if self.state.ID.instruction_bytes and self.state.ID.instruction_bytes != "":
            self.print_current_instruction(self.cycle, "ID", self.state.ID.instruction_bytes)
            try:
                instruction = decode(int(self.state.ID.instruction_bytes, 2))
                instruction_ob: InstructionBase = get_instruction_class(instruction.mnemonic)(instruction,
                                                                                              self.ext_dmem,
                                                                                              self.myRF,
                                                                                              self.state,
                                                                                              self.nextState)
                self.state, self.nextState, self.ext_dmem, self.myRF, _ = instruction_ob.decode(state=self.state,
                                                                                                nextState=self.nextState,
                                                                                                registers=self.myRF,
                                                                                                memory=self.ext_dmem)
                # If ID was marked as nop, propagate nop to EX
                if self.state.ID.nop:
                    self.nextState.EX.nop = True
            except MachineDecodeError as e:
                if "{:08x}".format(e.word) == 'ffffffff':
                    self.nextState.ID.halt = True
                else:
                    raise Exception("Invalid Instruction to Decode")
        else:
            # No valid instruction - create EX NOP that retains previous cycle's values
            from models import EXState
            ex_state = EXState()
            ex_state.nop = True
            ex_state.instr_binary = self.state.EX.instr_binary
            ex_state.operand1 = self.state.EX.operand1
            ex_state.operand2 = self.state.EX.operand2
            ex_state.destination_register = self.state.EX.destination_register
            ex_state.rs1 = self.state.EX.rs1
            ex_state.rs2 = self.state.EX.rs2
            ex_state.imm = self.state.EX.imm
            ex_state.is_i_type = self.state.EX.is_i_type
            ex_state.read_data_mem = self.state.EX.read_data_mem
            ex_state.write_data_mem = self.state.EX.write_data_mem
            ex_state.write_back_enable = self.state.EX.write_back_enable
            self.nextState.EX = ex_state
            self.print_current_instruction(self.cycle, "ID", "nop")

        # --------------------- IF stage ----------------------
        if not self.state.IF.nop:
            instruction_bytes = self.ext_imem.read_instr(self.state.IF.PC)
            if instruction_bytes == "1" * 32:
                # HALT detected - don't update ID with HALT, preserve current ID instruction
                self.nextState.ID.nop = True
                self.nextState.IF.nop = True
                self.nextState.ID.instruction_bytes = self.state.ID.instruction_bytes
                self.print_current_instruction(self.cycle, "IF", "Halt")
            else:
                # Normal instruction - update ID
                self.nextState.ID.instruction_bytes = instruction_bytes
                self.nextState.ID.nop = False
                self.nextState.IF.PC = self.state.IF.PC + 4
                self.nextState.IF.instruction_count = self.nextState.IF.instruction_count + 1
                self.print_current_instruction(self.cycle, "IF", instruction_bytes)
        else:
            # IF is nop - preserve ID instruction from previous cycle
            from models import IDState
            id_state = IDState()
            id_state.nop = True
            id_state.instruction_bytes = self.state.ID.instruction_bytes
            self.nextState.ID = id_state
            self.print_current_instruction(self.cycle, "IF", "nop")

        if (self.state.IF.halt or self.state.IF.nop) and (self.state.ID.halt or self.state.ID.nop) and (
                self.state.EX.halt or self.state.EX.nop) and (self.state.MEM.halt or self.state.MEM.nop) and (
                self.state.WB.halt or self.state.WB.nop):
            self.nextState.IF.instruction_count = self.state.IF.instruction_count + 1
            self.halted = True
            self.print_current_instruction(self.cycle, "--", "End of Simulation")

        self.myRF.output_rf(self.cycle)  # dump RF
        self.printState(self.nextState, self.cycle)  # print states after executing cycle 0, cycle 1, cycle 2 ...

        self.state = copy.deepcopy(self.nextState)
        self.cycle += 1

    def printState(self, state, cycle):
        # Format to match desired output - single newline after cycle, not double
        print_state = "-" * 70 + "\n" + "State after executing cycle: " + str(cycle) + "\n"
        print_state += str(state) + "\n"

        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.opFilePath, perm) as wf:
            wf.write(print_state)


if __name__ == "__main__":
    pass
