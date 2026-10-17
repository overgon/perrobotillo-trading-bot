#!/usr/bin/env python3
"""Generate bull market config and comparison from Optuna results."""
import json, os

DATA_DIR = os.path.expanduser("~/.openclaw/workspace/research")
CONFIG_PATH = os.path.expanduser("~/.openclaw/workspace/crypto-bots/per-coin-config.env")
BULL_PATH = os.path.expanduser("~/.openclaw/workspace/crypto-bots/per-coin-config-bull.env")

with open(os.path.join(DATA_DIR, "optuna_optimize_all_1h_180d_bull.json")) as f:
    bull = json.load(f)

current = {}
with open(CONFIG_PATH) as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            coin = key.split('_')[0]
            if coin not in current:
                current[coin] = {}
            current[coin][key] = val

coins = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

FIELD_MAP = {
    'tp1_percent': 'TP1',
    'tp2_percent': 'TP2',
    'tp3_percent': 'TP3',
    'stop_loss_percent': 'STOP_LOSS',
    'position_size_percent': 'POSITION_SIZE',
    'ml_min_confidence': 'ML_MIN_CONFIDENCE',
}

bull_lines = [
    "# Per-Coin Strategy Configuration — BULL MARKET (2023-2024 Optimized)",
    "# Generated from optuna_optimize_all_1h_180d_bull.json (25 trials per coin)",
    "# Data period: 2023-01-01 to 2025-01-20 (18,000 candles x coin)",
    "# Sharpe range: 1.67 (XRP) to 4.81 (BTC) — ALL POSITIVE",
    "# DO NOT USE in bear/lateral markets. Switch via regime detector.",
    "# Overrides dynamic-config.env per coin",
    ""
]

comparison = ["# Comparison: Current (Bear/Lateral) vs Bull Market Optimized HPs\n"]
comparison.append("| Coin | Field | Current | Bull Opt | Δ |")
comparison.append("|------|-------|---------|----------|---|")

for coin in coins:
    if coin not in bull:
        continue
    p = bull[coin]['best_params']
    m = bull[coin]['best_trial_metrics']
    cur = current.get(coin, {})

    bull_lines.append(f"# {coin} — Sharpe: {bull[coin]['best_value']:.2f} | Trades: {m['total_trades']} | Win%: {m['win_rate']:.1f} | PnL: ${m['net_profit']:.0f}")
    for json_key, field_name in FIELD_MAP.items():
        cfg_key = f"{coin}_{field_name}"
        val = p[json_key]
        if field_name == 'ML_MIN_CONFIDENCE':
            formatted = f"{val:.0f}"
        else:
            formatted = f"{val:.2f}"
        bull_lines.append(f"{cfg_key}={formatted}")

    bull_lines.append(f"{coin}_MAX_SLOTS={cur.get(f'{coin}_MAX_SLOTS', '3')}")
    bull_lines.append(f"{coin}_ENABLED={cur.get(f'{coin}_ENABLED', 'true')}")
    bull_lines.append("")

    for json_key, field_name in FIELD_MAP.items():
        cfg_key = f"{coin}_{field_name}"
        val = p[json_key]
        new_val = f"{val:.0f}" if field_name == 'ML_MIN_CONFIDENCE' else f"{val:.2f}"
        cur_val = cur.get(cfg_key, '?')
        delta = ""
        if cur_val != '?':
            cv = float(cur_val)
            nv = float(new_val)
            delta = "↑" if nv > cv else ("↓" if nv < cv else "→")
        comparison.append(f"| {coin} | {field_name} | {cur_val} | {new_val} | {delta} |")

with open(BULL_PATH, 'w') as f:
    f.write('\n'.join(bull_lines) + '\n')

comp_path = os.path.join(DATA_DIR, "config_comparison_current_vs_bull.md")
with open(comp_path, 'w') as f:
    f.write('\n'.join(comparison) + '\n')

print(f"✅ Bull config: {BULL_PATH}")
print(f"✅ Comparison: {comp_path}")
print(f"\n--- Bull config preview ---")
with open(BULL_PATH) as f:
    lines = f.readlines()
    for line in lines[:18]:
        print(line, end='')
print("\n--- Comparison table ---")
with open(comp_path) as f:
    print(f.read())
