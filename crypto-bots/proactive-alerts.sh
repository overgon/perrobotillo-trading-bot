#!/bin/bash
# ════════════════════════════════════════════════════════
# 🚨 PROACTIVE ALERTS - Alertas Tempranas de Riesgo
# Detecta condiciones peligrosas ANTES de que se acumulen pérdidas
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
LOG_FILE="/home/overgon/.openclaw/logs/proactive-alerts.log"
TRADE_HISTORY="$WORKSPACE/crypto-bots/trade-history.json"
ALERTS_STATE="$WORKSPACE/crypto-bots/alerts-state.json"

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

MAX_CONSECUTIVE_LOSSES=5      # Alertar después de 5 pérdidas seguidas
MIN_WINRATE_THRESHOLD=40      # Alertar si WR < 40% en últimos 10 trades
DAILY_LOSS_ALERT=2.0          # Alertar si pérdida diaria > 2% (antes del límite de 3%)
CHECK_INTERVAL_MINUTES=30     # Revisar cada 30 minutos

# ════════════════════════════════════════════════════════
# FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ✅ BUG #9/#10 FIX: Source centralized notify.sh
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

load_alerts_state() {
    if [ -f "$ALERTS_STATE" ]; then
        cat "$ALERTS_STATE" | jq -c '.' 2>/dev/null || echo '{"last_alert":{},"consecutive_losses":0,"daily_loss_notified":false}'
    else
        echo '{"last_alert":{},"consecutive_losses":0,"daily_loss_notified":false}'
    fi
}

save_alerts_state() {
    echo "$1" | jq '.' > "$ALERTS_STATE"
}

# ════════════════════════════════════════════════════════
# 🚨 ALERTA 1: RACHA DE PÉRDIDAS CONSECUTIVAS
# ════════════════════════════════════════════════════════

