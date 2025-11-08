import json

from bitstring import BitArray


# TODO: set nop default to false and handle it in init for core class
class InsMem(object):

    def __init__(self, name, io_dir, **kwargs):
        self.id = name

        if "ioTest" not in kwargs:
            input_file_path = io_dir
        else:
            input_file_path = kwargs["ioTest"] + f"/TC{kwargs['tc']}"

        print(input_file_path)

        with open(input_file_path + "/imem.txt") as im:
            self.IMem = [data.replace("\n", "") for data in im.readlines()]

    def read_instr(self, read_address: int):
        # DONE: Handle word addressing - use nearest lower multiple for 4 for address = x - x % 4
        read_address = read_address - read_address % 4
        if len(self.IMem) < read_address + 4:
            raise Exception("Instruction MEM - Out of bound access")
        return "".join(self.IMem[read_address: read_address + 4])


class DataMem(object):
    def __init__(self, name, io_dir, **kwargs):
        self.id = name
        self.io_dir = io_dir

        if "ioTest" not in kwargs:
            input_file_path = io_dir
        else:
            input_file_path = kwargs["ioTest"] + f"/TC{kwargs['tc']}"

        with open(input_file_path + "/dmem.txt") as dm:
            self.DMem = [data.replace("\n", "") for data in dm.readlines()]
            self.DMem += ["0" * 8] * (1000 - len(self.DMem))

    def read_data(self, read_address: int) -> int:
        # read data memory
        # return 32-bit signed int value

        # DONE: Handle word addressing - use nearest lower multiple for 4 for address = x - x % 4
        read_address = read_address - read_address % 4
        if len(self.DMem) < read_address + 4:
            raise Exception("Data MEM - Out of bound access")
        return BitArray(bin="".join(self.DMem[read_address: read_address + 4])).int32

    def write_data_mem(self, address: int, write_data: int):
        # write data into byte addressable memory
        # Assuming data as 32 bit signed integer

        # Converting from int to bin

        # DONE: Handle word addressing - use nearest lower multiple for 4 for address = x - x % 4
        address = address - address % 4
        write_data = '{:032b}'.format(write_data & 0xffffffff)

        left, right, zeroes = [], [], []

        if address <= len(self.DMem):
            left = self.DMem[:address]
        else:
            left = self.DMem
            zeroes = ["0" * 8] * (address - len(self.DMem))
        if address + 4 <= len(self.DMem):
            right = self.DMem[address + 4:]

        self.DMem = left + zeroes + [write_data[i: i + 8] for i in range(0, 32, 8)] + right

    def output_data_mem(self):
        if self.id == 'SS':
            res_path = self.io_dir + "/" + self.id + "_DMEMResult.txt"
        else:
            res_path = self.io_dir + "/" + self.id + "_DMEMResult.txt"
        with open(res_path, "w") as rp:
            rp.writelines([str(data) + "\n" for data in self.DMem])


class RegisterFile(object):
    def __init__(self, io_dir):
        self.output_file = io_dir + "RFResult.txt"
        self.registers = [0x0 for _ in range(32)]

    def read_rf(self, reg_addr: int) -> int:
        return self.registers[reg_addr]

    def write_rf(self, reg_addr: int, wrt_reg_data: int):
        if reg_addr != 0:
            self.registers[reg_addr] = wrt_reg_data

    def output_rf(self, cycle):
        op = ["State of RF after executing cycle:\t" + str(cycle) + "\n"]
        op.extend(['{:032b}'.format(val & 0xffffffff) + "\n" for val in self.registers])
        if cycle == 0:
            perm = "w"
        else:
            perm = "a"
        with open(self.output_file, perm) as file:
            file.writelines(op)


class IntermediateState:

    def __init__(self):
        pass

    def set_attributes(self, **kwargs):
        self.__dict__.update(kwargs)


class IFState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.PC: int = 0  # Program Counter
        self.instruction_count: int = 0  # count of instructions fetched - used for performance metrics
        self.halt: bool = False  # Flag - identify end of program
        super(IFState, self).__init__()

    def __str__(self):
        # Format for desired output - only show nop and PC
        return f"IF.nop: {str(self.nop)}\nIF.PC: {self.PC}"


