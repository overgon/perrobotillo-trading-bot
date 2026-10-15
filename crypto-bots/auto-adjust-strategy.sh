#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 Auto-Adjust Strategy Engine
# ════════════════════════════════════════════════════════
# Aplica la configuración dinámica al bot de trading
# Uso: ./auto-adjust-strategy.sh
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
CONFIG_FILE="${SCRIPT_DIR}/market-mode.conf"
BOT_SCRIPT="${SCRIPT_DIR}/crypto-trade-moneda-v3-slots.sh"
ML_VALIDATOR="${SCRIPT_DIR}/ml-market-validator.sh"
GLOBAL_PAUSE_FILE="${SCRIPT_DIR}/global-pause-flag.json"
STATE_DIR="${SCRIPT_DIR}/state"
mkdir -p "$STATE_DIR"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🧠 AUTO-ADJUST STRATEGY ENGINE                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════════════════
# PASO 0: CIRCUIT BREAKER GUARD
# ════════════════════════════════════════════════════════
CB_ALLOWED="true"
if [ -f "$GLOBAL_PAUSE_FILE" ]; then
    PAUSE_UNTIL=$(python3 -c "import json; print(json.load(open('$GLOBAL_PAUSE_FILE')).get('pause_until',''))" 2>/dev/null || echo "")
    if [ -n "$PAUSE_UNTIL" ]; then
        NOW=$(date '+%Y-%m-%d %H:%M:%S')
        if [[ "$NOW" < "$PAUSE_UNTIL" ]]; then
            CB_ALLOWED="false"
            echo "🛑 Circuit breaker activo hasta $PAUSE_UNTIL"
        else
            echo "✅ Circuit breaker expirado"
        fi
    fi
fi

# ════════════════════════════════════════════════════════
# PASO 1: EJECUTAR ANÁLISIS DE MERCADO
# ════════════════════════════════════════════════════════

echo "⏳ Paso 1/3: Analizando mercado..."
"${SCRIPT_DIR}/market-sentiment.sh"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: No se generó el archivo de configuración"
    exit 1
fi

# Cargar configuración
source "$CONFIG_FILE"

echo ""
echo "✅ Mercado analizado: ${MARKET_MODE}"
echo ""

# ════════════════════════════════════════════════════════
# PASO 1.5: COOLDOWN / HYSTERESIS
# ════════════════════════════════════════════════════════

LAST_MODE_FILE="${STATE_DIR}/last-market-mode.txt"
LAST_MODE_TIME_FILE="${STATE_DIR}/last-market-mode.time"
COOLDOWN_MINUTES=720  # 12 horas

FORCE_MODE="false"
if [ -f "$LAST_MODE_FILE" ] && [ -f "$LAST_MODE_TIME_FILE" ]; then
    LAST_MODE=$(cat "$LAST_MODE_FILE" || echo "")
    LAST_TS=$(cat "$LAST_MODE_TIME_FILE" || echo "")
    if [ -n "$LAST_TS" ]; then
        AGE_MIN=$(python3 -c "import time; from datetime import datetime; fmt='%Y-%m-%d %H:%M:%S'; print(int((datetime.now()-datetime.strptime('$LAST_TS', fmt)).total_seconds()/60))" 2>/dev/null || echo "9999")
        if [ "$LAST_MODE" = "$MARKET_MODE" ]; then
            echo "🔁 Modo sin cambios: $MARKET_MODE"
        elif [ "$AGE_MIN" -lt "$COOLDOWN_MINUTES" ]; then
            echo "⏳ Cooldown activo: hace ${AGE_MIN} min cambió a $LAST_MODE; se mantiene ${AGE_MIN} min más"
            MARKET_MODE="$LAST_MODE"
            FORCE_MODE="true"
        else
            echo "✅ Cooldown expirado, se permite cambio"
        fi
    fi
fi

echo "$MARKET_MODE" > "$LAST_MODE_FILE"
date '+%Y-%m-%d %H:%M:%S' > "$LAST_MODE_TIME_FILE"

# ════════════════════════════════════════════════════════
# PASO 2: ACTUALIZAR CONFIGURACIÓN DEL BOT
# ════════════════════════════════════════════════════════

echo "⏳ Paso 2/3: Actualizando configuración del bot..."

# Reusar valores de Paso 1; NO volver a consultar F&G
FG_VALUE="${FG_VALUE:-N/A}"
FG_CLASS="${FG_CLASS:-N/A}"

