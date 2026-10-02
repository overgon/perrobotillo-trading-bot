# 🧠 ML Validator - Machine Learning Trade Validator

## 📋 Descripción

Sistema de validación pre-trade que usa reglas técnicas y machine learning para aprobar/rechazar trades.

## 🎯 Features

- ✅ Validación pre-trade obligatoria
- ✅ Score de confianza 0-100%
- ✅ Ajuste automático de position size
- ✅ Market regime detection (BULL/BEAR/LATERAL)
- ✅ Auto-retraining semanal (domingos 3 AM)

## 🔧 Instalación

### Dependencias:

```bash
# Crear virtualenv (opcional pero recomendado)
cd /home/overgon/.openclaw/workspace
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install scikit-learn joblib TA-Lib numpy requests
```

### TA-Lib Installation:

TA-Lib requiere instalación del sistema primero:

```bash
# Ubuntu/Debian
sudo apt-get install libta-lib-dev

# O desde source
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
```

## 🚀 Uso

### Validar Trade Manualmente:

```bash
python3 ml-validator.py BTC NORMAL LONG
python3 ml-validator.py ETH SCALP SHORT
```

### Output Ejemplo:

```
🧠 ML Validator - BTC NORMAL LONG
==================================================
Aprobado: ✅ SÍ
Confianza: 75%
Dirección: LONG
Tamaño posición: 40%
Nivel riesgo: LOW
Market regime: BULL
Razones: RSI bajo (35.2); MACD bullish; Trend bullish
==================================================
```

## 📊 Configuración

Editar `ml-validator-config.json`:

```json
{
  "enabled": true,              // Activar/desactivar validator
  "min_confidence": 50,         // Mínimo % para aprobar
  "reduce_position_below": 70,  // Reducir posición si < 70%
  "position_reduction_percent": 50  // Reducir a 50%
}
```

## 🔄 Auto-Retraining

El modelo se re-entrena automáticamente cada domingo a las 3 AM.

### Trigger Manual:

```bash
python3 ml-retrain.py
```

### Logs:

- Entrenamiento: `ml-retrain.log`
- Validaciones: `ml-validator-log.json`

## 📈 Modelo Actual

Random Forest Classifier:
- 100 estimators
- Max depth: 10
- Features: RSI, MACD, Volume, Trend, Bollinger, Volatility

## 🧪 Testing

```bash
# Test con todas las monedas
for coin in BTC ETH BNB SOL LINK XRP AVAX; do
    echo "=== $coin ==="
    python3 ml-validator.py $coin NORMAL LONG
done
```

## 📝 Archivos

| Archivo | Propósito |
|---------|-----------|
| `ml-validator.py` | Validator principal |
| `ml-retrain.py` | Auto-retraining |
| `ml-retrain-cron.sh` | Cron job semanal |
| `ml-validator-config.json` | Configuración |
| `ml-validator-model.pkl` | Modelo entrenado |
| `ml-validator-model.json` | Info del modelo |
| `ml-validator-log.json` | Log de validaciones |

## 🎯 Sistema de Scoring

| Indicador | Puntos Máx | Descripción |
|-----------|------------|-------------|
| RSI | 25 | Overbought/Oversold detection |
| MACD | 25 | Momentum detection |
| Trend | 20 | SMA crossover |
| Volume | 15 | Volume ratio vs average |
| Bollinger | 15 | Price position in bands |

**Total:** 100 puntos = 100% confianza

## ⚠️ Thresholds por Trade Type

| Type | Min Confianza | Max Risk |
|------|---------------|----------|
| SCALP | 60% | HIGH |
| NORMAL | 65% | MEDIUM |
| SWING | 75% | LOW |

---

**Author:** Perrobotillo 🐕  
**Version:** 1.0.0  
**Last Update:** 2026-05-30
