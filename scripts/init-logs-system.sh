#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 LOG SYSTEM INITIALIZER - Perrobotillo v2.1
# Crea e inicializa los 8 logs faltantes
# Generado: 2026-10-04
# ════════════════════════════════════════════════════════

LOGS_DIR="/home/overgon/.openclaw/logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=== INICIALIZANDO SISTEMA DE LOGS ==="

# Crear logs base si no existen
for log in trade-slots.log order-placement-debug.log circuit-breaker-decisions.log auto-capital-adjust.log ml-prediction-input.log portfolio-balance-trace.log telegram-notification-delivery.log config-change-trace.log; do
    if [ ! -f "$LOGS_DIR/$log" ]; then
        touch "$LOGS_DIR/$log"
        echo "✅ Creado: $LOGS_DIR/$log"
    fi
done

# Headers JSONL para logs estructurados
echo "=== Inicializando headers JSONL ==="

# 1. trade-slots.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"slots\",\"message\":\"Log inicializado para 21 slots de trading\"}" > "$LOGS_DIR/trade-slots.log"

# 2. order-placement-debug.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"order-placement\",\"message\":\"Log para debug ordenes Binance API\"}" > "$LOGS_DIR/order-placement-debug.log"

# 3. circuit-breaker-decisions.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"circuit-breaker\",\"message\":\"Log de decisiones CB global\"}" > "$LOGS_DIR/circuit-breaker-decisions.log"

# 4. auto-capital-adjust.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"capital-manager\",\"message\":\"Log de ajustes automaticos de capital\"}" > "$LOGS_DIR/auto-capital-adjust.log"

# 5. ml-prediction-input.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"ml-predictions\",\"message\":\"Log de features ML por trade\"}" > "$LOGS_DIR/ml-prediction-input.log"

# 6. portfolio-balance-trace.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"portfolio\",\"message\":\"Trace de balances por transaccion\"}" > "$LOGS_DIR/portfolio-balance-trace.log"

# 7. telegram-notification-delivery.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"notifications\",\"message\":\"Trace de mensajes Telegram\"}" > "$LOGS_DIR/telegram-notification-delivery.log"

# 8. config-change-trace.log
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"system.init\",\"component\":\"config\",\"message\":\"Historial de cambios de config\"}" > "$LOGS_DIR/config-change-trace.log"

echo "=== Headers JSONL aplicados ==="
echo "✅ Todos los logs inicializados con formato JSONL estructurado"
