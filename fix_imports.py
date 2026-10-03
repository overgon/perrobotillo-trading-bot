#!/usr/bin/env python3
"""Fix issue #44: replace wrong 'jessie' import with correct namespace name in fase5_train.py.

The correct import name is extracted from the editable install .pth file,
so we never have to spell it correctly by hand.
"""
import re, os

TARGET = "/home/overgon/jesse-research/fase5_train.py"

# 1. Extract the EXACT import name from the editable .pth finder
pth = None
for candidate in [
    "/usr/local/lib/python3.11/site-packages/__editable___jesse_3_2_3_finder.py",
]:
    if os.path.exists(candidate):
        pth = candidate
        break

if not pth:
    # Try finding it inside the container
    import subprocess, glob
    patterns = [
        "/usr/local/lib/python*/site-packages/__editable__*jesse*finder.py",
    ]
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            pth = matches[0]
            break

if not pth:
    print("ERROR: Could not find editable .pth finder file")
    raise SystemExit(1)

print(f"Using .pth: {pth}")
with open(pth) as f:
    content = f.read()

m = re.search(r"MAPPING.*=\s*\{'([^']+)':", content)
if not m:
    print("ERROR: Could not extract MAPPING key")
    raise SystemExit(1)

correct_name = m.group(1)
print(f"Correct import name (len={len(correct_name)}): {repr(correct_name)}")

# 2. Read fase5_train.py and replace 'jessie' with correct name
with open(TARGET) as f:
    file_content = f.read()

count = file_content.count("jessie")
print(f"Found 'jessie' occurrences in fase5_train.py: {count}")

new_content = file_content.replace("jessie", correct_name)

if new_content != file_content:
    with open(TARGET, "w") as f:
        f.write(new_content)
    print(f"✅ Replaced {count} occurrence(s) of 'jessie' → '{correct_name}'")
else:
    print("⚠️ No changes made (strings identical?)")

# 3. Verify
with open(TARGET) as f:
    verify = f.read()
remaining = verify.count("jessie")
new_count = verify.count(correct_name)
print(f"Verification: 'jessie' remaining={remaining}, '{correct_name}' count={new_count}")
