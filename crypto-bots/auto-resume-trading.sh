#!/bin/bash
# ════════════════════════════════════════════════════════
# 🚀 AUTO-RESUME TRADING - Reactivación Automática
# Verifica si BTC/ETH (u otras monedas pausadas) deben reanudarse
# Criterios: Performance + Condiciones de Mercado
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
LOG_FILE="/home/overgon/.openclaw/logs/auto-resume.log"
TRADE_HISTORY="$WORKSPACE/crypto-bots/trade-history.json"
DYNAMIC_CONFIG="$WORKSPACE/crypto-bots/dynamic-config.env"

COINS=("BTC" "ETH" "BNB" "SOL" "LINK" "XRP" "AVAX")

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_json="/home/overgon/.openclaw/openclaw.json"
    local chat_id="7543955537"
    
    if [ -f "$config_json" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_json" 2>/dev/null)
        if [ -n "$bot_token" ]; then
            curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" \
                -d "chat_id=$chat_id" \
                -d "text=$message" \
                -d "parse_mode=Markdown" > /dev/null 2>&1
        fi
    fi
}

# ════════════════════════════════════════════════════════
# 📊 CRITERIO 1: PERFORMANCE (Win Rate Reciente)
# ════════════════════════════════════════════════════════

check_performance_criteria() {
    local coin="$1"
    
    if [ ! -f "$TRADE_HISTORY" ]; then
        echo "NO_DATA|No hay trade-history.json"
        return
    fi
    
    # Analizar últimos 10 trades de esta moneda
    python3 << PYTHON_EOF
import json
from datetime import datetime, timezone

coin = "$coin"
trade_history = "$TRADE_HISTORY"

try:
    with open(trade_history, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', []) if isinstance(data, dict) else data
    
    # Filtrar trades de esta moneda
    coin_trades = [t for t in trades if t.get('symbol') == coin]
    
    if len(coin_trades) == 0:
        print("NO_TRADES|Sin trades recientes")
        exit()
    
    # Ordenar por timestamp (más reciente primero)
    coin_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Últimos 10 trades
    recent = coin_trades[:10]
    wins = [t for t in recent if t.get('pnlUSDT', 0) > 0]
    
    win_rate = len(wins) / len(recent) * 100 if len(recent) > 0 else 0
    
    # Verificar rachas ganadoras consecutivas
    consecutive_wins = 0
    for t in recent:
        if t.get('pnlUSDT', 0) > 0:
            consecutive_wins += 1
        else:
            break
    
    # Criterios de aprobación
    approved = False
    reason = []
    
    if win_rate >= 50:
        approved = True
        reason.append(f"Win Rate {win_rate:.1f}% >= 50%")
    
    if consecutive_wins >= 5:
        approved = True
        reason.append(f"{consecutive_wins} wins consecutivos")
    
    if approved:
        print(f"APPROVED|{'; '.join(reason)} | WR={win_rate:.1f}% | Consec={consecutive_wins}")
    else:
        print(f"PENDING|Win Rate {win_rate:.1f}% < 50%, sin racha ganadora | Consec={consecutive_wins}")

except Exception as e:
    print(f"ERROR|{str(e)}")
PYTHON_EOF
}

# ════════════════════════════════════════════════════════
# 📈 CRITERIO 2: CONDICIONES DE MERCADO
# ════════════════════════════════════════════════════════

check_market_conditions() {
    python3 << 'PYTHON_EOF'
import json
import urllib.request
import os

workspace = "/home/overgon/.openclaw/workspace"
dynamic_config = f"{workspace}/crypto-bots/dynamic-config.env"

try:
    # Obtener precio actual de BTC
    req = urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    btc_price = float(json.loads(req.read())['price'])
    
    # Calcular EMA20 (simplificado - obtener de datos históricos)
    import pandas as pd
    historical_file = f"{workspace}/backtest/data/BTCUSDT_historical.csv"
    
    if os.path.exists(historical_file):
        df = pd.read_csv(historical_file).tail(30)
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        ema20 = df['ema20'].iloc[-1]
    else:
        ema20 = 0
    
    # Leer Fear & Greed del config dinámico
    fg_value = 22  # Default
    try:
        with open(dynamic_config, 'r') as f:
            for line in f:
                if 'FG_VALUE=' in line:
                    fg_value = int(line.split('=')[1].strip().strip('"'))
                    break
    except:
        pass
    
    # Criterios de aprobación
    approved = False
    reasons = []
    
    # BTC > EMA20
    if btc_price > ema20:
        reasons.append(f"BTC ${btc_price:.0f} > EMA20 ${ema20:.0f}")
    else:
        reasons.append(f"BTC ${btc_price:.0f} < EMA20 ${ema20:.0f}")
    
    # Fear & Greed > 40
    if fg_value > 40:
        reasons.append(f"F&G {fg_value} > 40 (optimismo)")
    else:
        reasons.append(f"F&G {fg_value} < 40 (miedo)")
    
    # Aprobado si AMBOS criterios se cumplen
    if btc_price > ema20 and fg_value > 40:
        approved = True
        status = "APPROVED"
    else:
        status = "PENDING"
    
    print(f"{status}|{' | '.join(reasons)}")

except Exception as e:
    print(f"ERROR|{str(e)}")
PYTHON_EOF
}

# ════════════════════════════════════════════════════════
# 🚀 VERIFICAR Y REANUDAR
# ════════════════════════════════════════════════════════

check_and_resume_coin() {
    local coin="$1"
    local pause_flag="$WORKSPACE/crypto-bots/${coin}-ml-pause-flag.json"
    
    # Verificar si está pausada
    if [ ! -f "$pause_flag" ]; then
        log "✅ $coin: No está pausada"
        return
    fi
    
    # Leer estado actual
    local paused=$(jq -r '.paused // false' "$pause_flag" 2>/dev/null)
    if [ "$paused" != "true" ]; then
        log "✅ $coin: Ya está activa (paused=false)"
        return
    fi
    
    log "⏸️ $coin: Verificando criterios de reactivación..."
    
    # CRITERIO 1: Performance
    local perf_result=$(check_performance_criteria "$coin")
    local perf_status=$(echo "$perf_result" | cut -d'|' -f1)
    local perf_msg=$(echo "$perf_result" | cut -d'|' -f2-)
    
    log "   📊 Performance: $perf_msg"
    
    # CRITERIO 2: Mercado
    local market_result=$(check_market_conditions)
    local market_status=$(echo "$market_result" | cut -d'|' -f1)
    local market_msg=$(echo "$market_result" | cut -d'|' -f2-)
    
    log "   📈 Mercado: $market_msg"
    
    # Decisión: Al menos UN criterio debe aprobarse
    if [ "$perf_status" = "APPROVED" ] || [ "$market_status" = "APPROVED" ]; then
        log "✅ $coin: CRITERIOS CUMPLIDOS - Reanudando trading"
        
        # Remover pause flag
        rm -f "$pause_flag"
        
        # Notificar
        send_telegram "✅ TRADING REANUDADO - $coin

📊 Performance: $perf_msg
📈 Mercado: $market_msg

🚀 Bot reactivado automáticamente - Monitoreando TPs...

*Nota:* La reactivación fue automática porque al menos uno de los criterios se cumplió:
• Win Rate últimos 10 trades ≥ 50% O 5+ wins consecutivos
• O BTC > EMA20 Y Fear & Greed > 40

¡Nunca confiar, siempre verificar! 🐕"
        
        return 0
    else
        log "⏸️ $coin: Criterios NO cumplidos - Mantiene pausa"
        return 1
    fi
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🚀 AUTO-RESUME CHECK - Verificando reactivaciones   ║"
log "╚═══════════════════════════════════════════════════════╝"

resumed_count=0

for coin in "${COINS[@]}"; do
    check_and_resume_coin "$coin"
    if [ $? -eq 0 ]; then
        resumed_count=$((resumed_count + 1))
    fi
done

log ""
log "📊 Resumen: $resumed_count monedas reanudadas"

if [ $resumed_count -eq 0 ]; then
    log "💤 No hubo reactivaciones - Todas las monedas pausadas mantienen criterios pendientes"
fi

log ""