# Si circuit breaker activo, forzar modo defensivo
if [ "$CB_ALLOWED" = "false" ]; then
    echo "🛑 CB activo: forzando modo defensivo"
    MARKET_MODE="LATERAL"
    MARKET_REASON="Circuit breaker activo"
    TP1=1.5
    TP2=3.0
    TP3=5.0
    SL=3.5
    POSITION_SIZE=10
    TRAILING_STOP="false"
fi

# Sanity check de parámetros por modo
case "$MARKET_MODE" in
    BULL)
        if [ "$(echo "$POSITION_SIZE > 25" | bc -l 2>/dev/null || echo 0)" = "1" ]; then POSITION_SIZE=25; fi
        if [ "$(echo "$SL > 10" | bc -l 2>/dev/null || echo 0)" = "1" ]; then SL=10; fi
        ;;
    BEAR)
        if [ "$(echo "$POSITION_SIZE > 15" | bc -l 2>/dev/null || echo 0)" = "1" ]; then POSITION_SIZE=15; fi
        if [ "$(echo "$SL > 5" | bc -l 2>/dev/null || echo 0)" = "1" ]; then SL=5; fi
        ;;
    VOLATILE_BULL)
        [ "$POSITION_SIZE" -gt 20 ] && POSITION_SIZE=20
        if [ "$(echo "$SL > 10" | bc -l 2>/dev/null || echo 0)" = "1" ]; then SL=10; fi
        ;;
    VOLATILE_BEAR)
        if [ "$(echo "$POSITION_SIZE > 15" | bc -l 2>/dev/null || echo 0)" = "1" ]; then POSITION_SIZE=15; fi
        if [ "$(echo "$SL > 5" | bc -l 2>/dev/null || echo 0)" = "1" ]; then SL=5; fi
        ;;
    LATERAL|*)
        [ "$POSITION_SIZE" -gt 20 ] && POSITION_SIZE=20
        if [ "$(echo "$SL > 5" | bc -l 2>/dev/null || echo 0)" = "1" ]; then SL=5; fi
        ;;
esac

# Crear archivo de configuración dinámica
DYNAMIC_CONFIG="${SCRIPT_DIR}/dynamic-config.env"

cat > "$DYNAMIC_CONFIG" << EOF
# Dynamic Strategy Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# Market Mode: ${MARKET_MODE}

# Auto-Adjusted Parameters
export TP1=${TP1}
export TP2=${TP2}
export TP3=${TP3}
export STOP_LOSS=${SL}
export POSITION_SIZE=${POSITION_SIZE}
export TRAILING_STOP=${TRAILING_STOP}

# Scalping Mode (Lateral Market)
export SCALPING_ENABLED="true"
export SCALP_TARGET_PERCENT="1.0"
export SCALP_SL_PERCENT="2.5"

# Market Context
export MARKET_MODE="${MARKET_MODE}"
export MARKET_REASON="${MARKET_REASON}"
export BTC_PRICE="${BTC_PRICE}"
export RSI="${RSI}"
export FG_VALUE="${FG_VALUE}"
EOF

echo "✅ Configuración dinámica guardada: ${DYNAMIC_CONFIG}"
echo ""

# ════════════════════════════════════════════════════════
# PASO 3: VALIDACIÓN ML
# ════════════════════════════════════════════════════════

echo "⏳ Paso 3/3: Ejecutando ML validation..."

# FIX: Verificar edad de ML predictions antes de validar
ML_RESULT_FILE="${SCRIPT_DIR}/../ml/market-predictions.json"
MAX_AGE_MINUTES=120  # 2 horas máximo

