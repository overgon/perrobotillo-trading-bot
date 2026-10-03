#!/usr/bin/env python3
"""Fix: replace 'jessie' with correct import name in fase5_train.py inside container."""
import re

# 1. Get correct import name from .pth
pth = "/usr/local/lib/python3.11/site-packages/__editable___jesse_3_2_3_finder.py"
with open(pth) as f:
    content = f.read()

# Match: {'<name>': '/jesse-docker/<name>', ...}
m = re.search(r"\{'([^']+)':\s*'/jesse-docker/", content)
if not m:
    m = re.search(r'\{("[^"]+"|\'[^\']+\'):\s*"/jesse-docker/', content)
    if m:
        correct = m.group(1).strip('"\'')
    else:
        raise SystemExit("ERROR: could not extract import name")

correct = m.group(1)
print(f"Correct import name (len={len(correct)}): {repr(correct)}")

# 2. Read fase5_train.py (at /home inside container)
target = "/home/fase5_train.py"
with open(target) as f:
    text = f.read()

count = text.count("jessie")
print(f"'jessie' occurrences before: {count}")

# 3. Replace
new_text = text.replace("jessie", correct)
with open(target, "w") as f:
    f.write(new_text)

# 4. Verify
with open(target) as f:
    verify = f.read()
print(f"'jessie' remaining: {verify.count('jessie')}")
print(f"'{correct}' occurrences: {verify.count(correct)}")

# Show the fixed import lines
for i, line in enumerate(verify.splitlines(), 1):
    if "research" in line and "backtest" in line or ("routes" in line and "import" in line):
        print(f"  L{i}: {line}")
