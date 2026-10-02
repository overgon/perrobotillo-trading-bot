# 🧪 Paper Trading Guide - Validación Sin Riesgo

## 📋 ¿Qué es Paper Trading?

**Paper Trading** es un modo de simulación que te permite:
- Operar con dinero **VIRTUAL** (no real)
- Usar precios **REALES** del mercado
- Probar estrategias **SIN RIESGO** financiero
- Validar configuraciones antes de invertir

**Ideal para:**
- ✅ Testear Grid Trading por primera vez
- ✅ Validar nueva configuración de parámetros
- ✅ Familiarizarse con el bot
- ✅ Medir profit potencial realista

---

## 🚀 Cómo Usar

### Modo Paper Trading (Default)

```bash
# Ejecutar Grid Trading en modo Paper por 24 horas
python3 /workspace/crypto-bots/grid-trading-bot-v2.py --coin BNB --hours 24

# O usar el wrapper bash
bash /workspace/crypto-bots/run-grid-bot.sh BNB 24
```

### Modo Live Trading (Dinero Real)

```bash
# Solo después de validar en Paper Trading!
python3 /workspace/crypto-bots/grid-trading-bot-v2.py --coin BNB --hours 24 --live
```

---

## 💰 Configuración Inicial

### Balances Virtuales

| Moneda | Balance Inicial | Propósito |
|--------|----------------|-----------|
| USDT | $1000 | Capital para compras |
| Coin (BNB, etc.) | 0.0 | Se adquiere con buys |

**Nota:** Los balances son virtuales solo en modo Paper Trading.

### Parámetros por Defecto (BNB)

```python
Rango: $650 - $800
Niveles: 15
Spacing: ~$10 entre niveles
Cantidad: 0.05 BNB (~$35-37) por nivel
Stop Loss: 5% debajo del rango
Take Profit: 5% encima del rango
```

---

## 📊 Métricas a Monitorear

### Durante la Ejecución

El bot mostrará logs cada 2 minutos:

```
[2026-05-31 16:13:33] 🧪 PAPER BUY 0.05 @ $700.62
[2026-05-31 16:15:45] 🧪 PAPER SELL ejecutada: 0.05 @ $720.62
[2026-05-31 16:15:45] 🧪 PAPER 🎯 Trade completado, profit: $1.00
[2026-05-31 16:15:45] 🧪 PAPER 💰 Profit acumulado: $1.00
```

### Ver Logs en Tiempo Real

```bash
tail -f /workspace/logs/grid-BNB-paper.log
```

### Ver Status Completo

El bot muestra status cada hora:
```
╔═══════════════════════════════════════════════════════╗
║  📊 STATUS DEL GRID
╚═══════════════════════════════════════════════════════╝
💵 USDT Virtual:    $950.00
🪙 BNB Virtual:     0.75
📊 Total Value:    $1015.50

📈 Trades:         3
💰 Profit Total:   $15.50
📊 Precio Actual:  $710.62
📋 Órdenes Activas: 11
```

---

## 🎯 Qué Buscar en Paper Trading

### ✅ Señales de que Funciona Bien:

1. **Trades constantes**: 5-15 trades por día
2. **Profit positivo**: $5-15/día con $1000 virtuales
3. **Órdenes se llenan**: Buy y sell orders ejecutándose
4. **Precio en rango**: No rompió SL ni TP del rango

### ⚠️ Señales de Alerta:

1. **Cero trades**: Precio fuera de rango o muy poca volatilidad
2. **Profit negativo**: Configuración incorrecta
3. **Muchos trades sin profit**: Spacing muy pequeño
4. **Precio rompió rango**: Necesita ajustar low/high price

---

## 🔧 Ajustar Configuración Basado en Resultados

### Problema: Pocas Ejecuciones

**Causa:** Rango muy estrecho o precio fuera de rango

**Solución:**
```python
# Ampliar rango
low_price: 680   # Antes: 700
high_price: 820  # Antes: 780

# O reducir spacing (más niveles)
grid_levels: 20  # Antes: 15
```

### Problema: Profit Muy Bajo

**Causa:** Spacing muy pequeño entre niveles

**Solución:**
```python
# Reducir niveles (más spacing)
grid_levels: 10  # Antes: 20

# O aumentar cantidad por nivel
quantity_per_grid: 0.08  # Antes: 0.05
```

### Problema: Precio Rompió Rango

**Causa:** Mercado salió de consolidación

**Solución:**
```python
# Esperar a que mercado se estabilice
# O ajustar rango al nuevo precio

# Si precio subió mucho:
low_price: 750   # Nuevo soporte
high_price: 850  # Nueva resistencia
```

---

## 📈 Criterios para Pasar a Live Trading

### ✅ Checklist Pre-Live:

- [ ] Paper Trading por **mínimo 48 horas**
- [ ] **Profit positivo** consistente ($5+/día)
- [ ] **Mínimo 10 trades** ejecutados
- [ ] Precio se mantuvo **en rango** la mayoría del tiempo
- [ ] Entendés cómo funciona el bot
- [ ] Configura ción ajustada y probada

### 🎯 Capital Inicial Recomendado:

| Nivel | Capital | Riesgo | Recomendado Para |
|-------|---------|--------|------------------|
| Mínimo | $50 | Bajo | Primera vez |
| Moderado | $100-200 | Medio | Con experiencia |
| Avanzado | $300-500 | Alto | Muy probado |

---

