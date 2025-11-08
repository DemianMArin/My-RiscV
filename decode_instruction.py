#!/usr/bin/env python3
"""
RISC-V Instruction Decoder
Decodes 32-bit instruction strings based on encoding.json
"""

import json
import sys

def decode_instruction(inst_binary):
    """
    Decode a 32-bit binary instruction string

    Args:
        inst_binary: 32-bit binary string (e.g., "00000000010000000000000100000011")

    Returns:
        Dictionary with decoded instruction fields
    """
    if len(inst_binary) != 32:
        return {"error": f"Invalid instruction length: {len(inst_binary)} (expected 32)"}

    # Extract opcode (bits [6:0])
    opcode = inst_binary[-7:]

    # Load encoding data
    with open('encoding.json', 'r') as f:
        data = json.load(f)

    # Find matching instruction
    for inst in data['instruction_encodings']:
        fields = inst['fields']

        # Check if opcode matches
        if '6:0' in fields and fields['6:0'] == opcode:
            # For R-type and I-type, also check funct3
            if '14:12' in fields:
                funct3 = inst_binary[-15:-12]  # bits [14:12]
                if fields['14:12'] != funct3:
                    continue

            # For R-type, also check funct7
            if '31:27' in fields and fields['31:27'] != 'x':
                funct7_bits = inst_binary[0:5]  # bits [31:27]
                if fields['31:27'] != funct7_bits:
                    continue
                # Also check bits [26:25]
                if '26:25' in fields and fields['26:25'] != 'x':
                    bits_26_25 = inst_binary[5:7]
                    if fields['26:25'] != bits_26_25:
                        continue

            # Found matching instruction
            result = {
                'mnemonic': inst['mnemonic'],
                'format': inst['format'],
                'opcode': opcode,
                'binary': inst_binary
            }

            # Decode fields based on instruction type
            if inst['format'] == 'R-Type':
                result['rd'] = int(inst_binary[-12:-7], 2)
                result['funct3'] = inst_binary[-15:-12]
                result['rs1'] = int(inst_binary[-20:-15], 2)
                result['rs2'] = int(inst_binary[-25:-20], 2)
                result['funct7'] = inst_binary[0:7]

            elif inst['format'] in ['I-Type (Imm)', 'I-Type (Load)']:
                result['rd'] = int(inst_binary[-12:-7], 2)
                result['funct3'] = inst_binary[-15:-12]
                result['rs1'] = int(inst_binary[-20:-15], 2)
                # Sign-extend 12-bit immediate
                imm_bits = inst_binary[0:12]
                imm_val = int(imm_bits, 2)
                if imm_bits[0] == '1':  # negative
                    imm_val = imm_val - (1 << 12)
                result['imm'] = imm_val
                result['imm_binary'] = imm_bits

            elif inst['format'] == 'S-Type (Store)':
                result['funct3'] = inst_binary[-15:-12]
                result['rs1'] = int(inst_binary[-20:-15], 2)
                result['rs2'] = int(inst_binary[-25:-20], 2)
                # Reconstruct 12-bit immediate: imm[11:5] | imm[4:0]
                imm_11_5 = inst_binary[0:7]
                imm_4_0 = inst_binary[-12:-7]
                imm_bits = imm_11_5 + imm_4_0
                imm_val = int(imm_bits, 2)
                if imm_bits[0] == '1':  # negative
                    imm_val = imm_val - (1 << 12)
                result['imm'] = imm_val
                result['imm_binary'] = imm_bits

            elif inst['format'] == 'B-Type':
                result['funct3'] = inst_binary[-15:-12]
                result['rs1'] = int(inst_binary[-20:-15], 2)
                result['rs2'] = int(inst_binary[-25:-20], 2)
                # Reconstruct 13-bit immediate: imm[12] | imm[10:5] | imm[4:1] | imm[11] | 0
                imm_12 = inst_binary[0]
                imm_10_5 = inst_binary[1:7]
                imm_4_1 = inst_binary[-12:-8]
                imm_11 = inst_binary[-8]
                imm_bits = imm_12 + imm_11 + imm_10_5 + imm_4_1 + '0'
                imm_val = int(imm_bits, 2)
                if imm_bits[0] == '1':  # negative
                    imm_val = imm_val - (1 << 13)
                result['imm'] = imm_val
                result['imm_binary'] = imm_bits

            elif inst['format'] == 'J-Type':
                result['rd'] = int(inst_binary[-12:-7], 2)
                # Reconstruct 21-bit immediate: imm[20] | imm[10:1] | imm[11] | imm[19:12] | 0
                imm_20 = inst_binary[0]
                imm_19_12 = inst_binary[1:9]
                imm_11 = inst_binary[9]
                imm_10_1 = inst_binary[10:20]
                imm_bits = imm_20 + imm_19_12 + imm_11 + imm_10_1 + '0'
                imm_val = int(imm_bits, 2)
                if imm_bits[0] == '1':  # negative
                    imm_val = imm_val - (1 << 21)
                result['imm'] = imm_val
                result['imm_binary'] = imm_bits

            return result

    # Check for HALT
    if inst_binary == '1' * 32:
        return {
            'mnemonic': 'HALT',
            'format': 'Special',
            'opcode': opcode,
            'binary': inst_binary
        }

    return {"error": f"Unknown instruction with opcode: {opcode}"}


def format_instruction(decoded):
    """Format decoded instruction for display"""
    if 'error' in decoded:
        return f"ERROR: {decoded['error']}"

    result = f"{decoded['mnemonic']:6s} ({decoded['format']})"

    if 'rd' in decoded:
        result += f" rd=x{decoded['rd']}"
    if 'rs1' in decoded:
        result += f" rs1=x{decoded['rs1']}"
    if 'rs2' in decoded:
        result += f" rs2=x{decoded['rs2']}"
    if 'imm' in decoded:
        result += f" imm={decoded['imm']}"
        if decoded.get('imm_binary'):
            result += f" ({decoded['imm_binary']})"

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python decode_instruction.py <32-bit binary instruction>")
        print("Example: python decode_instruction.py 00000000010000000000000100000011")
        sys.exit(1)

    # Decode instruction from command line
    inst = sys.argv[1].strip()

    # Validate input
    if len(inst) != 32:
        print(f"ERROR: Expected 32 bits, got {len(inst)} bits")
        sys.exit(1)

    if not all(c in '01' for c in inst):
        print(f"ERROR: Invalid binary string (must contain only 0 and 1)")
        sys.exit(1)

    decoded = decode_instruction(inst)

    if 'error' in decoded:
        print(f"ERROR: {decoded['error']}")
        sys.exit(1)

    # Print formatted output
    print(f"Binary:    {inst}")
    print(f"Mnemonic:  {decoded['mnemonic']}")
    print(f"Format:    {decoded['format']}")
    print(f"Opcode:    {decoded['opcode']}")

    if 'rd' in decoded:
        print(f"rd:        x{decoded['rd']}")
    if 'rs1' in decoded:
        print(f"rs1:       x{decoded['rs1']}")
    if 'rs2' in decoded:
        print(f"rs2:       x{decoded['rs2']}")
    if 'imm' in decoded:
        print(f"imm:       {decoded['imm']} (binary: {decoded['imm_binary']})")
    if 'funct3' in decoded:
        print(f"funct3:    {decoded['funct3']}")
    if 'funct7' in decoded:
        print(f"funct7:    {decoded['funct7']}")