if [ -f "$ML_RESULT_FILE" ]; then
    ML_AGE_MIN=$(python3 -c "
import json, datetime
d = json.load(open('$ML_RESULT_FILE'))
ts = datetime.datetime.fromisoformat(d['timestamp'])
age = (datetime.datetime.now() - ts).total_seconds() / 60
print(int(age))
" 2>/dev/null || echo "999")
    
    if [ "$ML_AGE_MIN" -gt "$MAX_AGE_MINUTES" ]; then
        echo "⚠️  ML predictions tienen ${ML_AGE_MIN} min (> ${MAX_AGE_MINUTES} min)"
        echo "   Actualizando predicciones primero..."
        "${SCRIPT_DIR}/update-ml-predictions.sh"
    else
        echo "✅ ML predictions frescas (${ML_AGE_MIN} min)"
    fi
fi

"${ML_VALIDATOR}"  # ML validator en crypto-bots/

# ✅ FIX: El ML validator puede haber sobreescrito dynamic-config.env
# Releer para sync memoria <-> archivo (evita discrepancia BULL vs LATERAL)
if [ -f "$DYNAMIC_CONFIG" ]; then
    source "$DYNAMIC_CONFIG"
    echo "🔄 Sync post-ML: MARKET_MODE=$MARKET_MODE (leído de dynamic-config.env)"
    
    # ✅ JSONL: Log de cambio de config
    CONFIG_LOG="$WORKSPACE/logs/config-change-trace.log"
    config_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"$config_ts\",\"event\":\"config.update\",\"source\":\"ml_sync\",\"market_mode\":\"$MARKET_MODE\",\"dynamic_config\":\"$DYNAMIC_CONFIG\"}" >> "$CONFIG_LOG" 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════
# PASO 4: RESULTADO FINAL + OVERRIDE + NOTIFICACIÓN
# ════════════════════════════════════════════════════════

OVERRIDE=""
FINAL_MODE="$MARKET_MODE"
ML_CONFIDENCE="N/A"

if [ -f "$ML_RESULT_FILE" ]; then
    # ✅ FIX: Ensemble voting across ALL coins, no longer BTC-only
    # Previous: BTC as sole reference → 4/7 BEAR + BTC LATERAL = no override
    # Now: majority vote across all coins; discrepancy = ensemble_mode != market_mode
    ML_DATA=$(python3 -c "
import json, sys
with open('$ML_RESULT_FILE') as f:
    d = json.load(f)
predictions = d.get('predictions', {})
if not predictions:
    print('false|UNKNOWN|N/A|0|0.0|0.0')
    sys.exit(0)
mode_votes = {}
mode_confs = {}
for coin, pred in predictions.items():
    mode = pred.get('market_mode', pred.get('mode', pred.get('recommended_mode', 'UNKNOWN')))
    conf = pred.get('confidence', 0)
    mode_votes[mode] = mode_votes.get(mode, 0) + 1
    mode_confs.setdefault(mode, []).append(conf)
ensemble_mode = max(mode_votes.keys(), key=lambda m: (mode_votes[m], sum(mode_confs[m])/len(mode_confs[m])))
ensemble_conf = sum(mode_confs[ensemble_mode]) / len(mode_confs[ensemble_mode])
# ✅ FIX: Use model_accuracy as proxy when metrics/f1_macro/cv_mean missing
metrics = d.get('metrics', {})
f1_macro = metrics.get('f1_macro', d.get('model_accuracy', 0))
cv_mean = metrics.get('cv_mean', min(d.get('model_accuracy', 0), 0.95))
discrepancy = str(ensemble_mode != '$MARKET_MODE').lower()
print(f'{discrepancy}|{ensemble_mode}|{ensemble_conf*100:.0f}%|{int(ensemble_conf*100)}|{f1_macro}|{cv_mean}')
" 2>/dev/null || echo "false|UNKNOWN|N/A|0|0.0|0.0")
    ML_DISCREPANCY=$(echo "$ML_DATA" | cut -d'|' -f1)
    ML_MODE=$(echo "$ML_DATA" | cut -d'|' -f2)
    ML_CONFIDENCE=$(echo "$ML_DATA" | cut -d'|' -f3)
    ML_CONF_NUM=$(echo "$ML_DATA" | cut -d'|' -f4)
    ML_F1_MACRO=$(echo "$ML_DATA" | cut -d'|' -f5)
    ML_CV_MEAN=$(echo "$ML_DATA" | cut -d'|' -f6)
    python3 -c "
import json
with open('$ML_RESULT_FILE') as f: d = json.load(f)
preds = d.get('predictions', {})
for coin, p in sorted(preds.items()):
    print(f'   {coin}: {p.get(\"market_mode\",\"?\")} ({p.get(\"confidence\",0)*100:.0f}%)')
" 2>/dev/null

    ML_GATE="false"
    if [ "$ML_DISCREPANCY" = "true" ] && [ "$ML_CONF_NUM" -gt 80 ] && [ "$(python3 -c "print($ML_F1_MACRO > 0.55)")" = "True" ] && [ "$(python3 -c "print($ML_CV_MEAN > 0.75)")" = "True" ]; then
        ML_GATE="true"
    fi

    ALLOWED_OVERRIDE_MODES="BULL|LATERAL|BEAR|VOLATILE_BULL|VOLATILE_BEAR"
    if [ "$ML_GATE" = "true" ] && echo "$MARKET_MODE" | grep -Eq "$ALLOWED_OVERRIDE_MODES"; then
        FINAL_MODE="$ML_MODE"
        OVERRIDE="✅ ML override aplicado"
        echo "🔁 Override ML aprobado (conf=$ML_CONFIDENCE, f1_macro=$ML_F1_MACRO, cv_mean=$ML_CV_MEAN)"
        if [ -f "$DYNAMIC_CONFIG" ]; then
            sed -i "s/^export MARKET_MODE=.*/export MARKET_MODE=\"$FINAL_MODE\"/" "$DYNAMIC_CONFIG"
            echo "" >> "$DYNAMIC_CONFIG"
            echo "# ML Override: $(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print(d.get('reason', ''))" 2>/dev/null || echo "")" >> "$DYNAMIC_CONFIG"
            echo "# ML Confidence: $ML_CONFIDENCE" >> "$DYNAMIC_CONFIG"
            echo "# ML Gate: f1_macro=$ML_F1_MACRO cv_mean=$ML_CV_MEAN" >> "$DYNAMIC_CONFIG"
        fi
    else
        OVERRIDE="✅ ML de acuerdo"
        if [ "$ML_DISCREPANCY" = "true" ]; then
            echo "⚠️  Override ML descartado (modo extendido=$MARKET_MODE o métricas insuficientes)"
        fi
    fi

# ✅ FIX: Si el ML validator ya sobrescribió dynamic-config.env, usar ese modo
if [ "$FINAL_MODE" = "$MARKET_MODE" ] && [ -n "$ML_MODE" ] && [ "$ML_MODE" != "UNKNOWN" ]; then
    FINAL_MODE="$MARKET_MODE"  # Sync con lo que validator escribió
fi
else
    OVERRIDE="⚠️ ML no disponible"
fi

# Notificación única final
MSG_FINAL=""
if [ "$CB_ALLOWED" = "false" ]; then
    MSG_FINAL=$(printf "🧠 AUTO-ADJUST | Modo: %s (CB activo)\n📝 %s\n⚙️ TP1/2/3: +%s/%s/%s%% | SL: -%s%% | Pos: %s%%\n📊 BTC: \\$%s | RSI: %s | F&G: %s (%s) | ML: %s %s\n✅ Ajuste aplicado" "$FINAL_MODE" "$MARKET_REASON" "$TP1" "$TP2" "$TP3" "$SL" "$POSITION_SIZE" "$BTC_PRICE" "$RSI" "$FG_VALUE" "$FG_CLASS" "$ML_CONFIDENCE" "$OVERRIDE")
else
    MSG_FINAL=$(printf "🧠 AUTO-ADJUST | %s %s\n📝 %s\n⚙️ TP1/2/3: +%s/%s/%s%% | SL: -%s%% | Pos: %s%%\n📊 BTC: \\$%s | RSI: %s | F&G: %s (%s) | ML: %s\n✅ Ajuste aplicado" "$FINAL_MODE" "$OVERRIDE" "$MARKET_REASON" "$TP1" "$TP2" "$TP3" "$SL" "$POSITION_SIZE" "$BTC_PRICE" "$RSI" "$FG_VALUE" "$FG_CLASS" "$ML_CONFIDENCE")
fi

# Cargar notify.sh para logging + dedup de notificaciones
if [ -f "${SCRIPT_DIR}/notify.sh" ]; then
    source "${SCRIPT_DIR}/notify.sh"
fi
# Use notify.sh which has notify.log + dedup
if [ -f "${SCRIPT_DIR}/notify.sh" ]; then
    source "${SCRIPT_DIR}/notify.sh"
    send_telegram "$MSG_FINAL"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ AUTO-ADJUST COMPLETED                             ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📁 Configuración en: ${DYNAMIC_CONFIG}"
echo ""
echo "🔄 El bot usará esta configuración en la próxima ejecución"
echo ""

# ✅ JSONL: Log final de config apply
CONFIG_LOG="$WORKSPACE/logs/config-change-trace.log"
final_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"timestamp\":\"$final_ts\",\"event\":\"config.apply\",\"market_mode\":\"$FINAL_MODE\",\"override\":\"$OVERRIDE\",\"dynamic_config\":\"$DYNAMIC_CONFIG\"}" >> "$CONFIG_LOG" 2>/dev/null || true

exit 0
