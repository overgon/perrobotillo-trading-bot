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
            remaining_minutes=$(( (pause_epoch - now_epoch) / 60 % 60 ))
            
            # 📱 ACTUALIZAR DASHBOARD STATUS - CB activo
            python3 << CBEOF
import json
from datetime import datetime, timezone, timedelta
cst = timezone(timedelta(hours=-6))
status = {
    "circuitBreakerActive": True,
    "status": "GLOBAL_PAUSE",
    "triggeredBy": "losses_count",
    "message": "🔴 Circuit Breaker ON",
    "pauseUntil": "$(echo "$pause_until" | python3 -c "import sys; from datetime import datetime, timezone, timedelta; cst = timezone(timedelta(hours=-6)); print(datetime.fromisoformat(sys.stdin.read().strip()).replace(tzinfo=cst).isoformat())")",
    "losses24h": $(jq -r '.losses_24h // 0' "$GLOBAL_PAUSE_FILE" 2>/dev/null || echo 0),
    "totalLoss": "$(jq -r '.total_loss // "0"' "$GLOBAL_PAUSE_FILE" 2>/dev/null)",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "activatedAt": datetime.now(cst).isoformat(),
    "lastChecked": datetime.now(cst).isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF

            # 🐕 FIX: Permitir gestión de trades activos (SL/TP) incluso con pause flag
            # Verificar si hay trades activos que necesitan gestión
            HAS_ACTIVE_TRADES=false
            for coin in BTC ETH BNB SOL LINK XRP AVAX; do
                state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
                if [ -f "$state_file" ]; then
                    active=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file" 2>/dev/null || echo 0)
                    if [ "$active" -gt 0 ]; then
                        HAS_ACTIVE_TRADES=true
                        break
                    fi
                fi
            done
            
            if [ "$HAS_ACTIVE_TRADES" = true ]; then
                # Hay trades activos - permitir ejecución para gestión (SL/TP)
                echo "ALLOW_ACTIVE_MANAGEMENT|${remaining_hours}h pause, gestionando activos"
                exit 0  # Permitir ejecución
            else
                # No hay trades activos - bloquear completamente
                echo "GLOBAL_PAUSE_ACTIVE|${remaining_hours}h restantes"
                exit 1
            fi
        else
            # Pausa expiró, limpiar flag
            rm -f "$GLOBAL_PAUSE_FILE"
            
            # 🐕 ACTUALIZAR DASHBOARD STATUS - Trading reanudado
            python3 << CBEOF
import json
from datetime import datetime
status = {
    "circuitBreakerActive": False,
    "status": "RESUMED",
    "message": "Circuit Breaker OFF - Trading Reanudado",
    "resumedAt": datetime.now().isoformat(),
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
            
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

# Usar Python para parsing correcto de timestamps (bash jq tiene problemas con timezones)
losses_data=$(python3 << 'PYEOF'
import json
from datetime import datetime, timezone, timedelta
import sys

with open("/home/overgon/.openclaw/workspace/crypto-bots/trade-history.json", 'r') as f:
    data = json.load(f)

now = datetime.now(timezone.utc)
cutoff_24h = now - timedelta(hours=24)
one_hour_ago = now - timedelta(hours=1)

losses_24h = 0
total_loss_24h = 0
trades_24h = 0
losses_1h = 0

for t in data.get('trades', []):
    ts_str = t['timestamp']
    try:
        if '+' not in ts_str and 'Z' not in ts_str:
            ts = datetime.fromisoformat(ts_str)
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        
        if ts >= cutoff_24h:
            trades_24h += 1
            if t['pnlUSDT'] < 0:
                losses_24h += 1
                total_loss_24h += t['pnlUSDT']
                if ts >= one_hour_ago:
                    losses_1h += 1
    except Exception as e:
        print(f"# Error parsing {t.get('timestamp', 'unknown')}: {e}", file=sys.stderr)

print(f"{losses_24h}|{total_loss_24h}|{trades_24h}|{losses_1h}")
PYEOF
)

losses_24h=$(echo "$losses_data" | cut -d'|' -f1)
total_loss_24h=$(echo "$losses_data" | cut -d'|' -f2)
trades_24h=$(echo "$losses_data" | cut -d'|' -f3)
losses_1h=$(echo "$losses_data" | cut -d'|' -f4)

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
    
    # 🐕 ACTUALIZAR DASHBOARD STATUS (on-demand)
    python3 << CBEOF
import json
from datetime import datetime
status = {
    "circuitBreakerActive": True,
    "status": "GLOBAL_PAUSE",
    "triggeredBy": "losses_count",
    "activatedAt": datetime.now().isoformat(),
    "pauseUntil": "$pause_until",
    "losses24h": $losses_24h,
    "message": f"🔴 Circuit Breaker ON - {losses_24h} losses en 24h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
    echo "GLOBAL_PAUSE_24H|$losses_24h losses en 24h (threshold: 4)"
    exit 1
fi

# Regla 2: -$50+ USDT en 24h → PAUSE 48h
if (( $(echo "$total_loss_24h < -50" | bc -l) )); then
    pause_until=$(date -d '+48 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_24h" --arg loss "$total_loss_24h" \
        '{"pause_until": $pause, "triggered_by": "drawdown_threshold", "losses_24h": $losses, "total_loss": $loss}' \
        > "$GLOBAL_PAUSE_FILE"
    
    # 🐕 ACTUALIZAR DASHBOARD STATUS (on-demand)
    python3 << CBEOF
import json
from datetime import datetime
status = {
    "circuitBreakerActive": True,
    "status": "GLOBAL_PAUSE",
    "triggeredBy": "drawdown_threshold",
    "activatedAt": datetime.now().isoformat(),
    "pauseUntil": "$pause_until",
    "losses24h": $losses_24h,
    "message": f"🔴 Circuit Breaker ON - \$${total_loss_24h} en 24h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
    echo "GLOBAL_PAUSE_48H|\$${total_loss_24h} pérdidas en 24h (threshold: -$50)"
    exit 1
fi

# Regla 3: 2+ losses en última hora → PAUSE 4h (evita "desastres" como May 16)
# losses_1h ya calculado arriba con Python
if [ "$losses_1h" -ge 2 ]; then
    pause_until=$(date -d '+4 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_1h" \
        '{"pause_until": $pause, "triggered_by": "hourly_losses", "losses_1h": $losses}' \
        > "$GLOBAL_PAUSE_FILE"
    
    # 🐕 ACTUALIZAR DASHBOARD STATUS (on-demand)
    python3 << CBEOF
import json
from datetime import datetime
status = {
    "circuitBreakerActive": True,
    "status": "GLOBAL_PAUSE",
    "triggeredBy": "hourly_losses",
    "activatedAt": datetime.now().isoformat(),
    "pauseUntil": "$pause_until",
    "losses24h": $losses_1h,
    "message": f"🔴 Circuit Breaker ON - {losses_1h} losses en 1h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
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
        
        # 🐕 ACTUALIZAR DASHBOARD STATUS (on-demand)
        python3 << CBEOF
import json
from datetime import datetime
status = {
    "circuitBreakerActive": True,
    "status": "GLOBAL_PAUSE",
    "triggeredBy": "loss_rate",
    "activatedAt": datetime.now().isoformat(),
    "pauseUntil": "$pause_until",
    "losses24h": $losses_24h,
    "message": f"🔴 Circuit Breaker ON - ${loss_rate}% loss rate",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
        
        echo "GLOBAL_PAUSE_12H|${loss_rate}% loss rate en 24h (threshold: 60%)"
        exit 1
    fi
fi

echo "OK_TO_TRADE|$losses_24h losses, \$${total_loss_24h}, ${trades_24h} trades en 24h"
exit 0