## 💡 Estrategia de Transición Paper → Live

### Semana 1: Paper Trading Intensivo
```bash
# Probar diferentes configuraciones
python3 grid-trading-bot-v2.py --coin BNB --hours 24
python3 grid-trading-bot-v2.py --coin BTC --hours 24
python3 grid-trading-bot-v2.py --coin ETH --hours 24
```

**Objetivo:** Encontrar mejor configuración por moneda

### Semana 2: Live Trading con Capital Mínimo
```bash
# Empezar con $50-100 reales
python3 grid-trading-bot-v2.py --coin BNB --hours 168 --live
```

**Objetivo:** Validar que live funciona igual que paper

### Semana 3+: Escalar Gradualmente
```bash
# Aumentar capital si funciona
# BNB: $100 → $200 → $300
# Agregar más monedas
```

**Objetivo:** Maximizar profit minimizando riesgo

---

## 📊 Comparativa Paper vs Live

| Aspecto | Paper Trading | Live Trading |
|---------|---------------|--------------|
| **Riesgo** | Cero | Real |
| **Balances** | Virtuales ($1000) | Reales (los tuyos) |
| **Órdenes** | Simuladas | Reales en Binance |
| **Slippage** | No considerado | Considerado |
| **Fees** | Estimados (0.1%) | Reales (0.1%) |
| **Emoción** | Ninguna | Estrés/Ansiedad |
| **Utilidad** | Testing/Validación | Profit real |

---

## 🛡️ Gestión de Riesgo en Paper Trading

### Errores Comunes a Evitar:

❌ **Saltar a live muy rápido** (< 24h paper)  
❌ **No ajustar configuración** cuando no funciona  
❌ **Ignorar señales de alerta** (precio fuera de rango)  
❌ **Usar capital grande** sin validación suficiente  

### Mejores Prácticas:

✅ **Minimum 48h paper trading** antes de live  
✅ **Ajustar basado en datos** reales del log  
✅ **Empezar con capital mínimo** ($50-100)  
✅ **Escalar gradualmente** si funciona  
✅ **Documentar resultados** de cada configuración  

---

## 📁 Archivos y Logs

### Logs Generados:

```
/workspace/logs/
├── grid-BNB-paper.log    # Paper trading BNB
├── grid-BTC-paper.log    # Paper trading BTC
├── grid-BNB-live.log     # Live trading BNB
└── grid-trading.log      # Log general
```

### Ver Logs por Moneda:

```bash
# Ver últimas 50 líneas
tail -50 /workspace/logs/grid-BNB-paper.log

# Seguir en tiempo real
tail -f /workspace/logs/grid-BNB-paper.log

# Buscar trades específicos
grep "ejecutada" /workspace/logs/grid-BNB-paper.log
```

---

## 🎯 Ejemplo Real de Uso

### Día 1: Paper Trading Inicial

```bash
# Iniciar paper trading BNB
python3 grid-trading-bot-v2.py --coin BNB --hours 24
```

**Resultado después de 24h:**
- Trades: 12
- Profit: $18.50
- Precio en rango: ✅
- **Conclusión:** Configuración funciona, continuar

### Día 2-3: Optimización

```bash
# Ajustar rango basado en Day 1
# Editar grid-trading-bot-v2.py línea ~47
"BNB": {
    "low_price": 690,   # Ajustado de 650
    "high_price": 790,  # Ajustado de 800
    "grid_levels": 12,  # Reducido de 15
}

# Ejecutar con config optimizada
python3 grid-trading-bot-v2.py --coin BNB --hours 24
```

**Resultado después de 48h total:**
- Trades totales: 28
- Profit total: $42.00
- Promedio/día: $21.00
- **Conclusión:** Listo para live trading

### Día 4: Live Trading con Capital Mínimo

```bash
# Empezar con $100 reales
python3 grid-trading-bot-v2.py --coin BNB --hours 168 --live
```

---

## 📞 Troubleshooting

### "No se ejecutan trades"

**Verificar:**
1. Precio actual está dentro del rango
2. Hay suficiente volatilidad
3. Balances virtuales son suficientes

**Solución:**
```bash
# Verificar precio actual
python3 -c "import ccxt; print(ccxt.binance().fetch_ticker('BNB/USDT')['last'])"

# Ajustar rango si es necesario
# Editar low_price y high_price en config
```

### "Profit negativo"

**Posibles causas:**
1. Fees > profit por trade (spacing muy pequeño)
2. Precio se movió en contra
3. Configuración incorrecta

**Solución:**
```python
# Aumentar spacing entre niveles
grid_levels: 10  # Reducir de 20 a 10

# O verificar que quantity_per_grid sea adecuado
quantity_per_grid: 0.05  # Mínimo para cubrir fees
```

---

## 🎓 Aprendizajes Clave

### Lo que Paper Trading te Enseña:

1. **Volatilidad real** de cada moneda
2. **Timing** de ejecuciones de órdenes
3. **Impacto de fees** en profit
4. **Configuración óptima** para cada moneda
5. **Gestión emocional** (antes de arriesgar dinero real)

### Cuándo Paper Trading NO es Suficiente:

❌ Mercados con **slippage alto** (baja liquidez)  
❌ Estrategias de **alta frecuencia** (< 1 min)  
❌ Cuando necesitás validar **latencia de ejecución**  

En estos casos: Paper Trading → Live con capital MÍNIMO → Escalar

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*

*Creado: 2026-05-31*
