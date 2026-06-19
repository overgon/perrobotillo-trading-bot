# 🐕 Perrobotillo Trading Bot - CHEATSHEET-UPDATE-SUMMARY.md

Fecha: 2026-06-18
Commit asociado: d98168b
Autor: Perrobotillo 🐕

## ✨ Resumen rápido
- Notificación de Telegram **centralizada** en `crypto-bots/notify.sh`.
- Eventos de **Apertura/Cierre/Trade** estandarizados desde `crypto-trade-moneda-v3-slots.sh`.
- **Anti-spam / dedup** por clave de evento (no más notificaciones duplicadas).
- Smoke test incluido (`crypto-bots/smoke-notify.sh`).

## 🧩 Archivos nuevos o clave

| Archivo | Rol principal |
|---------|----------------|
| `crypto-bots/notify.sh` | Notificador central de Telegram, wrapper y dedup |
| `crypto-bots/smoke-notify.sh` | Smoke test del sistema de notificaciones |
| `crypto-trade-moneda-v3-slots.sh` | Orquestador de slots con emisión de eventos estandarizados |

## 📢 Eventos estandarizados

| Clave | Tipo |
|-------|------|
| `OPEN | LONG | SYMBOL | slot_id` | Apertura |
| `TP1_HIT` | Cierre parcial |
| `TP2_HIT` | Cierre parcial |
| `TP3_FAIL` | Cierre fallido |
| `SL_HIT` | Cierre por stop |
| `SCALP_TP_HIT` | Cierre por scalping |
| `TRAILING_STOP` | Cierre por trailing |
| `BINANCE_ORDER_FAIL` | Falla de orden |
| `ORDER_FAIL | QUANTITY` | Falla local |
| `ALERT_LOSSES` | Alerta pérdidas |
| `DAILY_LIMIT` | Límite diario |
| `GLOBAL_CB | ACTIVATED` | Circuit breaker global |

## ✅ Cashouts 36/40 / 40 bugs resueltos
- Estado actual: **36/40**.
- Debug pendiente: **4 casos** pendientes de cierre fino.

## 🔔 Daily report + Trade notifications
- `daily-report-9am.sh` cubre reporte diario 9:00 AM.
- Orquestador cubre notificación de apertura y cierre por trade.
- `notify.sh` centraliza envío por Telegram.

## 🚨 Proactive alerts
- `crypto-bots/proactive-alerts.sh` cubre:
  - Consecutive losses
  - Win rate bajo
  - Daily loss limit
- Enviado por `notify.sh` con dedup.

## 🛡️ Seguridad
- `.gitignore` protege `secrets/binance.env` y `secrets/telegram.env`.
- No hay exposición de credenciales en cambios staged.

## 🧪 Smoke test
- Script: `crypto-bots/smoke-notify.sh`
- Comprobado envío y dedup.

## 📦 Cambios recientes (Junio 18, 2026)
- 18 archivos afectados.
- 439 inserciones, 280 eliminaciones.

```

 Documentación y CHANGELOG mantenidos por Perrobotillo 🐕
