#!/bin/bash
# ════════════════════════════════════════════════════════
# 📱 Telegram Notifications - Funciones Centralizadas v2
# ════════════════════════════════════════════════════════
# Formato optimizado: compacto, sin comillas extra, PnL (no P&L)
# Uso: source telegram-notifications.sh
# ════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE ORDENES
# ════════════════════════════════════════════════════════

notify_order_failed_minimum() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local order_value="$4" balance="$5"

    send_telegram "❌ ORDEN FALLÓ - ${symbol}
Slot ${slot_id}/${max_slots} | Order \$${order_value} < \$10 mínimo
Ajusta position_size o espera más capital 🛡️"
}

notify_order_failed_quantity() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local quantity="$4" price="$5" order_value="$6"

    send_telegram "❌ ORDEN FALLÓ - ${symbol}
Slot ${slot_id}/${max_slots} | Qty inválida (${quantity})
Order value: \$${order_value} 🛡️"
}

notify_order_failed_binance() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local error_msg="$4" error_code="$5" balance="$6" order_value="$7"

    send_telegram "❌ ORDEN FALLÓ - ${symbol}
Slot ${slot_id}/${max_slots} | ${error_msg}
Código: ${error_code} | Balance: \$${balance} | Order: \$${order_value} 🛡️"
}

notify_order_opened() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local fill_price="$4" quantity="$5"
    local usdt_spent="$6" fee_buy="$7"
    local tp1="$8" tp2="$9" tp3="${10}" sl="${11}"
    local tp1_pct="${12}" tp2_pct="${13}" tp3_pct="${14}"
    local mode="${15}"

    send_telegram "🟢 OPEN ${symbol} - ${mode} [Slot ${slot_id}/${max_slots}]
Entry: \$${fill_price} | Qty: ${quantity} | Cost: \$${usdt_spent} | Fee: -\$${fee_buy}
TP1: \$${tp1} (+${tp1_pct}%) | TP2: \$${tp2} (+${tp2_pct}%) | TP3: \$${tp3} (+${tp3_pct}%)
SL: -\$${sl} 🚀 Monitoreando..."
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE TP/SL
# ════════════════════════════════════════════════════════

notify_tp1_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5" pnl="$6"
    local recycling="${7:-false}"

    local msg="✅ TP1 ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | Qty: ${quantity} (35%) | PnL: +\$${pnl}"

    if [ "$recycling" = "true" ]; then
        msg="${msg}
🔄 RECICLAJE ACTIVADO - Nueva entrada 🚀"
    else
        msg="${msg}
ACUMULADO: 5% 📈 | 65% restante para TP2/TP3"
    fi

    send_telegram "$msg"
}

notify_tp2_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5" pnl="$6"

    send_telegram "✅ TP2 ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | Qty: ${quantity} (30%) | PnL: +\$${pnl}
ACUMULADO: 5% 📈 | 35% restante para TP3"
}

notify_tp3_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5"
    local pnl_total="$6" tp3_percentage="$7"
    local pnl_icon="${8:-✅}"

    send_telegram "${pnl_icon} TP3 ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | Qty: ${quantity} (${tp3_percentage})
PnL Total: +\$${pnl_total} ✅ Slot liberado 🎯"
}

notify_sl_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5"
    local pnl_icon="${6:-🛑}"

    send_telegram "${pnl_icon} SL HIT ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | PnL: \$${pnl}
Slot disponible para próximo trade 🛡️"
}

notify_scalp_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5" target="$6"
    local pnl_icon="${7:-🎯}"

    send_telegram "${pnl_icon} SCALP ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | PnL: +\$${pnl} | Target: ${target}%
✅ Ganancia rápida en mercado lateral 🚀"
}

notify_trailing_stop() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5" reason="$6"
    local pnl_icon="${7:-✅}"

    send_telegram "${pnl_icon} TRAILING STOP ${symbol} - \$${exit_price} [Slot ${slot_id}/${max_slots}]
Exit: \$${exit_price} | PnL: +\$${pnl} | Razón: ${reason}
✅ Ganancias aseguradas 🛡️"
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE RIESGO
# ════════════════════════════════════════════════════════

notify_risk_pause() {
    local symbol="$1" risk_level="$2" reason="$3"

    send_telegram "🛑 TRADING PAUSADO ${symbol}
🛡️ ML Risk: ${risk_level} | ${reason}
Esperar condiciones mejores 🐕"
}

notify_ml_override() {
    local auto_mode="$1" ml_mode="$2" confidence="$3" reason="$4"

    send_telegram "⚠️ ML OVERRIDE
Auto-Adjust: ${auto_mode} | ML: ${ml_mode} | Confianza: ${confidence}
${reason} ✅ Usando ML prediction"
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE ESTRATEGIA
# ════════════════════════════════════════════════════════

notify_strategy_update() {
    local mode="$1" reason="$2" override="$3"
    local tp1="$4" tp2="$5" tp3="$6" sl="$7"
    local position="$8" btc="$9" rsi="${10}" fg="${11}"
    local ml_confidence="${12}"

    send_telegram "🧠 AUTO-ADJUST + ML VALIDATION
Modo: ${mode} ${override}
TP1/TP2/TP3: +${tp1}%/+${tp2}%/+${tp3}% | SL: -${sl}% | Position: ${position}%
BTC: \$${btc} | RSI: ${rsi} | F&G: ${fg} | ML: ${ml_confidence}
✅ Estrategia validada y ajustada"
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE SISTEMA
# ════════════════════════════════════════════════════════

notify_system_status() {
    local status="$1" detail="$2" timestamp="$3"

    send_telegram "🔧 SYSTEM STATUS ${status}
${detail}
✅ ${timestamp}"
}

notify_daily_report() {
    local date="$1" portfolio="$2" pnl_24h="$3" win_rate="$4"
    local trades_today="$5" active_slots="$6" total_trades="$7"
    local net_pnl="$8"

    send_telegram "📊 REPORTE DIARIO ${date}
Portfolio: \$${portfolio} | PnL 24h: \$${pnl_24h} (${win_rate}% WR)
Trades hoy: ${trades_today} | Activos: ${active_slots} | Total: ${total_trades}
PnL Total: \$${net_pnl} 📈"
}
