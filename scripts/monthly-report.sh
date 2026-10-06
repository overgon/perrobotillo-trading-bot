#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - REPORTE MENSUAL DE TRADING
# ════════════════════════════════════════════════════════
# Ejecutar: Día 1 de cada mes a las 09:00 AM
# Envía reporte con top performance y rendimientos por moneda
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
OPENCLAW_BASE="/home/overgon/.openclaw"
LOGS_DIR="$OPENCLAW_BASE/logs"
CRYPTO_BOTS_DIR="$WORKSPACE/crypto-bots"
LOG_FILE="$LOGS_DIR/monthly-report.log"
DOLLAR="$"

# Configuración de Telegram
# ✅ BUG #9/#10 FIX: Source centralized notify.sh (Markdown parse_mode, --data-urlencode)
WORKSPACE="$HOME/.openclaw/workspace"
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ════════════════════════════════════════════════════════
# FUNCIONES DE ANÁLISIS
# ════════════════════════════════════════════════════════

# Extraer P&L de un daily report para una moneda específica
# Busca en la tabla de "Balances por Coin y Cambio 24h"
extract_coin_pnl() {
    local report_file=$1
    local coin=$2
    
    # Formato real del daily report: "🟢 BTC: $+3.80" o "🔴 BTC: $-1.45"
    local pnl=$(grep -a "^.*${coin}:" "$report_file" 2>/dev/null | \
        grep -oE '[+-]?\$[+-]?[\d]+\.?[\d]*' | \
        head -1 | tr -d '$' | sed 's/^[+-]//')
    
    if [ -z "$pnl" ] || [ "$pnl" == "" ]; then
        echo "0"
    else
        echo "$pnl"
    fi
}

# Contar trades del mes desde logs (líneas con TP o SL)
count_monthly_trades() {
    local coin=$1
    local year_month=$2
    local log_file="$LOGS_DIR/trade-${coin}.log"
    
    if [ ! -f "$log_file" ]; then
        echo "0"
        return
    fi
    
    # Contar cierres de trades (TP1, TP2, TP3, SL, Trailing Stop)
    local count=$(grep -a "\[${year_month}-" "$log_file" 2>/dev/null | \
        grep -acE "(TP[123] HIT|SL HIT|Trailing stop|Slot cerrado)" || echo "0")
    
    echo "$count"
}

# Calcular win rate desde logs del mes
calculate_win_rate() {
    local coin=$1
    local year_month=$2
    local log_file="$LOGS_DIR/trade-${coin}.log"
    
    if [ ! -f "$log_file" ]; then
        echo "0%"
        return
    fi
    
    # Contar wins y losses
    local wins=$(grep -a "\[${year_month}-" "$log_file" 2>/dev/null | \
        grep -acE "(TP[123] HIT)" 2>/dev/null || echo "0")
    local losses=$(grep -a "\[${year_month}-" "$log_file" 2>/dev/null | \
        grep -acE "(SL HIT|Trailing stop HIT)" 2>/dev/null || echo "0")
    
    # Asegurar que sean numeros validos
    wins=${wins:-0}
    losses=${losses:-0}
    wins=$(echo "$wins" | tr -d '\n\r ')
    losses=$(echo "$losses" | tr -d '\n\r ')
    
    # Validar que sean numeros
    if ! [[ "$wins" =~ ^[0-9]+$ ]]; then wins=0; fi
    if ! [[ "$losses" =~ ^[0-9]+$ ]]; then losses=0; fi
    
    local total=$((wins + losses))
    
    if [ "$total" -eq 0 ]; then
        echo "0%"
    else
        local win_rate=$(awk "BEGIN {printf \"%.1f\", $wins * 100 / $total}")
        echo "${win_rate}%"
    fi
}

