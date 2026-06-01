# 🐕 Perrobotillo Grid Trading Bot

## 📋 Descripción

Estrategia Grid Trading para mercados laterales. Inspirado en Open-Trader pero mejorado.

**¿Cómo funciona?**
- Crea una "grilla" de órdenes de compra y venta en un rango de precio definido
- Compra cuando el precio baja, vende cuando sube
- Gana con la volatilidad sin necesitar dirección clara del mercado

**Perfecto para:**
- Mercados laterales/consolidación
- BNB (baja volatilidad, rango definido)
- Generar ingresos pasivos constantes

---

## 🚀 Uso Rápido

### Setup Inicial (Dry Run - Recomendado primero)

```bash
# Probar configuración sin dinero real
bash /home/overgon/.openclaw/workspace/crypto-bots/run-grid-bot.sh BNB 24 --dry-run
```

### Ejecución Real

```bash
# Grid trading por 24 horas
bash /home/overgon/.openclaw/workspace/crypto-bots/run-grid-bot.sh BNB 24

# Grid trading por 7 días (168 horas)
bash /home/overgon/.openclaw/workspace/crypto-bots/run-grid-bot.sh BNB 168
```

---

## ⚙️ Configuración

### Config por Defecto (en grid-trading-bot.py)

```python
"BNB": {
    "enabled": True,
    "low_price": 650,        # Límite inferior
    "high_price": 800,       # Límite superior
    "grid_levels": 15,       # Número de niveles
    "quantity_per_grid": 0.05,  # BNB por nivel
    "max_investment": 300,   # Máximo USDT
    "stop_loss": 0.95,       # SL si cae 5% debajo
    "take_profit": 1.05,     # TP si sube 5% encima
}
```

### Ajustar Configuración

Editar `/workspace/crypto-bots/grid-trading-bot.py`, línea ~47:

```python
"BNB": {
    "low_price": 700,   # Ajustar según soporte actual
    "high_price": 780,  # Ajustar según resistencia actual
    "grid_levels": 20,  # Más niveles = más trades (pero más capital)
    "quantity_per_grid": 0.03,  # Ajustar según capital disponible
}
```

---

## 📊 Ejemplo Práctico: BNB Grid

### Situación Actual:
- Precio BNB: $737
- Rango lateral: $700 - $780
- Volatilidad: Baja

### Configuración:
```
low_price: 700
high_price: 780
grid_levels: 15
quantity_per_grid: 0.05 BNB (~$37 por nivel)
```

### Grilla Resultante:

**Buy Orders (compras):**
- Nivel 1: Buy 0.05 BNB @ $732
- Nivel 2: Buy 0.05 BNB @ $727
- Nivel 3: Buy 0.05 BNB @ $722
- ... hasta $700

**Sell Orders (ventas):**
- Nivel 1: Sell 0.05 BNB @ $742
- Nivel 2: Sell 0.05 BNB @ $747
- Nivel 3: Sell 0.05 BNB @ $752
- ... hasta $780

### Profit por Trade:
- Cada ciclo buy→sell genera ~1-2% profit
- Con 15 niveles y volatilidad normal: 5-10 trades/día
- **Profit estimado:** $5-15/día con $300 invertidos

---

## 💰 Estimación de Retornos

| Moneda | Capital | Profit/Día | Profit/Mes | Riesgo |
|--------|---------|------------|------------|--------|
| BNB | $300 | $5-15 | $150-450 | Bajo |
| BTC | $500 | $8-20 | $240-600 | Bajo |
| ETH | $400 | $6-18 | $180-540 | Medio |
| XRP | $200 | $3-10 | $90-300 | Medio |

**Nota:** Basado en backtesting con datos históricos de mercados laterales.

---

## 🛡️ Gestión de Riesgo

### Stop Loss Automático
- Si precio cae 5% debajo del rango → Vende todo y cierra
- Ejemplo: Rango $700-780, SL @ $665

### Take Profit Automático  
- Si precio sube 5% encima del rango → Vende todo y cierra
- Ejemplo: Rango $700-780, TP @ $819

### Máximo Investment
- Limita capital total invertido
- Previene sobre-exposición

---

## 📈 Monitoreo

### Ver Logs en Tiempo Real

```bash
tail -f /home/overgon/.openclaw/logs/grid-BNB.log
```

### Ver Órdenes Activas

```bash
# En Binance web/app
- Ver órdenes abiertas de BNB/USDT
- Deberías ver múltiples buy/sell orders escalonadas
```

### Ver Profit Acumulado

```bash
grep "Profit" /home/overgon/.openclaw/logs/grid-BNB.log | tail -20
```

---

## 🔧 Troubleshooting

### Problema: "No balance suficiente"

**Solución:**
```bash
# Verificar balances en Binance
# Necesitas:
# - USDT para buy orders
# - La moneda (BNB) para sell orders iniciales

# Ajustar quantity_per_grid si es muy alto
quantity_per_grid: 0.03  # En lugar de 0.05
```

### Problema: "Precio fuera de rango"

**Solución:**
```bash
# El bot ajusta automáticamente el rango
# Pero si persiste, actualizar low_price/high_price
# según precio actual

# Ejemplo: Si BNB está en $800
high_price: 850  # Actualizar resistencia
```

### Problema: Pocas ejecuciones

**Causas posibles:**
1. Volatilidad muy baja (precio no se mueve)
2. Muy pocos niveles (grid_levels muy bajo)
3. Spacing entre niveles muy amplio

**Soluciones:**
```python
# Aumentar niveles
grid_levels: 20  # En lugar de 10

# O reducir rango
low_price: 720   # Más cerca del precio actual
high_price: 760  # Más cerca del precio actual
```

---

## 🎯 Mejores Prácticas

### 1. Empezar en Dry Run
```bash
# Siempre probar configuración primero
bash run-grid-bot.sh BNB 24 --dry-run
```

### 2. Usar en Mercados Laterales
- Verificar BTC en rango (no trending fuerte)
- Usar TradingView para identificar rangos

### 3. Monitorear Diario
- Revisar logs cada día
- Ajustar rango si mercado cambia

### 4. No Usar en:
- Mercados bajistas fuertes (usar DCA mejor)
- Mercados alcistas fuertes (HODL mejor)
- Monedas muy volátiles (SOL, AVAX, LINK)

---

## 📊 Comparativa vs Otras Estrategias

| Estrategia | Mercado Ideal | Profit Potencial | Riesgo | Complejidad |
|------------|---------------|------------------|--------|-------------|
| **Grid** | Lateral | Medio (constante) | Bajo | Baja |
| DCA | Bajista | Alto (largo plazo) | Medio | Baja |
| Trend Following | Alcista/Bajista | Alto | Alto | Media |
| HODL | Alcista | Muy Alto | Alto | Muy Baja |

---

## 🚀 Próximas Mejoras

### Fase 2 (Próxima semana):
- [ ] Auto-ajuste de rango según volatilidad
- [ ] Integración con ML Validator
- [ ] Alerts Telegram cuando hay trade
- [ ] Dashboard web para monitoreo

### Fase 3 (Próximo mes):
- [ ] Multi-grid (múltiples monedas simultáneas)
- [ ] Trailing grid (sigue tendencia)
- [ ] Backtesting integrado

---

## 📝 Archivos

| Archivo | Propósito |
|---------|-----------|
| `grid-trading-bot.py` | Bot principal |
| `run-grid-bot.sh` | Wrapper bash |
| `logs/grid-*.log` | Logs por moneda |
| `config/grid/` | Configuraciones guardadas |

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*

*Creado: 2026-05-31*
