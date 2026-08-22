#!/bin/bash
# ════════════════════════════════════════════════════════
# 📱 Telegram Notifications - Funciones Centralizadas
# ════════════════════════════════════════════════════════
# Funciones reutilizables para notificaciones del bot
# Uso: source telegram-notifications.sh
# ════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE ÓRDENES
# ════════════════════════════════════════════════════════

notify_order_failed_minimum() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local order_value="$4" balance="$5"
    
    send_telegram "❌ ORDEN FALLÓ - $symbol

Slot: $slot_id / $max_slots
Razón: Order value \$${order_value} < \$10 mínimo

Ajusta position_size o espera más capital. 🛡️"
}

notify_order_failed_quantity() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local quantity="$4" price="$5" order_value="$6"
    
    send_telegram "❌ ORDEN FALLÓ - $symbol

Slot: $slot_id / $max_slots
Razón: Quantity inválida ($quantity)

Revisa configuración del bot. 🛡️"
}

notify_order_failed_binance() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local error_msg="$4" error_code="$5"
    local balance="$6" order_value="$7"
    
    send_telegram "❌ ORDEN FALLÓ - $symbol

Slot: $slot_id / $max_slots
Razón: $error_msg
Código: $error_code

Balance: \$${balance} | Order: \$${order_value} 🛡️"
}

notify_order_opened() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local fill_price="$4" quantity="$5"
    local usdt_spent="$6" fee_buy="$7"
    local tp1="$8" tp2="$9" tp3="${10}" sl="${11}"
    local tp1_pct="${12}" tp2_pct="${13}" tp3_pct="${14}"
    local mode="${15}"
    
    send_telegram "🟢 ORDEN ABIERTA - $symbol [$mode]
Slot: $slot_id / $max_slots
Entry: \$${fill_price} | Qty: $quantity
Costo: \$${usdt_spent} | Fee: -\$${fee_buy}
Objetivos:
TP1: \$${tp1} (+${tp1_pct}%)
TP2: \$${tp2} (+${tp2_pct}%)
TP3: \$${tp3} (+${tp3_pct}%)
Stop Loss: \$${sl}
🚀 Trade activo - Monitoreando TPs..."
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE TP/SL
# ════════════════════════════════════════════════════════

notify_tp1_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5" pnl="$6"
    local recycling="${7:-false}"
    
    local msg="✅ TP1 HIT - $symbol [35%] 🎯
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
Qty: $quantity (35%)
PnL: \$${pnl}"
    
    if [ "$recycling" = "true" ]; then
        msg="$msg
🔄 MODO RECICLAJE ACTIVADO
El slot buscará nueva entrada 🚀"
    else
        msg="$msg
ACUMULADO: 5% 📈
Quedan 65% para TP2/TP3 🎯"
    fi
    
    send_telegram "$msg"
}

notify_tp2_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5" pnl="$6"
    
    send_telegram "✅ TP2 HIT - $symbol [30%] 🎯
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
Qty: $quantity (30%)
PnL Parcial: \$${pnl}
ACUMULADO: 5% 📈
Queda 35% para TP3 🎯"
}

notify_tp3_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" quantity="$5"
    local pnl_total="$6" tp3_percentage="$7"
    local pnl_icon="${8:-✅}"
    
    send_telegram "${pnl_icon} TP3 HIT - $symbol [${tp3_percentage}] 🎯
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
Qty: $quantity
ACUMULADO: 5% 📈
PnL Total: \$${pnl_total}
✅ Slot cerrado y disponible 🎯"
}

notify_sl_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5"
    local pnl_icon="${6:-🛑}"
    
    send_telegram "${pnl_icon} SL HIT - $symbol
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
PnL: \$${pnl}
El slot está disponible para próximo trade. 🛡️"
}

notify_scalp_hit() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5" target="$6"
    local pnl_icon="${7:-🎯}"
    
    send_telegram "${pnl_icon} SCALP HIT - $symbol 🎯
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
PnL: \$${pnl}
Target: ${target}%
✅ Ganancia rápida en mercado lateral 🚀"
}

notify_trailing_stop() {
    local symbol="$1" slot_id="$2" max_slots="$3"
    local exit_price="$4" pnl="$5" reason="$6"
    local pnl_icon="${7:-✅}"
    
    send_telegram "${pnl_icon} TRAILING STOP - $symbol
Slot: $slot_id / $max_slots
Exit: \$${exit_price}
PnL: \$${pnl}
Razón: $reason
✅ Ganancias aseguradas 🛡️"
}

# ════════════════════════════════════════════════════════
# NOTIFICACIONES DE RIESGO
# ════════════════════════════════════════════════════════

notify_risk_pause() {
    local symbol="$1" risk_level="$2" reason="$3"
    
    send_telegram "🛑 TRADING PAUSADO - $symbol

🛡️ ML Risk Detector: Riesgo ${risk_level}
${reason}

Se recomienda esperar condiciones mejores. 🐕"
}

notify_ml_override() {
    local auto_mode="$1" ml_mode="$2" confidence="$3" reason="$4"
    
    send_telegram "⚠️ ML VALIDATION OVERRIDE

🤖 Auto-Adjust: $auto_mode
🧠 ML Classifier: $ml_mode
📊 Confianza: $confidence

Motivo: $reason

✅ Usando ML prediction por alta confianza"
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

🎯 Modo Final: ${mode}
${override}

📝 Razón: ${reason}

📊 Configuración:
TP1: +${tp1}%
TP2: +${tp2}%
TP3: +${tp3}%
SL: -${sl}%
Position: ${position}%

📈 Contexto:
BTC: \$${btc}
RSI: ${rsi}
F&G: ${fg}
ML Confianza: ${ml_confidence}

✅ Estrategia validada y ajustada"
}
