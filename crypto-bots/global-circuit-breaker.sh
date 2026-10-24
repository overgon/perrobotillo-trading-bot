#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛑 GLOBAL CIRCUIT BREAKER - Optimizado 2026-06-01
# ════════════════════════════════════════════════════════
# Verifica losses globales (todas las monedas) en últimas 24h
# Evita "desastres" como May 16 donde 11 losses ocurrieron en 48h
# Uso: ./global-circuit-breaker.sh
# Output: OK_TO_TRADE o GLOBAL_PAUSE_XXH
# ════════════════════════════════════════════════════════

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
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
            
            # 📱 ACTUALIZAR DASHBOARD STATUS - delegated to update-circuit-breaker-countdown.py
            # which correctly reads triggered_by from the pause flag.
            # Previously, this block had hardcoded triggeredBy="losses_count" and read
            # .losses_24h (missing on Rule 3 triggers → showed 0), causing a race
            # condition where the CB script (every 5 min) would overwrite the countdown
            # script's correct dashboard values with incorrect ones.
            # REMOVED: inline Python dashboard update — countdown script handles this

            # 🐕 FIX: Permitir gestión de trades activos (SL/TP) incluso con pause flag
            # Verificar si hay trades activos que necesitan gestión
            HAS_ACTIVE_TRADES=false
            for coin in BTC ETH BNB SOL ZEC XRP AVAX; do
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
            # ✅ FIX: Use triggered_at (pause start) as reset cutoff, NOT now (expiry)
            # This ensures trades that closed DURING the pause are counted in the next evaluation
            triggered_at_epoch=$(jq -r '.triggered_at // 0' "$GLOBAL_PAUSE_FILE" 2>/dev/null || echo 0)
            rm -f "$GLOBAL_PAUSE_FILE"
            if [ "$triggered_at_epoch" -gt 0 ] 2>/dev/null; then
                reset_ts="$triggered_at_epoch"
            else
                reset_ts=$(date +%s)
            fi
            jq -n --arg rt "$reset_ts" \
                '{"loss_window_reset": $rt, "source": "pause_expired"}' \
                > "${WORKSPACE}/crypto-bots/cb-loss-reset-flag.json"
            
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
            
            echo "GLOBAL_PAUSE_EXPIRED|Reanudando operaciones\n# Grace period: 1h buffer before re-evaluating loss rate (trade window must age out)"
            # 🔧 FIX: Grace period of 1h after resume to let 24h trade window age out
            # Without this, a trade still within 24h window triggers CB re-activation immediately
            grace_until=$((now_epoch + 3600))
            jq -n --arg grace "$grace_until" \
                '{"grace_until": $grace, "source": "global_pause_expired"}' \
                > "${WORKSPACE}/crypto-bots/cb-grace-period-flag.json"
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
cutoff_24h = now - timedelta(hours=24)       # Full 24h window (for Rule 1)
one_hour_ago = now - timedelta(hours=1)

# ✅ FIX 3: If a loss-window reset flag exists (set when CB pause expired),
# only count trades AFTER the reset time for Rules 2-4 — trades that triggered
# the CB should NOT immediately re-trigger it (prevents perpetual re-trigger loop)
# Rule 1 uses the FULL 24h window with a guard (losses_24h >= 1) to prevent
# re-triggering on the same losses.
reset_file = "/home/overgon/.openclaw/workspace/crypto-bots/cb-loss-reset-flag.json"
cutoff_reset = cutoff_24h  # Start with same as full window
try:
    with open(reset_file) as rf:
        reset_data = json.load(rf)
    reset_epoch = int(reset_data.get("loss_window_reset", 0))
    reset_time = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
    if reset_time > cutoff_24h:
        cutoff_reset = reset_time  # Shift reset window to post-reset
except (FileNotFoundError, ValueError, KeyError):
    pass  # No reset flag — use normal 24h window for both

# Count losses in BOTH windows: full (for Rule 1) and reset (for Rules 2-4)
losses_24h = 0          # Reset window (Rules 2-4)
total_loss_24h = 0      # Reset window
trades_24h = 0          # Reset window
losses_1h = 0           # 1h window (always raw, no reset)

