#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛡️ ON-CHAIN PRE-TRADE GATE - Binance Skill Hub Integration
# ════════════════════════════════════════════════════════
# Verifica token security audit + smart money signals antes de trade
# Usa Binance Skill Hub: query-token-audit + trading-signal
# Output codes:
#   ALLOW_ON_CHAIN_GATE|reason    → proceed to trade
#   BLOCK_ON_CHAIN_GATE|reason    → block trade (CRITICAL risk)
#   WARN_ON_CHAIN_GATE|reason     → allow trade pero ajustar posición
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
ON_CHAIN_GATE="$WORKSPACE/ml/on_chain_pre_trade_gate.py"
SYMBOL="${1:-BNB}"
ACTION="${2:-BUY}"  # BUY or SELL

# Saltar on-chain gate si no hay datos (fallback al sistema anterior)
if [ ! -f "$ON_CHAIN_GATE" ]; then
    echo "ALLOW_ON_CHAIN_GATE|fallback: no on-chain gate script"
    exit 0
fi

# Llamar al gate checker
# El python imprime debug a stderr, resultado final a stdout (última línea)
RESULT=$(python3 "$ON_CHAIN_GATE" "$SYMBOL" "$ACTION" 2>/dev/null | tail -1)

# Parsear resultado
STATUS=$(echo "$RESULT" | cut -d'|' -f1)
REASON=$(echo "$RESULT" | cut -d'|' -f2-)

echo "${STATUS}|${REASON}"

case "$STATUS" in
    ALLOW_ON_CHAIN_GATE)
        exit 0
        ;;
    WARN_ON_CHAIN_GATE)
        exit 0  # Allow pero dashboard notifica warning
        ;;
    BLOCK_ON_CHAIN_GATE)
        exit 1  # Bloquear trade
        ;;
    *)
        echo "ALLOW_ON_CHAIN_GATE|unknown_status_fallback"
        exit 0
        ;;
esac