class IDState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.instruction_bytes: str = ""  # Binary Instruction string
        # self.instruction_ob = None  # Decoded InstructionBase object
        self.halt: bool = False  # Flag - identify end of program
        super(IDState, self).__init__()

    def __str__(self):
        # Format for desired output - rename instruction_bytes to Instr
        return f"ID.nop: {str(self.nop)}\nID.Instr: {self.instruction_bytes}"


class EXState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.instr_binary: str = ""  # 32-bit binary instruction string
        self.operand1: int = 0  # operand 1 for execute
        self.operand2: int = 0  # operand 2 for execute - can be rs2 or imm or forwarded data
        self.store_data: int = 0  # sw data - result of alu
        self.destination_register: int = 0  # destination register - rd
        self.rs1: int = 0  # source register 1 address
        self.rs2: int = 0  # source register 2 address
        self.imm: int = 0  # immediate value (for I, S, B, J type instructions)
        self.is_i_type: int = 0  # Flag: 1 for I-type instructions, 0 for R-type
        # self.alu_operation: str = None  # not required for now
        self.read_data_mem: bool = False  # Flag - identify if we need to read from mem (MEM Stage)
        self.write_data_mem: bool = False  # Flag - identify if we need to write to mem (MEM Stage)
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(EXState, self).__init__()

    def __str__(self):
        # Format for desired output
        # Always use binary instruction string (preserve even when nop for stalled instructions)
        instr_str = self.instr_binary

        # Format operands as 32-bit binary strings
        read_data1 = '{:032b}'.format(self.operand1 & 0xffffffff)
        read_data2 = '{:032b}'.format(self.operand2 & 0xffffffff)

        # Format immediate based on instruction type
        if self.instr_binary == "":
            imm = '{:032b}'.format(self.imm & 0xffffffff)
        else:
            # Extract opcode (bits [6:0]) to determine instruction type
            opcode = self.instr_binary[-7:] if len(self.instr_binary) >= 7 else "0000000"
            if opcode == "1100011":  # Branch instructions (BEQ, BNE, etc.)
                imm = '{:013b}'.format(self.imm & 0x1fff)  # 13 bits for branches
            elif opcode == "1101111":  # JAL instruction
                imm = '{:021b}'.format(self.imm & 0x1fffff)  # 21 bits for JAL
            else:  # I-type, R-type, S-type, etc.
                imm = '{:012b}'.format(self.imm & 0xfff)  # 12 bits

        # Format register addresses as 5-bit binary strings
        rs = '{:05b}'.format(self.rs1 & 0x1f)
        rt = '{:05b}'.format(self.rs2 & 0x1f)

        # Wrt_reg_addr formatting:
        # - 5 bits when no instruction OR (nop=False AND wrt_enable=True)
        # - 6 bits otherwise (stalled instruction or non-writeback instruction)
        if self.instr_binary == "" or (not self.nop and self.write_back_enable):
            wrt_reg_addr = '{:05b}'.format(self.destination_register & 0x1f)
        else:
            wrt_reg_addr = '{:06b}'.format(self.destination_register & 0x3f)

        # Convert booleans to integers
        rd_mem = 1 if self.read_data_mem else 0
        wrt_mem = 1 if self.write_data_mem else 0
        alu_op = "00"  # Placeholder for now
        wrt_enable = 1 if self.write_back_enable else 0

        return f"EX.nop: {str(self.nop)}\n" \
               f"EX.instr: {instr_str}\n" \
               f"EX.Read_data1: {read_data1}\n" \
               f"EX.Read_data2: {read_data2}\n" \
               f"EX.Imm: {imm}\n" \
               f"EX.Rs: {rs}\n" \
               f"EX.Rt: {rt}\n" \
               f"EX.Wrt_reg_addr: {wrt_reg_addr}\n" \
               f"EX.is_I_type: {self.is_i_type}\n" \
               f"EX.rd_mem: {rd_mem}\n" \
               f"EX.wrt_mem: {wrt_mem}\n" \
               f"EX.alu_op: {alu_op}\n" \
               f"EX.wrt_enable: {wrt_enable}"


