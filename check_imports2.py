import re, importlib

pth = "/usr/local/lib/python3.11/site-packages/__editable___jesse_3_2_3_finder.py"
with open(pth) as f:
    content = f.read()

m = re.search(r"MAPPING.*=\s*\{'([^']+)':", content)
if m:
    import_name = m.group(1)
    print(f"Exact import name from .pth: {repr(import_name)} (len={len(import_name)})")
    try:
        mod = importlib.import_module(import_name)
        print(f"import {import_name}: OK -> {mod.__file__}")
        # Test submodules
        bt = importlib.import_module(f"{import_name}.research.backtest")
        print(f".research.backtest: OK")
        routes = importlib.import_module(f"{import_name}.routes")
        print(f".routes: OK")
        candles = importlib.import_module(f"{import_name}.research")
        print(f".research: OK")
    except Exception as e:
        print(f"import {import_name}: FAIL -> {e}")
else:
    print("Could not extract MAPPING key")
    # Fallback: try common spellings
    for name in ["jese", "jessie", "jessie", "jesse"]:
        try:
            mod = importlib.import_module(name)
            print(f"  {name}: OK -> {mod.__file__}")
        except ModuleNotFoundError:
            print(f"  {name}: FAIL")
