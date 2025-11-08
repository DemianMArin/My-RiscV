#!/usr/bin/env python3

# Compare two state files line by line and show differences with context

with open('submissions/Data/StateResult_FS.txt', 'r') as f1:
    generated = f1.readlines()

with open('submissions/Test/T0/Result/StateResult_FS.txt', 'r') as f2:
    expected = f2.readlines()

print("Differences found:")
print("=" * 80)

current_cycle = -1
for i, (line1, line2) in enumerate(zip(generated, expected)):
    if 'State after executing cycle:' in line1:
        current_cycle = int(line1.split(':')[-1].strip())

    if line1.strip() != line2.strip():
        print(f"\nCycle {current_cycle}, Line {i+1}:")
        print(f"  Generated: {line1.strip()}")
        print(f"  Expected:  {line2.strip()}")

print("\n" + "=" * 80)
print("Comparison complete")
