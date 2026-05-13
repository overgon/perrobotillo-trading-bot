#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  CONFIGURACIÓN DE CAPITAL - ESTRATEGIA 20/80          ║
# ║  Actualizado: 2026-04-22 12:55 CST                    ║
# ╚═══════════════════════════════════════════════════════╝

# ════════════════════════════════════════════════════════
# ESTRATEGIA 20/80
# ════════════════════════════════════════════════════════
HOLD_PERCENT=20        # % para holding (largo plazo)
TRADE_PERCENT=80       # % para trading (activo)

# ════════════════════════════════════════════════════════
# TRADE SETTINGS
# ════════════════════════════════════════════════════════
TRADE_POSITION_PERCENT=  # % del capital de trading por trade
MIN_TRADE_SIZE=10          # USDT mínimo con margen (Binance = $5-10)

# ════════════════════════════════════════════════════════
# CAPITAL REAL CONFIRMADO (2026-04-22 12:54 CST)
# ACTUALIZADO 2026-05-02: Reducido exposición por mercado lateral
# ════════════════════════════════════════════════════════
TOTAL_PORTFOLIO=2700   # USDT (aproximado)
HOLDING_CAPITAL=540    # 20% (en crypto)
TRADING_CAPITAL=1100   # 80% (USDT líquido)
PER_COIN=157           # $1100 / 7 coins

# ════════════════════════════════════════════════════════
# GESTIÓN DE RIESGO - MERCADO LATERAL (2026-05-02)
# ════════════════════════════════════════════════════════
# Reducir exposición en consolidación hasta romper rango
MAX_ACTIVE_SLOTS=14    # Máximo slots activos (antes: 21)
# Reactivar slots completos cuando BTC rompa $77,750 o $78,600

# ════════════════════════════════════════════════════════
# ALERTAS DE USDT
# ════════════════════════════════════════════════════════
USDT_WARNING_THRESHOLD=100   # Alerta si trading < $100
USDT_CRITICAL_THRESHOLD=50   # Crítico si trading < $50

# ════════════════════════════════════════════════════════
# DUST MANAGEMENT
# ════════════════════════════════════════════════════════
DUST_THRESHOLD=5       # Auto-vender si < $5

# ════════════════════════════════════════════════════════
# FUNCIONES DE CÁLCULO
# ════════════════════════════════════════════════════════

# Calcular tamaño de trade basado en balance USDT
calc_trade_size() {
    local balance=$1
    local trade_capital=$(awk -v b="$balance" -v p="$TRADE_PERCENT" 'BEGIN {printf "%.2f", b * p / 100}')
    local trade_size=$(awk -v c="$trade_capital" -v p="$TRADE_POSITION_PERCENT" 'BEGIN {printf "%.2f", c * p / 100}')
    echo "$trade_size"
}

# Calcular capital de trading (80% del balance)
calc_trade_capital() {
    local balance=$1
    awk -v b="$balance" -v p="$TRADE_PERCENT" 'BEGIN {printf "%.2f", b * p / 100}'
}

# Verificar si trade cumple mínimo
validate_trade_size() {
    local trade_size=$1
    if (( $(awk -v t="$trade_size" -v m="$MIN_TRADE_SIZE" 'BEGIN {print (t < m) ? 1 : 0}') )); then
        return 1  # Inválido
    fi
    return 0  # Válido
}

# Verificar alerta de USDT bajo
check_usdt_alert() {
    local balance=$1
    if (( $(awk -v b="$balance" -v t="$USDT_CRITICAL_THRESHOLD" 'BEGIN {print (b < t) ? 1 : 0}') )); then
        echo "CRITICAL"
        return 2
    elif (( $(awk -v b="$balance" -v t="$USDT_WARNING_THRESHOLD" 'BEGIN {print (b < t) ? 1 : 0}') )); then
        echo "WARNING"
        return 1
    fi
    echo "OK"
    return 0
}

# ════════════════════════════════════════════════════════
# EJEMPLO DE USO
# ════════════════════════════════════════════════════════
# source config/capital-config.sh
# trade_size=$(calc_trade_size 1100)  # Retorna: 352.00 (80% de 1100 = 880, 40% de 880 = 352)
# validate_trade_size 352 && echo "Trade válido"
# check_usdt_alert 50  # Retorna: CRITICAL
