# 🐛 BUGFIX: LOT_SIZE Filter Failure en Ventas TP

## 📅 Fecha: 2026-05-30

### 🚨 Problema:

El bot intentaba vender cantidades con demasiados decimales, causando error de Binance:
```
{"code":-1013,"msg":"Filter failure: LOT_SIZE"}
```

### 📊 Caso Específico:

- **Coin:** LINK
- **Slot:** 3
- **TP2 Hit:** $9.258 (precio actual $9.262)
- **Cantidad calculada:** 1.92400000 LINK ❌
- **Cantidad válida:** 1.92 LINK ✅

### 🔍 Root Cause:

Binance requiere que las cantidades sigan el `stepSize` definido en `exchangeInfo`:

```json
{
  "filterType": "LOT_SIZE",
  "minQty": "0.01000000",
  "maxQty": "90000.00000000",
  "stepSize": "0.01000000"  // ← Solo 2 decimales válidos
}
```

**1.924** tiene 3 decimales → **INVÁLIDO**  
**1.92** tiene 2 decimales → **VÁLIDO**

### ✅ Solución Temporal Aplicada:

Se realizó la venta manualmente con cantidad formateada correctamente:
```bash
quantity="1.92"  # Formateado a 2 decimales
```

### 🔧 Fix Permanente Requerido:

La función `format_quantity()` en `crypto-trade-moneda-v3-slots.sh` YA existe y debería manejar esto, pero posiblemente no se está aplicando correctamente en el flujo de ventas TP.

**Verificar:**
1. Que `format_quantity()` se llame ANTES de enviar la orden
2. Que el resultado se use en `place_sell_order_market()`
3. Agregar logging para depurar cantidades

### 📝 Lecciones Aprendidas:

1. Siempre verificar `exchangeInfo` antes de enviar órdenes
2. Cada par tiene diferentes requisitos de LOT_SIZE
3. El bot ya tiene `format_quantity()` pero puede no estar aplicándose en todos los casos

### 🎯 Acciones Futuras:

- [ ] Revisar que TODAS las ventas usen `format_quantity()`
- [ ] Agregar validación pre-envío de órdenes
- [ ] Loggear cantidad raw vs formateada para debugging
- [ ] Considerar agregar test automático para cada coin

---

## 💡 Referencia Rápida - Step Sizes Oficiales:

| Coin | Step Size | Decimales | Ejemplo Válido |
|------|-----------|-----------|----------------|
| BTC | 0.00001 | 5 | 0.00123 |
| ETH | 0.0001 | 4 | 0.1234 |
| BNB | 0.001 | 3 | 0.123 |
| SOL | 0.01 | 2 | 2.35 |
| LINK | 0.01 | 2 | 1.92 |
| XRP | 0.1 | 1 | 12.3 |
| AVAX | 0.01 | 2 | 3.45 |

**Nota:** El bot solo opera con estas 7 monedas. Verificar siempre con `curl "https://api.binance.com/api/v3/exchangeInfo?symbol=XXXUSDT"`
