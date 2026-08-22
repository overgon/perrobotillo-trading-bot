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
# 📈 CRITERIO 2: CONDICIONES DE MERCADO (BTC TREND)
# ════════════════════════════════════════════════════════
# Aprobación estricta: BTC debe estar en tendencia alcista confirmada
# (precio > EMA50 y EMA12 > EMA50) y volumen no deprimido.
# Se usa la propia API de Binance para historial 1h + pandas local.

check_btc_market_trend() {
    python3 << 'PYTHON_EOF'
import json
import urllib.request
import os
import sys

workspace = "/home/overgon/.openclaw/workspace"

try:
    # 1. Precio actual de BTC
    req = urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
    btc_price = float(json.loads(req.read())['price'])

    # 2. Datos históricos últimos ~110 velas 1h
    req_hist = urllib.request.urlopen(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=110",
        timeout=10
    )
    raw = json.loads(req_hist.read())
    closes = [float(k[4]) for k in raw]
    volumes = [float(k[5]) for k in raw]

    if len(closes) < 52:
        raise RuntimeError(f"Datos insuficientes: {len(closes)} velas")

    # 3. Medias móviles
    def ema(arr, span):
        m = 2.0 / (span + 1)
        out = [arr[0]]
        for i in range(1, len(arr)):
            out.append(arr[i] * m + out[-1] * (1 - m))
        return out[-1]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    ema50 = ema(closes, 50)
    avg_vol_20 = sum(volumes[-20:]) / 20.0
    last_vol = volumes[-1]

    # 4. Criterios estrictos
    bull_trend = btc_price > ema12 > ema50
    volume_ok = last_vol >= avg_vol_20 * 0.8
    ema12_cross = ema12 > ema50
    price_vs_ema50_pct = (btc_price - ema50) / ema50 * 100

    reasons = []
    reasons.append(f"BTC ${btc_price:,.2f} vs EMA50 ${ema50:,.2f} ({price_vs_ema50_pct:+.2f}%)")
    reasons.append(f"EMA12=${ema12:,.2f} EMA50=${ema50:,.2f} cross={ema12_cross}")
    reasons.append(f"Volumen vs avg20: {last_vol/avg_vol_20:.2f}x (ok={volume_ok})")

    approved = bool(bull_trend and volume_ok and ema12_cross)

    if approved:
        status = "APPROVED"
        reasons.append("BTC en tendencia alcista confirmada + volumen aceptable")
    else:
        status = "PENDING"
        reasons.append("Falta confirmación de tendencia/volumen para reanudar")

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
    
    # CRITERIO 1: Performance (WIN_RATE/racha)
    local perf_result=$(check_performance_criteria "$coin")
    local perf_status=$(echo "$perf_result" | cut -d'|' -f1)
    local perf_msg=$(echo "$perf_result" | cut -d'|' -f2-)
    
    log "   📊 Performance: $perf_msg"
    
    # CRITERIO 2: Mercado (tendencia BTC) - AHORA REQUERIDO
    local market_result=$(check_btc_market_trend)
    local market_status=$(echo "$market_result" | cut -d'|' -f1)
    local market_msg=$(echo "$market_result" | cut -d'|' -f2-)
    
    log "   📈 Mercado: $market_msg"
    
    # Decisión: AMBOS criterios deben aprobarse
    if [ "$perf_status" = "APPROVED" ] && [ "$market_status" = "APPROVED" ]; then
        log "✅ $coin: CRITERIOS CUMPLIDOS - Reanudando trading"
        
        # Remover pause flag
        rm -f "$pause_flag"
        
        # Notificar
        send_telegram "✅ TRADING REANUDADO ${coin}
Perf: ${perf_msg} | Mercado: ${market_msg} 🚀"
        
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
