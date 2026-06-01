#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛑 GLOBAL CIRCUIT BREAKER - Optimizado 2026-06-01
# ════════════════════════════════════════════════════════
# Verifica losses globales (todas las monedas) en últimas 24h
# Evita "desastres" como May 16 donde 11 losses ocurrieron en 48h
# Uso: ./global-circuit-breaker.sh
# Output: OK_TO_TRADE o GLOBAL_PAUSE_XXH
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
TRADE_HISTORY="${WORKSPACE}/crypto-bots/trade-history.json"
GLOBAL_PAUSE_FILE="${WORKSPACE}/crypto-bots/global-pause-flag.json"

# ════════════════════════════════════════════════════════
# VERIFICAR SI YA HAY PAUSE GLOBAL ACTIVO
# ════════════════════════════════════════════════════════
if [ -f "$GLOBAL_PAUSE_FILE" ]; then
    pause_until=$(jq -r '.pause_until // null' "$GLOBAL_PAUSE_FILE")
    if [ "$pause_until" != "null" ]; then
        pause_epoch=$(date -d "$pause_until" +%s 2>/dev/null || echo 0)
        now_epoch=$(date +%s)
        
        if [ $now_epoch -lt $pause_epoch ]; then
            remaining_hours=$(( (pause_epoch - now_epoch) / 3600 ))
            echo "GLOBAL_PAUSE_ACTIVE|${remaining_hours}h restantes"
            exit 1
        else
            # Pausa expiró, limpiar flag
            rm -f "$GLOBAL_PAUSE_FILE"
            echo "GLOBAL_PAUSE_EXPIRED|Reanudando operaciones"
        fi
    fi
fi

# ════════════════════════════════════════════════════════
# CALCULAR LOSSSES GLOBALES EN ÚLTIMAS 24H
# ════════════════════════════════════════════════════════
if [ ! -f "$TRADE_HISTORY" ]; then
    echo "OK_TO_TRADE|Sin histórico"
    exit 0
fi

current_time=$(date +%s)
cutoff_time=$((current_time - 86400))  # 24 horas atrás

# Contar losses en últimas 24h (todas las monedas)
losses_24h=$(jq --argjson cutoff "$cutoff_time" \
    '[.trades[] | select(.timestamp | fromdateiso8601 > $cutoff) | select(.pnlUSDT < 0)] | length' \
    "$TRADE_HISTORY" 2>/dev/null || echo 0)

# Calcular pérdida total en 24h
total_loss_24h=$(jq --argjson cutoff "$cutoff_time" \
    '[.trades[] | select(.timestamp | fromdateiso8601 > $cutoff) | select(.pnlUSDT < 0) | .pnlUSDT] | add // 0' \
    "$TRADE_HISTORY" 2>/dev/null || echo 0)

# Contar trades totales en 24h
trades_24h=$(jq --argjson cutoff "$cutoff_time" \
    '[.trades[] | select(.timestamp | fromdateiso8601 > $cutoff)] | length' \
    "$TRADE_HISTORY" 2>/dev/null || echo 0)

echo "# Global 24h: $losses_24h losses, $trades_24h trades, \$${total_loss_24h}" >&2

# ════════════════════════════════════════════════════════
# 🛑 REGLAS DE CIRCUIT BREAKER - OPTIMIZADO 2026-06-01
# ════════════════════════════════════════════════════════

# Regla 1: 4+ losses en 24h → PAUSE 24h
if [ "$losses_24h" -ge 4 ]; then
    pause_until=$(date -d '+24 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_24h" --arg loss "$total_loss_24h" \
        '{"pause_until": $pause, "triggered_by": "losses_count", "losses_24h": $losses, "total_loss": $loss}' \
        > "$GLOBAL_PAUSE_FILE"
    
    echo "GLOBAL_PAUSE_24H|$losses_24h losses en 24h (threshold: 4)"
    exit 1
fi

# Regla 2: -$50+ USDT en 24h → PAUSE 48h
if (( $(echo "$total_loss_24h < -50" | bc -l) )); then
    pause_until=$(date -d '+48 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_24h" --arg loss "$total_loss_24h" \
        '{"pause_until": $pause, "triggered_by": "drawdown_threshold", "losses_24h": $losses, "total_loss": $loss}' \
        > "$GLOBAL_PAUSE_FILE"
    
    echo "GLOBAL_PAUSE_48H|\$${total_loss_24h} pérdidas en 24h (threshold: -$50)"
    exit 1
fi

# Regla 3: 2+ losses en última hora → PAUSE 4h (evita "desastres" como May 16)
one_hour_ago=$((current_time - 3600))
losses_1h=$(jq --argjson cutoff "$one_hour_ago" \
    '[.trades[] | select(.timestamp | fromdateiso8601 > $cutoff) | select(.pnlUSDT < 0)] | length' \
    "$TRADE_HISTORY" 2>/dev/null || echo 0)

if [ "$losses_1h" -ge 2 ]; then
    pause_until=$(date -d '+4 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_1h" \
        '{"pause_until": $pause, "triggered_by": "hourly_losses", "losses_1h": $losses}' \
        > "$GLOBAL_PAUSE_FILE"
    
    echo "GLOBAL_PAUSE_4H|$losses_1h losses en última hora (threshold: 2)"
    exit 1
fi

# Regla 4: Loss rate > 60% en 24h → PAUSE 12h
if [ "$trades_24h" -gt 0 ]; then
    loss_rate=$(echo "scale=2; $losses_24h * 100 / $trades_24h" | bc)
    if (( $(echo "$loss_rate > 60" | bc -l) )); then
        pause_until=$(date -d '+12 hours' '+%Y-%m-%d %H:%M:%S')
        jq -n --arg pause "$pause_until" --arg rate "$loss_rate" --argjson losses "$losses_24h" \
            '{"pause_until": $pause, "triggered_by": "loss_rate", "loss_rate": $rate, "losses_24h": $losses}' \
            > "$GLOBAL_PAUSE_FILE"
        
        echo "GLOBAL_PAUSE_12H|${loss_rate}% loss rate en 24h (threshold: 60%)"
        exit 1
    fi
fi

echo "OK_TO_TRADE|$losses_24h losses, \$${total_loss_24h}, ${trades_24h} trades en 24h"
exit 0
