#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# CI GATE — backtest regression detector (Issue #66)
#
# Verifica que un cambio no regresione la estrategia:
#   - Sharpe Δ ≥ -0.3
#   - PnL drop ≤ 15%
#   - win rate ≥ 40%
# Salida: 0 = pass, 1 = regression, 2 = error
# Muestra un JSON con el resultado para los CI.
# ═══════════════════════════════════════════════════════════════════════════

import json
import sys

# Límites de regresión (CI)
SHARPE_DELTA_MIN = -0.3      # Sharpe no puede bajar más de 0.3
PNL_DROP_MAX = 0.15          # PnL no puede bajar más del 15%
WIN_RATE_MIN = 0.40          # win rate no puede bajar de 40%

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ No se pudo leer el backtest: {e}")
        sys.exit(2)

def check(backtest):
    baseline = backtest.get("baseline", {})
    latest   = backtest.get("latest", {})

    sharpe_b = baseline.get("Sharpe", 0)
    sharpe_l = latest.get("Sharpe", 0)
    sharpe_delta = sharpe_l - sharpe_b

    pnl_b = baseline.get("totalPnL", 0) or 0
    pnl_l = latest.get("totalPnL", 0) or 0
    pnl_drop = (pnl_b - pnl_l) / (abs(pnl_b) + 1e-9)

    wr_b = baseline.get("winRate", 0) or 0
    wr_l = latest.get("winRate", 0) or 0

    results = {
        "baseline": baseline,
        "latest":  latest,
        "sharpe_delta": round(sharpe_delta, 4),
        "pnl_drop": round(pnl_drop, 4),
        "win_rate_baseline": wr_b,
        "win_rate_latest": wr_l,
    }

    checks = {
        "sharpe_delta": sharpe_delta >= SHARPE_DELTA_MIN,
        "pnl_drop": pnl_drop <= PNL_DROP_MAX,
        "win_rate": wr_l >= WIN_RATE_MIN,
    }

    ok = all(checks.values())
    results["checks"] = checks
    results["passed"] = ok
    return results

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("backtest", help="ruta al archivo backtest.json")
    ap.add_argument("--json", action="store_true", help="imprimir solo JSON")
    args = ap.parse_args()

    try:
        data = load(args.backtest)
    except SystemExit:
        sys.exit(2)

    # El backtest puede tener la estructura:
    # { "baseline": {...}, "latest": {...} }  o  { "baseline": {...}, "delta": {...} }
    results = check(data)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("═ CI BACKTEST GATE ═")
        print(f"Sharpe Δ      = {results['sharpe_delta']:+.3f}   (min {SHARPE_DELTA_MIN})")
        print(f"PnL drop %    = {results['pnl_drop']*100:.2f}%      (max {PNL_DROP_MAX*100:.2f}%)")
        print(f"Win rate L    = {results['win_rate_latest']*100:.1f}%  (min {WIN_RATE_MIN*100:.0f}%)")
        print("─" * 40)
        for k, v in results["checks"].items():
            print(f"  [{'✅' if v else '❌'}] {k}")
        print(f"→ {'PASO' if results['passed'] else 'REGRESIÓN'}")
        print("═" * 40)

    if not results["passed"]:
        sys.exit(1)

if __name__ == "__main__":
    main()
