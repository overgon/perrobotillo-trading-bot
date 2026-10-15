#!/usr/bin/env python3
"""
Perrobotillo ML Feature: On-Chain Pre-Trade Gate (FASE 9 - Realtime)
"""
import sys
import os
import json
from pathlib import Path

# 🔧 FIX (2026-10-06): Use expanduser instead of hardcoded path.
# Previous hardcoded "/home/verton/..." was WRONG (real home is /home/overgon).
# This caused ModuleNotFoundError for ml.smart_money_signal because sys.path
# pointed to a non-existent directory. See skill on-chain-pre-trade-gate:
# "Use os.path.expandhome not hardcoded paths".
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from ml.smart_money_signal import get_smart_money_features
from ml.token_audit_gate import check_token_audit, RISK_BLOCK_THRESHOLD

ALL_COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'ZEC', 'LINK', 'XRP', 'AVAX']
RISK_BLOCK_THRESHOLD = 4
RISK_WARN_THRESHOLD = 3


def evaluate_onchain_gate(symbol, force_refresh=False):
    """Run full on-chain validation pipeline for a single coin."""
    symbol_upper = symbol.upper()
    if symbol_upper not in ALL_COINS:
        return {
            "symbol": symbol,
            "decision": "UNKNOWN",
            "risk_level_num": -1,
            "error": f"Unknown coin: {symbol}. Valid: {ALL_COINS}",
        }

    sm = get_smart_money_features(symbol_upper, force_refresh=force_refresh)
    ta = check_token_audit(symbol_upper, force_refresh=force_refresh)
    
    risk_level = ta.get("risk_level_num", 0)
    sm_signal = sm.get("smart_money_signal", 0)
    sm_score = sm.get("smart_money_score", 0.0)
    confidence_boost = sm.get("confidence_boost", 0)
    
    # 🔧 FIX: When token audit has no result (hasResult=false), the API returned
    # risk_level_num=0 which mapped to ALLOW — a silent no-op gate.
    # When we cannot verify on-chain safety, treat as WARN to be conservative.
    # This prevents the gate from always allowing when data sources are empty.
    if not ta.get("has_result"):
        risk_level = RISK_WARN_THRESHOLD  # 3 = WARN
    
    if risk_level >= RISK_BLOCK_THRESHOLD:
        decision = "BLOCK"
    elif risk_level >= RISK_WARN_THRESHOLD:
        decision = "WARN"
    else:
        decision = "ALLOW"

    result = {
        "symbol": symbol_upper,
        "decision": decision,
        "risk_level_num": risk_level,
        "risk_level_enum": ta.get("risk_level_enum", "UNKNOWN"),
        "smart_money_signal": sm_signal,
        "smart_money_score": sm_score,
        "confidence_boost": confidence_boost,
        "is_verified": ta.get("is_verified"),
        "buy_tax": ta.get("buy_tax", 0),
        "sell_tax": ta.get("sell_tax", 0),
        "risk_items": ta.get("risk_items", []),
        "cached": bool(ta.get("has_result")),
    }

    print(f"[{decision}] {symbol_upper}: Risk={risk_level}/5 | SM={sm_signal:+d} | Score={sm_score:.2f}")
    return result


def batch_validate(force_refresh=False):
    """Run on-chain gate for ALL 8 coins."""
    print("=== FASE 9 On-Chain Pre-Trade Gate - Batch Validation ===")
    print("")
    
    results = {}
    summary = {"ALLOW": [], "WARN": [], "BLOCK": [], "UNKNOWN": []}

    for coin in ALL_COINS:
        result = evaluate_onchain_gate(coin, force_refresh=force_refresh)
        results[coin] = result
        summary[result["decision"]].append(coin)

    print("")
    print(f"Summary: {len(summary['ALLOW'])} ALLOW | {len(summary['WARN'])} WARN | {len(summary['BLOCK'])} BLOCK")
    if summary["BLOCK"]:
        print(f"   BLOCK: {summary['BLOCK']}")
    if summary["WARN"]:
        print(f"   WARN: {summary['WARN']}")
    if summary["ALLOW"]:
        print(f"   ALLOW: {summary['ALLOW']}")

    return {"results": results, "summary": summary}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Perrobotillo On-Chain Pre-Trade Gate")
    parser.add_argument("coin", nargs="?", default="all", help="Coin to validate (BTC, ETH, etc.) or 'all'")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass cache")
    args = parser.parse_args()

    if args.coin == "all" or args.coin == "":
        batch_validate(force_refresh=args.force_refresh)
    else:
        result = evaluate_onchain_gate(args.coin, force_refresh=args.force_refresh)
        print(json.dumps(result, indent=2, default=str))