check_consecutive_losses() {
    python3 << 'PYTHON_EOF'
import json
import os
from datetime import datetime, timezone

trade_history = os.environ.get('TRADE_HISTORY', '')
max_losses = int(os.environ.get('MAX_CONSECUTIVE_LOSSES', 5))
alerts_state_file = os.environ.get('ALERTS_STATE', '')

try:
    with open(trade_history, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', []) if isinstance(data, dict) else data
    
    # Ordenar por timestamp (más reciente primero)
    trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Contar pérdidas consecutivas
    consecutive_losses = 0
    for t in trades:
        pnl = t.get('pnlUSDT', 0)
        if pnl <= 0:
            consecutive_losses += 1
            if consecutive_losses >= max_losses:
                break
        else:
            break
    
    # Cargar estado para verificar si ya alertamos
    last_alert_key = ""
    if os.path.exists(alerts_state_file):
        with open(alerts_state_file, 'r') as f:
            alerts_state = json.load(f)
            last_alert_key = alerts_state.get('last_alert', {}).get('consecutive_losses', '')
    
    current_streak_key = f"streak_{consecutive_losses}"
    
    if consecutive_losses >= max_losses and last_alert_key != current_streak_key:
        # Obtener detalles de la racha
        losing_trades = trades[:consecutive_losses]
        total_loss = sum(t.get('pnlUSDT', 0) for t in losing_trades)
        coins_involved = list(set(t.get('symbol', 'UNKNOWN') for t in losing_trades))
        
        result = {
            'alert': True,
            'consecutive_losses': consecutive_losses,
            'total_loss': total_loss,
            'coins': coins_involved,
            'alert_key': current_streak_key
        }
        print(json.dumps(result))
    else:
        print(json.dumps({'alert': False, 'consecutive_losses': consecutive_losses}))

except Exception as e:
    print(json.dumps({'alert': False, 'error': str(e)}))
PYTHON_EOF
}

# ════════════════════════════════════════════════════════
# 🚨 ALERTA 2: WIN RATE BAJO (ROLLING 10 TRADES)
# ════════════════════════════════════════════════════════

check_low_winrate() {
    python3 << 'PYTHON_EOF'
import json
import os
from datetime import datetime, timezone

trade_history = os.environ.get('TRADE_HISTORY', '')
min_winrate = int(os.environ.get('MIN_WINRATE_THRESHOLD', 40))
alerts_state_file = os.environ.get('ALERTS_STATE', '')

try:
    with open(trade_history, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', []) if isinstance(data, dict) else data
    
    # Ordenar por timestamp (más reciente primero)
    trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Últimos 10 trades
    recent = trades[:10]
    wins = [t for t in recent if t.get('pnlUSDT', 0) > 0]
    
    win_rate = len(wins) / len(recent) * 100 if len(recent) > 0 else 0
    
    # Verificar si ya alertamos recientemente (últimas 2 horas)
    last_alert_time = 0
    if os.path.exists(alerts_state_file):
        with open(alerts_state_file, 'r') as f:
            alerts_state = json.load(f)
            last_alert_time = alerts_state.get('last_alert', {}).get('low_winrate_time', 0)
    
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    
    if win_rate < min_winrate and (now_epoch - last_alert_time) > 7200:
        # Calcular pérdida en últimos 10 trades
        total_pnl = sum(t.get('pnlUSDT', 0) for t in recent)
        losses = [t for t in recent if t.get('pnlUSDT', 0) <= 0]
        
        result = {
            'alert': True,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'losses_count': len(losses),
            'alert_time': now_epoch
        }
        print(json.dumps(result))
    else:
        print(json.dumps({'alert': False, 'win_rate': win_rate}))

except Exception as e:
    print(json.dumps({'alert': False, 'error': str(e)}))
PYTHON_EOF
}

# ════════════════════════════════════════════════════════
# 🚨 ALERTA 3: PÉRDIDA DIARIA ACERCÁNDOSE AL LÍMITE
# ════════════════════════════════════════════════════════

check_daily_loss() {
    python3 << 'PYTHON_EOF'
import json
import os
from datetime import datetime, timezone, timedelta

trade_history = os.environ.get('TRADE_HISTORY', '')
daily_loss_threshold = float(os.environ.get('DAILY_LOSS_ALERT', 2.0))
alerts_state_file = os.environ.get('ALERTS_STATE', '')

try:
    with open(trade_history, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', []) if isinstance(data, dict) else data
    
    # Filtrar trades de hoy (desde medianoche)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    losses_today = []
    for t in trades:
        try:
            ts_str = t.get('timestamp', '')
            # Manejar diferentes formatos de timestamp
            for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S']:
                try:
                    ts = datetime.strptime(ts_str, fmt)
                    break
                except:
                    continue
            else:
                continue
            
            if ts >= today_start and t.get('pnlUSDT', 0) < 0:
                losses_today.append(t)
        except:
            pass
    
    total_loss = sum(t.get('pnlUSDT', 0) for t in losses_today)
    
    # Verificar si ya notificamos hoy
    notified_today = False
    last_notified_date = ""
    if os.path.exists(alerts_state_file):
        with open(alerts_state_file, 'r') as f:
            alerts_state = json.load(f)
            notified_today = alerts_state.get('daily_loss_notified', False)
            last_notified_date = alerts_state.get('last_daily_loss_date', '')
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    already_notified = notified_today or (last_notified_date == today_str)
    
    if total_loss <= -daily_loss_threshold and not already_notified:
        coins_affected = list(set(t.get('symbol', 'UNKNOWN') for t in losses_today))
        
        result = {
            'alert': True,
            'daily_loss': abs(total_loss),
            'trades_count': len(losses_today),
            'coins': coins_affected,
            'notified_today': True,
            'date': today_str
        }
        print(json.dumps(result))
    else:
        print(json.dumps({
            'alert': False, 
            'daily_loss': abs(total_loss),
            'notified_today': already_notified
        }))

except Exception as e:
    print(json.dumps({'alert': False, 'error': str(e)}))
PYTHON_EOF
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🚨 PROACTIVE ALERTS CHECK                            ║"
log "╚═══════════════════════════════════════════════════════╝"

# Exportar variables para Python
export TRADE_HISTORY
export MAX_CONSECUTIVE_LOSSES
export MIN_WINRATE_THRESHOLD
export DAILY_LOSS_ALERT
export ALERTS_STATE

alerts_state=$(load_alerts_state)
alerts_sent=0

# ════════════════════════════════════════════════════════
# CHECK 1: Rachas de pérdidas
# ════════════════════════════════════════════════════════

log "📊 Check 1: Rachas de pérdidas consecutivas..."
result=$(check_consecutive_losses)
consecutive_losses=$(echo "$result" | jq -r '.consecutive_losses // 0')
should_alert=$(echo "$result" | jq -r '.alert // false')

if [ "$should_alert" = "true" ]; then
    total_loss=$(echo "$result" | jq -r '.total_loss // 0')
    coins=$(echo "$result" | jq -r '.coins | join(", ") // "N/A"')
    alert_key=$(echo "$result" | jq -r '.alert_key // ""')
    
    log "   🚨 ALERTA: $consecutive_losses pérdidas consecutivas (-\$${total_loss})"
    
    notify "PROACTIVE_ALERT" "🚨 ALERTA - RACHA DE PÉRDIDAS
${consecutive_losses} pérdidas consecutivas | PnL: -\\$${total_loss} USDT
🪙 ${coins}
• Pausar trading temporalmente
• Revisar patrones comunes en pérdidas
• Esperar señal de alta confianza 🐕"
    
    # Actualizar estado
    alerts_state=$(echo "$alerts_state" | jq ".last_alert.consecutive_losses = \"$alert_key\"")
    alerts_sent=$((alerts_sent + 1))
else
    log "   ✅ Sin alerta ($consecutive_losses pérdidas consecutivas)"
fi

# ════════════════════════════════════════════════════════
# CHECK 2: Win rate bajo
# ════════════════════════════════════════════════════════

log "📊 Check 2: Win rate rolling 10 trades..."
result=$(check_low_winrate)
win_rate=$(echo "$result" | jq -r '.win_rate // 0')
should_alert=$(echo "$result" | jq -r '.alert // false')

if [ "$should_alert" = "true" ]; then
    total_pnl=$(echo "$result" | jq -r '.total_pnl // 0')
    losses_count=$(echo "$result" | jq -r '.losses_count // 0')
    alert_time=$(echo "$result" | jq -r '.alert_time // 0')
    
    log "   🚨 ALERTA: Win Rate ${win_rate}% (<${MIN_WINRATE_THRESHOLD}%)"
    
    notify "PROACTIVE_ALERT" "🚨 ALERTA - WIN RATE BAJO
WR: ${win_rate}% (<${MIN_WINRATE_THRESHOLD}%) | PnL: \\$${total_pnl} USDT
${losses_count}/10 pérdidas
• Modelo desactualizado? Retrain manual si WR < 40%
• Monitorear 24h 🐕"
    
    # Actualizar estado
    alerts_state=$(echo "$alerts_state" | jq ".last_alert.low_winrate_time = $alert_time")
    alerts_sent=$((alerts_sent + 1))
else
    log "   ✅ Sin alerta (WR: ${win_rate}%)"
fi

# ════════════════════════════════════════════════════════
# CHECK 3: Pérdida diaria acercándose al límite
# ════════════════════════════════════════════════════════

log "📊 Check 3: Pérdida diaria (umbral: ${DAILY_LOSS_ALERT}%)..."
result=$(check_daily_loss)
daily_loss=$(echo "$result" | jq -r '.daily_loss // 0')
should_alert=$(echo "$result" | jq -r '.alert // false')
notified_today=$(echo "$result" | jq -r '.notified_today // false')

if [ "$should_alert" = "true" ]; then
    trades_count=$(echo "$result" | jq -r '.trades_count // 0')
    coins=$(echo "$result" | jq -r '.coins | join(", ") // "N/A"')
    notified=$(echo "$result" | jq -r '.notified_today // false')
    
    log "   🚨 ALERTA: Pérdida diaria \$${daily_loss} USDT (umbral: ${DAILY_LOSS_ALERT}%)"
    
    notify "PROACTIVE_ALERT" "🚨 ALERTA - PÉRDIDA DIARIA
\\$${daily_loss} USDT acumulados hoy | \\$$(awk "BEGIN {printf \"%.2f\", 15 - $daily_loss}") faltan para límite 3%
${trades_count} trades perdedores | ${coins} 🐕"
    
    # Actualizar estado solo si no habíamos notificado hoy
    if [ "$notified" = "false" ]; then
        today_str=$(date +%Y-%m-%d)
        alerts_state=$(echo "$alerts_state" | jq ".daily_loss_notified = true | .last_daily_loss_date = \"$today_str\"")
        alerts_sent=$((alerts_sent + 1))
    fi
else
    log "   ✅ Sin alerta (pérdida diaria: \$${daily_loss}, notificada: $notified_today)"
fi

# ════════════════════════════════════════════════════════
# RESUMEN Y GUARDAR ESTADO
# ════════════════════════════════════════════════════════

log ""
log "📊 Resumen: $alerts_sent alertas enviadas"

if [ $alerts_sent -eq 0 ]; then
    log "💤 Sistema operativo - Sin condiciones de riesgo detectadas"
fi

# Guardar estado actualizado
save_alerts_state "$alerts_state"

log ""
