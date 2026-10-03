import importlib, os, sys

# Print exact .pth MAPPING
pth = "/usr/local/lib/python3.11/site-packages/__editable___jesse_3_2_3_finder.py"
if os.path.exists(pth):
    with open(pth) as f:
        for line in f:
            if "MAPPING" in line:
                print("MAPPING line:", line.strip())

# List the actual package dir name
import glob
pkg_dirs = glob.glob("/jesse-docker/jes*")
print("Package dirs:", pkg_dirs)

# Try each spelling
for name in ["jase", "jessie", "jessa", "jasse"]:
    try:
        m = importlib.import_module(name)
        print(f"{name}: OK -> {m.__file__}")
    except ModuleNotFoundError as e:
        print(f"{name}: FAIL ({e})")
