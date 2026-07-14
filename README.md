# 🐕 Perrobotillo Trading Bot

**Bot de trading automatizado para Binance con Machine Learning**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Binance](https://img.shields.io/badge/Binance-API-yellow.svg)](https://binance.com)
[![License](https://img.shields.io/badge/License-Private-red.svg)]()
[![Phase](https://img.shields.io/badge/Fase-SLOT_V3%20Operativa-brightgreen.svg)]()

---

## 📋 Descripción

Perrobotillo es un bot de trading de criptomonedas enfocado en **estabilidad y operación real**, no en exámenes académicos. Hoy opera con **3 monedas activas** (BNB, AVAX, SOL), **9 slots**, y un flujo probado de ejecución, notificación y monitoreo.

Componentes actuales:
- ✅ **Bot principal multi-slot**: `crypto-trade-moneda-v3-slots.sh`
- ✅ **ML Validator + Auto-retrain semanal**: domingos 3 AM
- ✅ **Monitor TP/SL**: `tp-monitor.sh` y `check-tp.py`
- ✅ **Dashboard local**: puerto 8080
- ✅ **Recaudación/reconciliación**: `reconcile-binance-state.py`

Inspirado en herramientas open-source, pero adaptado a la operativa real con **reglas estrictas**, logging y trazabilidad.

---

## 🎯 Estado actual del sistema

### Bots activos
- **Coins:** BNB, AVAX, SOL
- **Slots por coin:** 3
- **Modo:** LATERAL (ajustado por `market-mode.conf`)
- **TP/SL:** Valores por defecto + overrides por moneda

### ML / validación
- **Modelos:** Random Forest optimizado, guardados en `ml/models_optimized/`
- **Último retrain:** 2026-07-14, **7/7 monedas OK**
- **Cron retrain:** domingos 03:00
- **Criterio extra:** reentrena si hay ≥10 trades nuevos desde el último entrenamiento

### Datos clave
- **Spot operativo:** ~210.09 USDT
- **Portfolio total:** ~2,481.71 USDT
- **IP pública:** 187.188.230.63 autorizada

---

## 🚀 Instalación

### Prerequisites
```bash
python3 --version
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuración
```bash
cp secrets/binance.env.example secrets/binance.env
# Editar con tus API keys
```

### Ejecutar bot principal
```bash
./crypto-trade-moneda-v3-slots.sh AVAX
./crypto-trade-moneda-v3-slots.sh BNB
./crypto-trade-moneda-v3-slots.sh SOL
```

### Dashboard
```bash
# Acceso local con autenticación
curl http://127.0.0.1:8080/api/portfolio
```

---

## 📁 Estructura del proyecto

```
/workspace
├── crypto-trade-moneda-v3-slots.sh   # Bot principal
├── crypto-bots/
│   ├── market-mode.conf              # Modo de mercado + overrides por moneda
│   └── *.trade-state.json            # Estado local de slots
├── ml/
│   ├── ml_pipeline.py                # Pipeline base
│   ├── ml_pipeline_optimized.py      # Pipeline anti-overfitting
│   ├── ml_validator_wrapper.py       # Validator integrado
│   ├── auto-retrain-v2.py            # Auto-retrain semanal
│   └── models_optimized/             # Modelos entrenados
├── dashboard/
│   ├── app.py                        # API /api/portfolio y /api/status
│   └── static/js/app.js              # Frontend
├── scripts/
│   ├── reconcile-binance-state.py    # Reconciliación Binance ↔ state
│   ├── tp-monitor.sh                 # Monitor TP/SL
│   └── check-tp.py                   # Respaldo monitor TP/SL
├── .archive/                         # Historial/documentación obsoleta
└── logs/                             # Logs del sistema
```

---

## ⏰ Automatización actual

- **Bots:** systemd por moneda + watchdog
- **Reconciliación:** cada 15 min
- **ML retrain:** domingos 03:00
- **Reporte diario:** 09:00
- **Housekeeping:** mensual

Si querés dato operativo, el punto más útil ahora mismo es **`crypto-trade-moneda-v3-slots.sh`**, **`ml/auto-retrain-v2.py`** y **`scripts/reconcile-binance-state.py`**.
