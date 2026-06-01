# 🛡️ STOP LOSS PROTECTION UPDATE - 2026-06-01

## Contexto

Después del trade de BTC que perdió **-$40.48 USDT** (5.94% drop) el 2026-06-01 a las 06:10 AM, se identificó un patrón crítico:

### Estadísticas de BTC (últimos 10 trades):
- **SL Hits:** 6 (60%)
- **Wins:** 4 (40%)
- **P&L Total:** -$93.52 USDT 🔴

**Últimos 6 SL hits en BTC:**
1. -$40.48 - Jun 01 (este trade)
2. -$22.55 - May 29
3. -$11.86 - May 27
4. -$13.29 - May 22
5. -$9.71 - May 18
6. -$2.56 - May 17

---

## Cambios Implementados

### 1️⃣ STOP LOSS REDUCIDO (URGENTE)

**Archivo:** `crypto-trade-moneda-v3-slots.sh` (línea ~114)

```bash
declare -A STOP_LOSS_BY_COIN=(
    ["BTC"]="3.0"   # Antes: 5.5% → 3.0% (Evitar pérdidas >$20 USDT)
    ["ETH"]="3.5"   # Antes: 6.0% → 3.5%
    ["SOL"]="5.0"   # Antes: 8.0% → 5.0%
    ["LINK"]="4.0"  # Antes: 7.0% → 4.0%
    ["XRP"]="3.5"   # Antes: 6.0% → 3.5%
    ["BNB"]="3.0"   # Antes: 5.5% → 3.0%
    ["AVAX"]="4.5"  # Antes: 7.5% → 4.5%
)
```

**Impacto:**
- ✅ Máxima pérdida por trade en BTC: ~$20 USDT (en vez de $40)
- ✅ Protección más tight contra downtrends fuertes
- ⚠️ Posible aumento de SL hits por ruido (pero pérdidas menores)

---

### 2️⃣ PAUSE AUTOMÁTICO DESPUÉS DE 2 SL HITS CONSECUTIVOS

**Archivo:** `crypto-trade-moneda-v3-slots.sh` (línea ~2190)

**Mecanismo:**
- Después de **2 SL hits consecutivos** → PAUSE de **4 horas**
- Archivo de tracking: `crypto-bots/{COIN}-sl-tracking.json`
- Notificación automática por Telegram cuando se activa el pause

**Ejemplo de archivo de tracking:**
```json
{
  "consecutive_sl": 1,
  "last_sl_time": "2026-06-01T06:10:02",
  "pause_until": null,
  "total_sl_today": 1,
  "last_date": "2026-06-01"
}
```

**Cuando se activa el pause:**
```json
{
  "consecutive_sl": 2,
  "last_sl_time": "2026-06-01T09:30:00",
  "pause_until": "2026-06-01 13:30:00",
  "total_sl_today": 2,
  "last_date": "2026-06-01"
}
```

---

### 3️⃣ POSITION SIZE DINÁMICO

**Archivo:** `crypto-trade-moneda-v3-slots.sh` (línea ~2230)

**Reglas:**
- **0 SLs consecutivos:** 40% (normal)
- **1 SL consecutivo:** 30% (reducido)
- **2+ SLs consecutivos:** PAUSE (no entra)

**Código:**
```bash
if [ "$consecutive_sl" -eq 1 ]; then
    TRADE_PERCENT=30  # Reducir de 40% a 30%
    log "⚠️ Position size reducido: 40% → 30% (1 SL reciente)"
fi
```

---

### 4️⃣ TRACKING DE SL HITS POR MONEDA

**Función agregada:** `log_trade_to_history()` actualizada

**Características:**
- Trackea SLs consecutivos por moneda
- Trackea total de SLs por día
- Reset automático al inicio de cada día
- Reset de contador consecutivo cuando hay un WIN
- Alerta Telegram si hay 5+ SLs en un día

**Archivos creados:**
- `crypto-bots/BTC-sl-tracking.json`
- `crypto-bots/ETH-sl-tracking.json`
- `crypto-bots/SOL-sl-tracking.json`
- `crypto-bots/LINK-sl-tracking.json`
- `crypto-bots/XRP-sl-tracking.json`
- `crypto-bots/BNB-sl-tracking.json`
- `crypto-bots/AVAX-sl-tracking.json`

---

## Estado Actual (Después de Cambios)

### BTC:
- **Consecutive SLs:** 1 (después del trade de $40.48)
- **Position Size:** 30% (reducido automáticamente)
- **Próximo SL:** Si ocurre → PAUSE 4 horas activado
- **Nuevo Stop Loss:** 3.0% (~$20 USDT máx)

### Próximos Escenarios:

**Si BTC tiene un WIN:**
- Contador consecutivo → 0
- Position size → 40% (normal)

**Si BTC tiene otro SL:**
- Contador consecutivo → 2
- PAUSE automático por 4 horas
- Telegram notification enviada

---

## Beneficios Esperados

1. **Reducción de pérdidas máximas:** De $40 USDT a ~$20 USDT por trade
2. **Protección contra rachas perdedoras:** Pause automático después de 2 SLs
3. **Position sizing inteligente:** Menos riesgo después de pérdidas
4. **Visibilidad:** Tracking claro de SLs por moneda y por día
5. **Alertas proactivas:** Telegram notifications antes de que sea crítico

---

## Monitoreo Recomendado

1. Revisar archivos `crypto-bots/{COIN}-sl-tracking.json` diariamente
2. Monitorear win rate después de reducir SLs
3. Ajustar si hay demasiados SLs por ruido (podría necesitar 3.5% en vez de 3%)
4. Considerar agregar filtro de tendencia del mercado (ML)

---

## Créditos

Análisis original: Perrobotillo Trading Bot
Fecha: 2026-06-01
Motivo: Pérdida de -$40.48 USDT en BTC (trade #144)

*"Nunca confiar, siempre verificar"* 🐕
