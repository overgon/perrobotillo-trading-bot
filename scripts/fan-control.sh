#!/bin/bash
# ════════════════════════════════════════════════════════
# 🌀 PERROBOTILLO FAN CONTROL - AUTOMATIZADO POR TEMPERATURA
# ════════════════════════════════════════════════════════
# Controla el ventilador de la RPi5 basado en temperatura
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

LOG_FILE="$HOME/.openclaw/logs/fan-control.log"
PWM_FAN="/sys/class/hwmon/hwmon2/pwm1"
PWM_ENABLE="/sys/class/hwmon/hwmon2/pwm1_enable"

# ════════════════════════════════════════════════════════
# ⚙️ CONFIGURACIÓN DE TEMPERATURA
# ════════════════════════════════════════════════════════

TEMP_OFF=38      # Apagar ventilador (<38°C)
TEMP_LOW=50      # Velocidad baja (38-50°C) - Optimizado para menos ruido
TEMP_MED=65      # Velocidad media (50-65°C) - Optimizado para menos ruido
TEMP_HIGH=75     # Velocidad alta (65-75°C) - Máximo solo en caso de necesidad
TEMP_MAX=80      # Velocidad máxima (>80°C) - Seguro límite RPi5 (throttling @ 85°C)

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

get_temp() {
    vcgencmd measure_temp | cut -d"'" -f1 | cut -d"=" -f2
}

set_pwm() {
    local pwm=$1
    echo 1 | sudo tee "$PWM_ENABLE" > /dev/null 2>&1
    echo $pwm | sudo tee "$PWM_FAN" > /dev/null 2>&1
}

# ════════════════════════════════════════════════════════
# 🌡️ CONTROL POR TEMPERATURA
# ════════════════════════════════════════════════════════

TEMP=$(get_temp)
CURRENT_PWM=$(cat "$PWM_FAN" 2>/dev/null || echo "0")

# Determinar velocidad según temperatura
if (( $(echo "$TEMP < $TEMP_OFF" | bc -l) )); then
    PWM=0
    STATUS="OFF"
elif (( $(echo "$TEMP < $TEMP_LOW" | bc -l) )); then
    PWM=40      # 16% - Muy bajo (reducido ruido al mínimo)
    STATUS="LOW"
elif (( $(echo "$TEMP < $TEMP_MED" | bc -l) )); then
    PWM=120     # 47% - Bajo (reducido ruido)
    STATUS="MEDIUM-LOW"
elif (( $(echo "$TEMP < $TEMP_HIGH" | bc -l) )); then
    PWM=190     # 75% - Medio
    STATUS="MEDIUM"
elif (( $(echo "$TEMP < $TEMP_MAX" | bc -l) )); then
    PWM=230     # 90% - Alto
    STATUS="HIGH"
else
    PWM=255     # 100% - Máximo
    STATUS="MAX"
fi

# Solo cambiar si hay diferencia significativa (evita flickering)
PWM_DIFF=$((PWM - CURRENT_PWM))
if [ $PWM_DIFF -lt 0 ]; then
    PWM_DIFF=$((-PWM_DIFF))
fi

if [ $PWM_DIFF -gt 30 ] || { [ "$CURRENT_PWM" -eq 0 ] && [ "$PWM" -gt 0 ]; }; then
    set_pwm $PWM
    log "🌡️ Temp: ${TEMP}°C | 🌀 Fan: ${PWM}/255 (${STATUS}) | Prev: ${CURRENT_PWM}"
else
    # Mismo estado, no loguear para no llenar el log
    :
fi

# ════════════════════════════════════════════════════════
# 📊 SALIDA PARA DEBUG (opcional)
# ════════════════════════════════════════════════════════

echo "Temp: ${TEMP}°C | Fan: ${PWM}/255 (${STATUS})"