class MEMState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.alu_result: int = 0  # ALU result from EX stage
        self.data_address: int = 0  # address for read / write DMEM operation
        self.store_data: int = 0  # data to be written to MEM for SW instruction or passed to WB
        self.write_register_addr: int = 0  # register to load data from MEM
        self.rs1: int = 0  # source register 1 address (propagated from EX)
        self.rs2: int = 0  # source register 2 address (propagated from EX)
        self.read_data_mem: bool = False  # Flag - identify if we need to read from mem (MEM Stage)
        self.write_data_mem: bool = False  # Flag - identify if we need to write to mem (MEM Stage)
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(MEMState, self).__init__()

    def __str__(self):
        # Format for desired output
        # Use actual alu_result field
        alu_result = '{:032b}'.format(self.alu_result & 0xffffffff)
        store_data = '{:032b}'.format(self.store_data & 0xffffffff)

        # Format register addresses as 5-bit binary strings - NOW USING ACTUAL VALUES
        rs = '{:05b}'.format(self.rs1 & 0x1f)
        rt = '{:05b}'.format(self.rs2 & 0x1f)
        wrt_reg_addr = '{:05b}'.format(self.write_register_addr & 0x1f)

        # Convert booleans to integers
        rd_mem = 1 if self.read_data_mem else 0
        wrt_mem = 1 if self.write_data_mem else 0
        wrt_enable = 1 if self.write_back_enable else 0

        return f"MEM.nop: {str(self.nop)}\n" \
               f"MEM.ALUresult: {alu_result}\n" \
               f"MEM.Store_data: {store_data}\n" \
               f"MEM.Rs: {rs}\n" \
               f"MEM.Rt: {rt}\n" \
               f"MEM.Wrt_reg_addr: {wrt_reg_addr}\n" \
               f"MEM.rd_mem: {rd_mem}\n" \
               f"MEM.wrt_mem: {wrt_mem}\n" \
               f"MEM.wrt_enable: {wrt_enable}"


class WBState(IntermediateState):

    def __init__(self):
        self.nop = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.store_data: int = 0  # data to be written to MEM for SW instruction
        self.write_register_addr: int = 0  # register to load data from MEM
        self.rs1: int = 0  # source register 1 address (propagated from MEM)
        self.rs2: int = 0  # source register 2 address (propagated from MEM)
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(WBState, self).__init__()

    def __str__(self):
        # Format for desired output
        wrt_data = '{:032b}'.format(self.store_data & 0xffffffff)

        # Format register addresses as 5-bit binary strings - NOW USING ACTUAL VALUES
        rs = '{:05b}'.format(self.rs1 & 0x1f)
        rt = '{:05b}'.format(self.rs2 & 0x1f)
        wrt_reg_addr = '{:05b}'.format(self.write_register_addr & 0x1f)

        # Convert booleans to integers
        wrt_enable = 1 if self.write_back_enable else 0

        return f"WB.nop: {str(self.nop)}\n" \
               f"WB.Wrt_data: {wrt_data}\n" \
               f"WB.Rs: {rs}\n" \
               f"WB.Rt: {rt}\n" \
               f"WB.Wrt_reg_addr: {wrt_reg_addr}\n" \
               f"WB.wrt_enable: {wrt_enable}"


class State(object):

    def __init__(self):
        self.IF: IFState = IFState()

        self.ID = IDState()

        self.EX = EXState()

        self.MEM = MEMState()

        self.WB = WBState()

    def nop_init(self):
        self.IF.nop = False
        self.ID.nop = True
        self.EX.nop = True
        self.MEM.nop = True
        self.WB.nop = True

    def __str__(self):
        # DONE: update __str__ to make use of individual State objects
        # No blank lines between stages - just newlines between them
        return "\n".join([str(self.IF), str(self.ID), str(self.EX), str(self.MEM), str(self.WB)])
