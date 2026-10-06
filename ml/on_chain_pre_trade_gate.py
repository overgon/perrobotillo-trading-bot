#!/usr/bin/env python3
"""
Perrobotillo ML: On-Chain Pre-Trade Gate
=======================================
Verifica token security audit + smart money signals antes de permitir un trade.

Integra:
1. Token Audit (query-token-audit skill): riesgo de contrato, taxes, mintability
2. Smart Money Signals (trading-signal skill): dirección, whales, exit rate

Output codes:
  ALLOW_ON_CHAIN_GATE|reason   → proceed to trade
  WARN_ON_CHAIN_GATE|reason    → allow trade pero ajustar posición (reduce 50%)
  BLOCK_ON_CHAIN_GATE|reason   → block trade (CRITICAL risk)

Uso:
  python3 ml/on_chain_pre_trade_gate.py BNB BUY
  python3 ml/on_chain_pre_trade_gate.py ETH SELL

NOTA: Este gate es read-only. No ejecuta trades.
"""
import os
import sys

# Setup path
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
sys.path.insert(0, os.path.join(WORKSPACE, "ml"))

from token_audit_gate import check_token_audit
from smart_money_signal import get_smart_money_features

# ── Risk thresholds ──────────────────────────────────────────────────────────
# Token Audit: riskLevel 4-5 = BLOCK (del SKILL.md)
TOKAN_AUDIT_BLOCK_THRESHOLD = 4

# Smart Money: confidence boost thresholds
SMART_MONEY_STRONG_THRESHOLD = 5   # 5+ whales, low exitRate → strong signal
SMART_MONEY_WEAK_THRESHOLD = 3     # 3+ whales → moderate signal
EXIT_RATE_RED_THRESHOLD = 70       # 70%+ exit rate → smart money exiting


def evaluate_pre_trade(symbol: str, action: str) -> str:
    """
    Evalúa on-chain data antes de permitir un trade.

    Args:
        symbol: "BNB", "ETH", "SOL", etc.
        action: "BUY" o "SELL"

    Returns:
        "ALLOW_ON_CHAIN_GATE|reason"
        "WARN_ON_CHAIN_GATE|reason"
        "BLOCK_ON_CHAIN_GATE|reason"
    """
    symbol_upper = symbol.upper()
    action_upper = action.upper()

    # ── 1. Token Audit Check ────────────────────────────────────────────────
    audit = check_token_audit(symbol_upper, force_refresh=False)

    # BLOCK if riskLevel >= 4
    if audit.get("risk_level_num", 0) >= TOKAN_AUDIT_BLOCK_THRESHOLD:
        return f"BLOCK_ON_CHAIN_GATE|Token audit HIGH risk (level {audit['risk_level_num']}): {audit.get('risk_level_enum')}"

    # Warn if MID risk con mintable o taxas altas
    if audit.get("has_result") and audit.get("risk_level_enum") == "MID":
        for risk in audit.get("risk_items", []):
            if "mintable" in risk.get("title", "").lower():
                return f"WARN_ON_CHAIN_GATE|Token audit MID: mintable detected ({risk['title']})"
        # Taxas altas
        buy_tax = audit.get("buy_tax", 0)
        sell_tax = audit.get("sell_tax", 0)
        if buy_tax > 5 or sell_tax > 5:
            return f"WARN_ON_CHAIN_GATE|High tax detected: buy={buy_tax}%, sell={sell_tax}%"

    # ── 2. Smart Money Check ────────────────────────────────────────────────
    sm = get_smart_money_features(symbol_upper, force_refresh=False)

    # Si es BUY y smart money está vendiendo (exitRate alto) → WARNING
    if action_upper == "BUY" and sm.get("smart_money_count", 0) >= SMART_MONEY_WEAK_THRESHOLD:
        if sm.get("exit_rate", 0) >= EXIT_RATE_RED_THRESHOLD:
            return f"WARN_ON_CHAIN_GATE|Smart money exiting: {sm['smart_money_count']} whales, exit_rate={sm['exit_rate']}% — considerar posición reducida"

    # Si es SELL y smart money está comprando → WARNING
    if action_upper == "SELL" and sm.get("smart_money_signal", 0) == 1 and sm.get("smart_money_count", 0) >= SMART_MONEY_STRONG_THRESHOLD:
        return f"WARN_ON_CHAIN_GATE|Smart money buying ({sm['smart_money_count']} whales) while bot sells — posible bottom"

    # ── 3. Combine score: confidence boost affects position sizing ───────────
    confidence_boost = sm.get("confidence_boost", 0)
    risk_level = audit.get("risk_level_enum", "LOW")

    if confidence_boost >= SMART_MONEY_STRONG_THRESHOLD and risk_level in ("LOW", "MID"):
        # Strong smart money + low risk → allow + boost position
        return f"ALLOW_ON_CHAIN_GATE|Strong signal: {sm['smart_money_count']} whales, +{confidence_boost}% confidence, audit={risk_level}"
    elif confidence_boost >= SMART_MONEY_WEAK_THRESHOLD:
        return f"ALLOW_ON_CHAIN_GATE|Moderate signal: {sm['smart_money_count']} whales, +{confidence_boost}% confidence, audit={risk_level}"
    else:
        # No strong on-chain signal → fallback al ML validator
        return f"ALLOW_ON_CHAIN_GATE|No strong on-chain signal, audit={risk_level}, ML validator decides"


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 on_chain_pre_trade_gate.py <SYMBOL> [BUY|SELL]")
        print("Example: python3 on_chain_pre_trade_gate.py BNB BUY")
        sys.exit(2)

    symbol = sys.argv[1].upper()
    action = sys.argv[2].upper() if len(sys.argv) > 2 else "BUY"

    result = evaluate_pre_trade(symbol, action)
    print(result)
