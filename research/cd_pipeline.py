#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# CD ORCHESTRATOR — cd_pipeline.py  (Issue #66)
#
# Ejecución en el Raspberry Pi (cron):
#   Mon-Sat 5:05 AM  daily     → backtest 7 monedas, alerta Telegram
#   Sun 3:00 AM      optimize  → Optuna 50 trials, train/test 70/30
#   Sun 5:00 AM      ml-retrain→ Retrain RF per-coin, valida gap de CV
#   Sun 7:00 AM      deploy-gate→ Si Sharpe > baseline + 0.1 → commit + tag
#
# Uso:
#   python3 research/cd_pipeline.py --mode daily|optimize|ml-retrain|deploy-gate
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
LOGS = os.path.join(WORKSPACE, "logs")
os.makedirs(LOGS, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX", "ZEC"]

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    with open(os.path.join(LOGS, "cd_pipeline.log"), "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

def run(cmd, check=True):
    log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)

def backtest_all(days=14):
    log("▶ BACKTEST todas las monedas...")
    for c in COINS:
        run(["python", "research/run_backtest.py", "--symbol", f"{c}USDT", "--days", str(days)])
    # baseline vs latest
    baseline = json.load(open(os.path.join(WORKSPACE, "research", "mc_trades_results.json")))
    latest = json.load(open(os.path.join(LOGS, "backtest_latest.json")))
    report = {
        "timestamp": datetime.now().isoformat(),
        "days": days,
        "baseline": baseline,
        "latest": latest,
    }
    json.dump(report, open(os.path.join(LOGS, "backtest_report.json"), "w"), indent=2)
    log(f"✅ backtest {days}d guardado en backtest_report.json")
    return report

def optuna_trials(trials=50):
    log(f"▶ OPTUNA {trials} trials...")
    run(["python", "research/optuna_custom.py", "--trials", str(trials)])
    log("✅ Optuna completado")

def ml_retrain():
    log("▶ ML AUTO-RETRAIN...")
    run(["python", "ml/auto-retrain-v2.py"])
    log("✅ Retrain completado")

def deploy_gate():
    log("▶ DEPLOY GATE...")
    # compara Sharpe actual contra baseline + 0.1 → si gana, commit + tag
    latest = json.load(open(os.path.join(LOGS, "backtest_report.json")))  # placeholder
    gate = json.load(open(os.path.join(LOGS, "ci_backtest_gate.json")))
    if gate.get("passed"):
        run(["git", "add", "-A"])
        run(["git", "commit", "-m", f"chore: deploy gate pasó ({datetime.now().isoformat()})"])
        run(["git", "tag", f"deploy-{datetime.now().strftime('%Y%m%d-%H%M%S')}"])
        log("✅ Commit + tag creados")
    else:
        log("⚠️  Deploy gate NO aprobado; sin commit/tag")

# ---- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=["daily", "optimize", "ml-retrain", "deploy-gate"],
                    help="Fase del pipeline")
    ap.add_argument("--days", type=int, default=14, help="días de backtest")
    ap.add_argument("--trials", type=int, default=50, help="trials Optuna")
    args = ap.parse_args()

    modes = {
        "daily":      (backtest_all, {"days": args.days}),
        "optimize":   (optuna_trials, {"trials": args.trials}),
        "ml-retrain": (ml_retrain, {}),
        "deploy-gate":(deploy_gate, {}),
    }
    fn, kw = modes[args.mode]
    log(f"=== CD PIPELINE — mode={args.mode} — inicio ===")
    fn(**kw)
    log(f"=== CD PIPELINE — mode={args.mode} — fin ===")

if __name__ == "__main__":
    main()