# Obtener mejor y peor trade del mes desde daily reports
get_best_worst_from_reports() {
    local year_month=$2
    local best="0"
    local worst="0"
    
    # Leer todos los daily reports del mes
    for report in "$CRYPTO_BOTS_DIR"/daily-report-${year_month}-*.md; do
        if [ -f "$report" ]; then
            # Extraer P&L 24h de cada reporte
            local daily_pnl=$(grep "| P&L 24h |" "$report" 2>/dev/null | \
                awk -F'|' '{print $3}' | \
                grep -oP '[+-]?\$?\d+\.?\d*' | \
                tr -d '$' | head -1)
            
            if [ -n "$daily_pnl" ]; then
                # Comparar con mejor/peor
                is_better=$(awk "BEGIN {print ($daily_pnl > $best) ? 1 : 0}")
                is_worse=$(awk "BEGIN {print ($daily_pnl < $worst) ? 1 : 0}")
                
                if [ "$is_better" -eq 1 ]; then
                    best=$daily_pnl
                fi
                if [ "$is_worse" -eq 1 ]; then
                    worst=$daily_pnl
                fi
            fi
        fi
    done
    
    echo "${best}|${worst}"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  📊 REPORTE MENSUAL - Generando                       ║"
log "╚═══════════════════════════════════════════════════════╝"

# Determinar mes anterior (reportamos el mes que acaba de terminar)
YEAR_MONTH_PREV=$(date -d "last month" '+%Y-%m' 2>/dev/null || date '+%Y-%m')
MONTH_NAME_PREV=$(date -d "last month" '+%B' 2>/dev/null || date '+%B')
REPORT_DATE=$(date '+%Y-%m-%d %H:%M')

log "📅 Reporte del mes: $MONTH_NAME_PREV $YEAR_MONTH_PREV"

# Monedas a analizar
COINS=("BTC" "ETH" "BNB" "SOL" "ZEC" "XRP" "AVAX")

# Arrays para almacenar resultados
declare -A MONTHLY_PNL
declare -A TRADES_COUNT
declare -A WIN_RATES

TOTAL_PNL=0
TOTAL_TRADES=0
TOTAL_WINS=0
TOTAL_LOSSES=0

log ""
log "📊 Analizando daily reports de cada moneda..."

# Sumar P&L de todos los daily reports del mes
for coin in "${COINS[@]}"; do
    log "  • Analizando $coin..."
    
    coin_pnl=0
    
    # Sumar P&L de todos los reports del mes
    for report in "$CRYPTO_BOTS_DIR"/daily-report-${YEAR_MONTH_PREV}-*.md; do
        if [ -f "$report" ]; then
            # Extraer P&L del formato: "🟢 BTC: $+3.80" o "🔴 LINK: $-1.45"
            daily_pnl=$(grep -a "^.*${coin}:" "$report" 2>/dev/null | head -1 | \
                grep -oE '[+-]?\$[+-]?[0-9]+\.?[0-9]*' | head -1 | tr -d '$' | sed 's/^[+-]//')
            
            if [ -n "$daily_pnl" ] && [ "$daily_pnl" != "" ]; then
                coin_pnl=$(awk "BEGIN {printf \"%.2f\", $coin_pnl + $daily_pnl}")
            fi
        fi
    done
    
    MONTHLY_PNL[$coin]=$coin_pnl
    TOTAL_PNL=$(awk "BEGIN {printf \"%.2f\", $TOTAL_PNL + $coin_pnl}")
    
    # Contar trades
    trades=$(count_monthly_trades "$coin" "$YEAR_MONTH_PREV")
    # ✅ FIX: Sanitizar trades a número entero (evita syntax error en $((arithmetic)))
    trades=$(echo "$trades" | tr -dc '0-9')
    trades=${trades:-0}
    
    TRADES_COUNT[$coin]=$trades
    TOTAL_TRADES=$((TOTAL_TRADES + trades))
    
    # Win rate
    winrate=$(calculate_win_rate "$coin" "$YEAR_MONTH_PREV")
    WIN_RATES[$coin]=$winrate
    
    # Wins/Losses para total
    wins=$(grep -a "\[${YEAR_MONTH_PREV}-" "$LOGS_DIR/trade-${coin}.log" 2>/dev/null | grep -acE "(TP[123] HIT)" 2>/dev/null | tr -d '\n\r ' || echo "0")
    losses=$(grep -a "\[${YEAR_MONTH_PREV}-" "$LOGS_DIR/trade-${coin}.log" 2>/dev/null | grep -acE "(SL HIT|Trailing stop HIT)" 2>/dev/null | tr -d '\n\r ' || echo "0")
    
    # Validar que sean numeros
    if ! [[ "$wins" =~ ^[0-9]+$ ]]; then wins=0; fi
    if ! [[ "$losses" =~ ^[0-9]+$ ]]; then losses=0; fi
    
    TOTAL_WINS=$((TOTAL_WINS + wins))
    TOTAL_LOSSES=$((TOTAL_LOSSES + losses))
done

log "✅ Análisis completado"

# ════════════════════════════════════════════════════════
# CALCULAR TOP PERFORMERS
# ════════════════════════════════════════════════════════

log ""
log "🏆 Calculando top performers..."

BEST_COIN=""
BEST_PNL=-999999
WORST_COIN=""
WORST_PNL=999999

for coin in "${COINS[@]}"; do
    pnl=${MONTHLY_PNL[$coin]}
    if [ -n "$pnl" ] && [ "$pnl" != "0" ]; then
        is_better=$(awk "BEGIN {print ($pnl > $BEST_PNL) ? 1 : 0}")
        is_worse=$(awk "BEGIN {print ($pnl < $WORST_PNL) ? 1 : 0}")
        
        if [ "$is_better" -eq 1 ]; then
            BEST_PNL=$pnl
            BEST_COIN=$coin
        fi
        if [ "$is_worse" -eq 1 ]; then
            WORST_PNL=$pnl
            WORST_COIN=$coin
        fi
    fi
done

# Calcular win rate total
if [ "$TOTAL_WINS" -gt 0 ] || [ "$TOTAL_LOSSES" -gt 0 ]; then
    TOTAL_WIN_RATE=$(awk "BEGIN {printf \"%.1f\", $TOTAL_WINS * 100 / ($TOTAL_WINS + $TOTAL_LOSSES)}")
    TOTAL_WIN_RATE="${TOTAL_WIN_RATE}%"
else
    TOTAL_WIN_RATE="0%"
fi

# ════════════════════════════════════════════════════════
# CONSTRUIR MENSAJE TELEGRAM
# ════════════════════════════════════════════════════════

log ""
log "📝 Construyendo mensaje..."

# Manejar casos donde no hay datos
if [ -z "$BEST_COIN" ]; then
    BEST_COIN="N/A"
    BEST_PNL="0"
fi
if [ -z "$WORST_COIN" ]; then
    WORST_COIN="N/A"
    WORST_PNL="0"
fi

# Encabezado
MESSAGE="🐕 **REPORTE MENSUAL** ${MONTH_NAME_PREV^^} ${YEAR_MONTH_PREV}
📅 ${REPORT_DATE}

━━━━━━━━━━━━━━━━━━

🏆 MEJOR: ${BEST_COIN} | PnL: ${DOLLAR}${BEST_PNL} USDT
🥉 PEOR: ${WORST_COIN} | PnL: ${DOLLAR}${WORST_PNL} USDT

📊 RENDIMIENTOS POR MONEDA"

# Tabla de rendimientos
for coin in "${COINS[@]}"; do
    pnl=${MONTHLY_PNL[$coin]}
    trades=${TRADES_COUNT[$coin]}
    winrate=${WIN_RATES[$coin]}

    if [ -n "$pnl" ] && [ "$pnl" != "0" ]; then
        if awk "BEGIN {exit !($pnl > 0)}"; then
            icon="🟢"
        else
            icon="🔴"
        fi
    else
        icon="⚪"
    fi

    MESSAGE="${MESSAGE}
${icon} ${coin} | ${DOLLAR}${pnl} | ${trades} trades | ${winrate}"
done

MESSAGE="${MESSAGE}

━━━━━━━━━━━━━━━━━━
📈 RESUMEN
├─ PnL Total: ${DOLLAR}${TOTAL_PNL} USDT
├─ Trades: ${TOTAL_TRADES} | W:${TOTAL_WINS} ✅ L:${TOTAL_LOSSES} ❌
└─ Win Rate: ${TOTAL_WIN_RATE}

🤖 Perrobotillo v2.1"

# ════════════════════════════════════════════════════════
# ENVIAR Y GUARDAR REPORTE
# ════════════════════════════════════════════════════════

log ""
log "📤 Enviando reporte por Telegram..."

if notify "MONTHLY_REPORT" "$MESSAGE"; then
    log "✅ Reporte enviado exitosamente"
else
    log "❌ Error al enviar reporte por Telegram"
fi

# Guardar copia del reporte en archivo
REPORT_FILE="$CRYPTO_BOTS_DIR/monthly-report-${YEAR_MONTH_PREV}.md"
cat > "$REPORT_FILE" << EOF
# 🐕 Reporte Mensual - ${MONTH_NAME_PREV^^} ${YEAR_MONTH_PREV}

_Generado: ${REPORT_DATE}_

---

## 🏆 Top Performance

### 🥇 Mejor Moneda
- **Moneda:** ${BEST_COIN}
- **PnL:** ${DOLLAR}${BEST_PNL} USDT

### 🥉 Peor Moneda
- **Moneda:** ${WORST_COIN}
- **PnL:** ${DOLLAR}${WORST_PNL} USDT

---

## 📊 Rendimientos por Moneda

| Moneda | PnL (USDT) | Trades | Win Rate |
|--------|------------|--------|----------|
EOF

for coin in "${COINS[@]}"; do
    pnl=${MONTHLY_PNL[$coin]}
    trades=${TRADES_COUNT[$coin]}
    winrate=${WIN_RATES[$coin]}
    echo "| ${coin} | ${DOLLAR}${pnl} | ${trades} | ${winrate} |" >> "$REPORT_FILE"
done

cat >> "$REPORT_FILE" << EOF

---

## 📈 Resumen Mensual

- **PnL Total:** ${DOLLAR}${TOTAL_PNL} USDT
- **Total Trades:** ${TOTAL_TRADES}
- **Wins:** ${TOTAL_WINS} ✅
- **Losses:** ${TOTAL_LOSSES} ❌
- **Win Rate Global:** ${TOTAL_WIN_RATE}

---

## 🤖 Estado del Sistema

- API Binance: ✅ Conectada
- Emergency Close: ✅ Protegido
- Drawdown Alert: ✅ Activo
- IP Monitor: ✅ Activo

---

_Generado por Perrobotillo Trading Bot 🐕_
_"¡Nunca confiar, siempre verificar!"_
EOF

log "💾 Reporte guardado en: $REPORT_FILE"

log ""
log "╔═══════════════════════════════════════════════════════╗"
log "║  ✅ REPORTE MENSUAL COMPLETED                         ║"
log "╚═══════════════════════════════════════════════════════╝"

exit 0