losses_24h_full = 0     # Full 24h window (Rule 1)
total_loss_24h_full = 0 # Full 24h window
trades_24h_full = 0     # Full 24h window

for t in data.get('trades', []):
    ts_str = t.get('timestamp') or t.get('closeTime') or ''
    if not ts_str:
        continue
    try:
        # ✅ FIX: Timestamps from trade-history.json are in Mexico CST (UTC-6).
        # Naive timestamps (no timezone suffix) are CST, not UTC.
        if '+' not in ts_str and 'Z' not in ts_str:
            ts = datetime.fromisoformat(ts_str)
            ts = ts.replace(tzinfo=timezone(timedelta(hours=-6)))  # Mexico CST (UTC-6)
        else:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

        # Full 24h window — for Rule 1 (cumulative loss count)
        if ts >= cutoff_24h:
            trades_24h_full += 1
            if t['pnlUSDT'] < 0:
                losses_24h_full += 1
                total_loss_24h_full += t['pnlUSDT']

        # Reset window — for Rules 2, 3, 4
        if ts >= cutoff_reset:
            trades_24h += 1
            if t['pnlUSDT'] < 0:
                losses_24h += 1
                total_loss_24h += t['pnlUSDT']
                if ts >= one_hour_ago:
                    losses_1h += 1
    except Exception as e:
        print(f"# Error parsing {t.get('timestamp', 'unknown')}: {e}", file=sys.stderr)

print(f"{losses_24h}|{total_loss_24h}|{trades_24h}|{losses_1h}|{losses_24h_full}|{total_loss_24h_full}|{trades_24h_full}")
PYEOF
)

losses_24h=$(echo "$losses_data" | cut -d'|' -f1)
total_loss_24h=$(echo "$losses_data" | cut -d'|' -f2)
trades_24h=$(echo "$losses_data" | cut -d'|' -f3)
losses_1h=$(echo "$losses_data" | cut -d'|' -f4)
losses_24h_full=$(echo "$losses_data" | cut -d'|' -f5)
total_loss_24h_full=$(echo "$losses_data" | cut -d'|' -f6)
trades_24h_full=$(echo "$losses_data" | cut -d'|' -f7)

# Fallback if full-window fields are missing (backward compat with old output)
losses_24h_full=${losses_24h_full:-$losses_24h}
total_loss_24h_full=${total_loss_24h_full:-$total_loss_24h}
trades_24h_full=${trades_24h_full:-$trades_24h}

echo "# Global 24h: $losses_24h_full losses, $trades_24h_full trades, \$${total_loss_24h_full} (reset window: $losses_24h/$trades_24h)" >&2

# 🔧 FIX: Grace period check after global pause expired
# Skip loss_rate evaluation during grace period to prevent immediate re-trigger
# when a recent trade is still inside the 24h window
now_epoch=$(date +%s)
if [ -f "${WORKSPACE}/crypto-bots/cb-grace-period-flag.json" ]; then
    grace_until_epoch=$(jq -r '.grace_until // 0' "${WORKSPACE}/crypto-bots/cb-grace-period-flag.json" 2>/dev/null || echo 0)
    if [ "$now_epoch" -lt "$grace_until_epoch" ]; then
        remaining_grace=$(( (grace_until_epoch - now_epoch) / 3600 ))
        echo "OK_TO_TRADE|$losses_24h_full losses, \$${total_loss_24h_full}, ${trades_24h_full} trades en 24h (grace period: ${remaining_grace}h)"
        exit 0
    else
        rm -f "${WORKSPACE}/crypto-bots/cb-grace-period-flag.json"
        # ✅ FIX 3: Do NOT remove cb-loss-reset-flag.json here — it must persist
        # through the loss calculation below. The Python code checks if the reset
        # time is within 24h; if older, it's simply ignored. Removing it here
        # would delete it right before the calculation that needs it.
        # The flag gets overwritten on next pause expiry.
    fi
fi

