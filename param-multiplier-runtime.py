#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# param-multiplier-runtime.py — Cron-ready inference script
#
# Called by cron every 5 minutes to generate param-multipliers.json
# Output: JSON file read by dashboard API + sourced by trading bot
#
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════════════

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, "/home/overgon/jesse-research")

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
OUTPUT_JSON = WORKSPACE / "ml" / "param-multipliers.json"

# Import inference module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "pmi", "/home/overgon/jesse-research/param_multiplier_inference.py"
)
pmi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pmi)


def main():
    print("=== Param Multiplier Runtime Inference ===")

    # Get current multipliers for all coins
    multipliers = pmi.get_current_multipliers()

    # Load per-coin base config
    bots_dir = WORKSPACE / "crypto-bots"
    per_coin_path = bots_dir / "per-coin-config.env"
    base_config = pmi._parse_env_file(per_coin_path) if hasattr(pmi, "_parse_env_file") else {}

    # If pmi doesn't expose _parse_env_file, load it manually
    if not base_config:
        import re
        with open(per_coin_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                base_config[key.strip()] = val.strip()

    int_keys = {"TP1", "TP2", "TP3", "STOP_LOSS", "POSITION_SIZE"}
    bool_keys = {"ENABLED"}

    coin_names = ["BTC", "ETH", "BNB", "SOL", "ZEC", "XRP", "AVAX"]
    output = {
        "updatedAt": pd_ts_now_iso(),
        "coins": {},
    }

    for coin in coin_names:
        mults = multipliers.get(coin, {})

        # Get base config for this coin
        base = {}
        for k, v in base_config.items():
            if k.startswith(f"{coin}_") and "_" in k:
                field = k.split("_", 1)[1]
                if field in int_keys:
                    try:
                        base[field] = float(v)
                    except ValueError:
                        base[field] = v
                elif field in bool_keys:
                    base[field] = v.lower() in ("true", "1", "yes")
                else:
                    base[field] = v

        # Compute effective config (base × multiplier)
        eff = pmi.compute_effective_config(base, mults)

        output["coins"][coin] = {
            "multipliers": mults,
            "base_config": base,
            "effective_config": {
                k.replace("_eff", ""): v for k, v in eff.items()
            },
        }

        # Print summary
        tp1_base = base.get("TP1", 0)
        tp1_eff = eff.get("TP1_eff", tp1_base)
        print(f"  {coin}: TP1={tp1_base}×{mults.get('tp1_mult',1.0):.2f}={tp1_eff:.2f} "
              f"SL={base.get('STOP_LOSS',0)}×{mults.get('sl_mult',1.0):.2f}={eff.get('STOP_LOSS_eff',0):.2f} "
              f"SIZE={base.get('POSITION_SIZE',0)}×{mults.get('size_mult',1.0):.2f}={eff.get('POSITION_SIZE_eff',0):.2f}")

    # Write JSON output
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✅ Written: {OUTPUT_JSON}")
    print(f"   Coins: {list(output['coins'].keys())}")


def pd_ts_now_iso():
    import pandas as pd
    return pd.Timestamp.now(tz="America/Mexico_City").isoformat()


if __name__ == "__main__":
    main()
