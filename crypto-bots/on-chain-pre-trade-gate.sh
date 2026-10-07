#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO — ON-CHAIN PRE-TRADE GATE (FASE 9)
# ════════════════════════════════════════════════════════
# Shell wrapper para el on-chain pre-trade gate.
# Se ejecuta ANTES de cada trade para validar riesgo on-chain.
#
# Usage: ./on-chain-pre-trade-gate.sh <COIN> <BUY|SELL>
# Output: STATUS|reason  (ALLOW_ON_CHAIN_GATE|WARN_ON_CHAIN_GATE|BLOCK_ON_CHAIN_GATE)
# Exit:   0=ALLOW, 1=WARN(50%), 2=BLOCK
# ════════════════════════════════════════════════════════

set -uo pipefail

# --- Config ---
WORKSPACE="$(cd "$(dirname "$0")/../" && pwd)"
PYTHON="/usr/bin/python3"
GATE_SCRIPT="${WORKSPACE}/ml/on_chain_pre_trade_gate.py"

# --- Args ---
COIN="${1:-}"
ACTION="${2:-BUY}"

if [ -z "$COIN" ]; then
    echo "ERROR_USAGE|Usage: $0 <COIN> [BUY|SELL]"
    exit 3
fi

# --- Run gate ---
RESULT=$($PYTHON -B "$GATE_SCRIPT" "$COIN" 2>&1) || RESULT="ERROR|$RESULT"

# --- Extract decision ---
# Python output format: [DECISION] COIN: Risk=X/5 | SM=Y | Score=Z
DECISION=$(echo "$RESULT" | grep -oP '^\[\K\w+' | head -1)
RISK_LEVEL=$(echo "$RESULT" | grep -oP 'Risk=\K\d+' | head -1)
SM_SIGNAL=$(echo "$RESULT" | grep -oP 'SM=\K[+\-]\d+' | head -1)
SM_SCORE=$(echo "$RESULT" | grep -oP 'Score=\K[\d.]+' | head -1)

# --- Build output en formato esperado por crypto-trade-moneda-v3-slots.sh ---
case "$DECISION" in
    BLOCK)
        echo "BLOCK_ON_CHAIN_GATE|Risk=${RISK_LEVEL}/5 - Token audit HIGH (mintable/honeypot/tax)"
        exit 2
        ;;
    WARN)
        echo "WARN_ON_CHAIN_GATE|Risk=${RISK_LEVEL}/5 - Token audit MID, position reducida al 50%"
        exit 1
        ;;
    ALLOW)
        echo "ALLOW_ON_CHAIN_GATE|Risk=${RISK_LEVEL}/5 - On-chain validation passed (SM=${SM_SIGNAL}, Score=${SM_SCORE})"
        exit 0
        ;;
    *)
        echo "ALLOW_ON_CHAIN_GATE|UNKNOWN - No on-chain data available, proceeding with caution"
        exit 0
        ;;
esac