# ════════════════════════════════════════════════════════
# 📊 CB DECISIONS LOG - Perrobotillo v2.1
# ════════════════════════════════════════════════════════
CB_LOG="$WORKSPACE/logs/circuit-breaker-decisions.log"
log_cb() {
    local event="$1"
    local detail="$2"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"$ts\",\"event\":\"$event\",\"losses_24h\":$losses_24h,\"total_loss_24h\":$total_loss_24h,\"trades_24h\":$trades_24h,\"losses_1h\":$losses_1h,\"losses_24h_full\":$losses_24h_full,\"total_loss_24h_full\":$total_loss_24h_full,\"trades_24h_full\":$trades_24h_full,\"detail\":\"$detail\"}" >> "$CB_LOG"
}

# ════════════════════════════════════════════════════════
# 🛑 REGLAS DE CIRCUIT BREAKER - OPTIMIZADO 2026-06-01
# ════════════════════════════════════════════════════════

# Regla 1: 4+ losses en 24h → PAUSE 24h
# ✅ FIX: Use full 24h window (not reset window) for Rule 1, but require at least 1
# new loss since last pause trigger to prevent infinite re-trigger loop.
if [ "$losses_24h_full" -ge 4 ] && [ "$losses_24h" -ge 1 ]; then
    log_cb "cb.triggered" "losses_count_>=4_full_window"
    pause_until=$(date -d '+24 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_24h_full" --arg loss "$total_loss_24h_full" --argjson triggered_at "$(date +%s)" \
        '{"pause_until": $pause, "triggered_by": "losses_count", "losses_24h": $losses, "total_loss": $loss, "triggered_at": $triggered_at, "losses_full": $losses}' \
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
    "losses24h": $losses_24h_full,
    "message": "🔴 Circuit Breaker ON - $losses_24h_full losses en 24h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
    echo "GLOBAL_PAUSE_24H|$losses_24h_full losses en 24h (threshold: 4)"
    exit 1
fi

# Regla 2: -$50+ USDT en 24h → PAUSE 48h
if (( $(echo "$total_loss_24h < -50" | bc -l) )); then
    pause_until=$(date -d '+48 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_24h_full" --arg loss "$total_loss_24h_full" --argjson triggered_at "$(date +%s)" \
        '{"pause_until": $pause, "triggered_by": "drawdown_threshold", "losses_24h": $losses, "total_loss": $loss, "triggered_at": $triggered_at}' \
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
    "losses24h": $losses_24h_full,
    "message": "🔴 Circuit Breaker ON - $total_loss_24h_full en 24h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
    echo "GLOBAL_PAUSE_48H|\$${total_loss_24h_full} pérdidas en 24h (threshold: -$50)"
    log_cb "cb.triggered" "drawdown_threshold_-50usdt" 2>/dev/null || true
    exit 1
fi

# Regla 3: 2+ losses en última hora → PAUSE 4h (evita "desastres" como May 16)
# losses_1h ya calculado arriba con Python
if [ "$losses_1h" -ge 2 ]; then
    pause_until=$(date -d '+4 hours' '+%Y-%m-%d %H:%M:%S')
    jq -n --arg pause "$pause_until" --argjson losses "$losses_1h" --argjson triggered_at "$(date +%s)" \
        '{"pause_until": $pause, "triggered_by": "hourly_losses", "losses_1h": $losses, "triggered_at": $triggered_at}' \
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
    "message": "🔴 Circuit Breaker ON - $losses_1h losses en 1h",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
    
    echo "GLOBAL_PAUSE_4H|$losses_1h losses en última hora (threshold: 2)"
    log_cb "cb.triggered" "hourly_losses_>=2" 2>/dev/null || true
    exit 1
fi

# Regla 4: Loss rate > 60% en 24h → PAUSE 12h
# 🔧 FIX: requerir mínimo 3 trades en 24h antes de evaluar loss rate
# Con 1-2 trades, un solo SL dispara 100% loss rate → CB se perpetúa
if [ "$trades_24h" -ge 3 ]; then
    loss_rate=$(echo "scale=2; $losses_24h * 100 / $trades_24h" | bc)
    if (( $(echo "$loss_rate > 60" | bc -l) )); then
        pause_until=$(date -d '+12 hours' '+%Y-%m-%d %H:%M:%S')
        jq -n --arg pause "$pause_until" --arg rate "$loss_rate" --argjson losses "$losses_24h" --argjson triggered_at "$(date +%s)" \
            '{"pause_until": $pause, "triggered_by": "loss_rate", "loss_rate": $rate, "losses_24h": $losses, "triggered_at": $triggered_at}' \
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
    "losses24h": $losses_24h_full,
    "message": "🔴 Circuit Breaker ON - $loss_rate% loss rate",
    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
    "blockedOperations": ["New Entries", "DCA Operations"],
    "lastChecked": datetime.now().isoformat()
}
with open("/home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json", 'w') as f:
    json.dump(status, f, indent=2)
CBEOF
        
        echo "GLOBAL_PAUSE_12H|${loss_rate}% loss rate en 24h (threshold: 60%)"
        log_cb "cb.triggered" "loss_rate_gt_60pct" 2>/dev/null || true
        exit 1
    fi
fi

# ════════════════════════════════════════════════════════
# 🛡️ REGLA 5: ON-CHAIN PRE-TRADE GATE (Binance Skill Hub)
# ════════════════════════════════════════════════════════
# Verifica token audit + smart money antes de permitir NEW trades
# Output codes:
#   ALLOW_ON_CHAIN_GATE → proceed (may have warnings)
#   BLOCK_ON_CHAIN_GATE → block trade (CRITICAL risk)
#   WARN_ON_CHAIN_GATE  → allow pero ajustar posición
# 
# NOTA: Solo aplica a NEW trades. SL/TP management no se ve afectado.
ON_CHAIN_CHECK_SCRIPT="$WORKSPACE/crypto-bots/on-chain-pre-trade-gate.sh"
if [ -f "$ON_CHAIN_CHECK_SCRIPT" ]; then
    # El circuit breaker no conoce el symbol específico — usar CHECK_ALL_COINS
    # para pre-chequear que no haya tokens con HIGH risk en la lista de trading
    CB_SKIP_ON_CHAIN="${CB_SKIP_ON_CHAIN:-false}"
    if [ "$CB_SKIP_ON_CHAIN" = "true" ]; then
        echo "OK_TO_TRADE|$losses_24h_full losses, \$${total_loss_24h_full}, ${trades_24h_full} trades en 24h (on-chain gate skipped)"
        exit 0
    fi
    
    # Pre-chequear coins activas (no bloquear CB completo si un solo token tiene riesgo HIGH)
    ON_CHAIN_BLOCKED_COINS=""
    for coin in BTC ETH BNB SOL ZEC LINK XRP AVAX; do
        result=$("$ON_CHAIN_CHECK_SCRIPT" "$coin" "BUY" 2>/dev/null)
        status=$(echo "$result" | cut -d'|' -f1)
        if [ "$status" = "BLOCK_ON_CHAIN_GATE" ]; then
            ON_CHAIN_BLOCKED_COINS="${ON_CHAIN_BLOCKED_COINS}${coin},"
        fi
    done
    
    if [ -n "$ON_CHAIN_BLOCKED_COINS" ]; then
        blocked=$(echo "$ON_CHAIN_BLOCKED_COINS" | sed 's/,$//')
        echo "OK_TO_TRADE|$losses_24h_full losses, \$${total_loss_24h_full}, ${trades_24h_full} trades en 24h (on-chain BLOCKED: $blocked — coins skip on-chain trades, usar runtime ML gate)"
        # ⚠️ No bloquear completamente — solo documentar coins bloqueados por on-chain
        # El gate individual se ejecuta en crypto-trade-moneda-v3-slots.sh antes de cada trade
        exit 0
    else
        echo "OK_TO_TRADE|$losses_24h_full losses, \$${total_loss_24h_full}, ${trades_24h_full} trades en 24h (on-chain gate: all coins OK)"
        exit 0
    fi
fi

echo "OK_TO_TRADE|$losses_24h_full losses, \$${total_loss_24h_full}, ${trades_24h_full} trades en 24h"
exit 0
