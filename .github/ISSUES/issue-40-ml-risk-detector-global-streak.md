# #40 - 🐛 ML Risk Detector usa racha de pérdidas GLOBAL en lugar de por moneda

**Estado:** ✅ FIXED  
**Reportado:** 2026-05-21 11:45 CST  
**Fixeado:** 2026-05-21 11:50 CST  
**Labels:** `bug` `ml` `risk-detector` `fixed`  
**Commit:** pending

---

## 📋 Descripción

El ML Risk Detector (`ml/ml-drawdown-check.sh`) estaba evaluando el riesgo usando la racha de pérdidas **global** (todas las monedas combinadas) en lugar de calcular la racha **específica de cada moneda**.

Esto causaba que monedas con buen performance (como SOL con TP1 hit reciente) fueran pausadas injustamente por pérdidas de otras monedas (BTC, ETH, LINK, etc.).

---

## 🐛 Síntomas

**Reporte de usuario:**
```
🛑 TRADING PAUSADO - SOL
🛡️ ML Risk Detector: Riesgo ALTO
Racha de 7 pérdidas consecutivas
```

**Pero SOL individualmente:**
- Solo 3 pérdidas consecutivas (15-16 mayo)
- TP1 hit exitoso el 21-05-2026 11:33 AM (+$0.44 USDT)
- Sin pérdidas recientes

**Racha global (todas las monedas):**
- 12 pérdidas consecutivas (16-18 mayo)
- Afectó a BTC, ETH, LINK, AVAX, SOL, XRP

---

## 🔍 Causa Raíz

En `ml/ml-drawdown-check.sh`, el código Python usaba todos los trades sin filtrar por símbolo:

```python
# ❌ CÓDIGO ANTERIOR (BUG)
df_trades = []
for t in trades:
    df_trades.append({
        'timestamp': ts,
        'pnl': float(t.get('pnlUSDT', 0)),
        'symbol': t.get('symbol', '')
    })

# Racha de pérdidas (últimos 10 trades GLOBALES)
recent = df_trades[-10:] if len(df_trades) >= 10 else df_trades
```

**Problema:** La variable `recent` contenía trades de **todas las monedas**, no solo de la moneda siendo evaluada (`$SYMBOL`).

---

## ✅ Solución

Agregar filtrado por símbolo antes de calcular features:

```python
# ✅ CÓDIGO NUEVO (FIX)
# Filtrar trades por símbolo específico
symbol_trades = [t for t in df_trades if t['symbol'] == '$SYMBOL']

# Racha de pérdidas (últimos 10 trades DE ESTA MONEDA)
recent = symbol_trades[-10:] if len(symbol_trades) >= 10 else symbol_trades
```

**Aplicado en dos secciones:**
1. Reglas hard-coded de emergencia (líneas ~70-95)
2. Modelo ML histórico (líneas ~210-230)

---

## 🧪 Testing

**Antes del fix:**
```bash
$ bash ml/ml-drawdown-check.sh SOL
HIGH_RISK|PAUSE|0|Racha de 7 pérdidas consecutivas
```

**Después del fix:**
```bash
$ bash ml/ml-drawdown-check.sh SOL
LOW_RISK|NORMAL|40|Riesgo bajo - ML histórico permite operar (confianza: 71.5%)
```

**Validación con todas las monedas:**
```
BTC:  LOW_RISK|NORMAL|40 (71.4%)
ETH:  LOW_RISK|NORMAL|40 (79.2%)
BNB:  LOW_RISK|NORMAL|40 (68.4%)
SOL:  LOW_RISK|NORMAL|40 (71.5%)
LINK: LOW_RISK|NORMAL|40 (74.5%)
XRP:  LOW_RISK|NORMAL|40 (68.0%)
AVAX: LOW_RISK|NORMAL|40 (77.4%)
```

---

## 📊 Impacto

**Antes:**
- SOL pausado injustamente por pérdidas de otras monedas
- Oportunidades de trading perdidas cuando una moneda tiene buen performance
- Falsa sensación de "riesgo alto" cuando el problema era aislado

**Después:**
- Cada moneda evaluada individualmente
- Monedas con buen performance pueden seguir operando
- Pausas solo cuando la moneda específica tiene problemas reales

---

## 🛡️ Prevención Futura

- [ ] Agregar test unitario que verifique filtrado por símbolo
- [ ] Documentar que cada métrica debe ser por-moneda, no global
- [ ] Revisar otros scripts ML para bugs similares
- [ ] Agregar logging que muestre cuántos trades se usaron en el cálculo

---

## 📝 Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `ml/ml-drawdown-check.sh` | Agregar filtrado `symbol_trades` en 2 secciones |
| `ml/ml-drawdown-check.sh` | Fix import `os` en sección ML histórico |
| `ml/ml-drawdown-check.sh` | Cambiar lógica de salida para "USE_ML" |

---

## 🔗 Referencias

- **Comentario de usuario:** "Perrobotillo veo que SOL esta a la alza y acaba de hacer TP1 Hit slot 2 pero al mismo tiempo ML Risk Detector pauso trading con SOL"
- **Histórico SOL:** 3 pérdidas consecutivas (15-16 mayo), TP1 hit 21-mayo
- **Histórico global:** 12 pérdidas consecutivas (16-18 mayo)

---

<div align="center">

**🐕 Perrobotillo Trading Bot** - *"Nunca confiar, siempre verificar"*

</div>
