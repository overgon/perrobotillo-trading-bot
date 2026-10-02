# 🐛 BUG: ML Auto-Retrain falla por rutas $HOME sin expandir en Python

---

## Descripción

El auto-retrain del ML no se ejecutaba correctamente porque los scripts Python usaban rutas con `$HOME` que Python no expande automáticamente.

---

## Síntomas

```
[2026-05-17 03:00:03] ❌ No hay modelo existente
[2026-05-17 03:00:03] ⚠️  No hay trade-history.json
[2026-05-17 03:00:03] ⚠️  Solo 0 trades nuevos (mínimo: 10)
[2026-05-17 03:00:03] 💤 Saltando re-entrenamiento
```

Aunque los archivos SÍ existían en el filesystem.

---

## Causa Raíz

Python no expande variables de entorno en strings literalmente. Las rutas así:

```python
MODEL_PATH = '$HOME/.openclaw/workspace/ml/tp_prediction_model.pkl'
```

No funcionan porque `$HOME` se trata como texto literal, no como variable.

**Verificación:**

```bash
python3 -c "import os; print(os.path.exists('$HOME/.openclaw/workspace/ml/tp_prediction_model.pkl'))"
# False (ruta literal no existe)

python3 -c "import os; print(os.path.exists(os.path.expandvars('$HOME/.openclaw/workspace/ml/tp_prediction_model.pkl')))"  
# True (ruta expandida sí existe)
```

---

## Scripts Afectados

1. `ml/auto-retrain.py` - Pipeline de re-entrenamiento
2. `ml/predict-tp.py` - Predicción TP en tiempo real

---

## Solución Aplicada

### 1. auto-retrain.py

**Antes:**

```python
MODEL_PATH = '$HOME/.openclaw/workspace/ml/tp_prediction_model.pkl'
METADATA_PATH = '$HOME/.openclaw/workspace/ml/model_metadata.json'
TRADE_HISTORY_PATH = '$HOME/.openclaw/workspace/crypto-bots/trade-history.json'
BACKTEST_DATA_DIR = '$HOME/.openclaw/workspace/backtest/data'
ML_LOG_PATH = '$HOME/.openclaw/logs/ml-retrain.log'
```

**Después:**

```python
HOME = os.path.expandvars('$HOME')
MODEL_PATH = os.path.join(HOME, '.openclaw/workspace/ml/tp_prediction_model.pkl')
METADATA_PATH = os.path.join(HOME, '.openclaw/workspace/ml/model_metadata.json')
TRADE_HISTORY_PATH = os.path.join(HOME, '.openclaw/workspace/crypto-bots/trade-history.json')
BACKTEST_DATA_DIR = os.path.join(HOME, '.openclaw/workspace/backtest/data')
ML_LOG_PATH = os.path.join(HOME, '.openclaw/logs/ml-retrain.log')
```

### 2. predict-tp.py

Mismo patrón: agregar `HOME = os.path.expandvars('$HOME')` y usar `os.path.join(HOME, ...)` para todas las rutas.

### 3. Bug Adicional: Carga de trade-history.json

**Problema:** El script asumía que el JSON era una lista directa, pero tiene estructura:

```json
{
  "version": "1.0",
  "trades": [...]
}
```

**Fix:**

```python
def load_trade_history():
    with open(TRADE_HISTORY_PATH, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        trades = data.get('trades', [])
    else:
        trades = data
    
    return trades
```

### 4. Bug Adicional: Lógica de trades nuevos

**Problema:** Los trades están en orden INVERSO (más reciente en índice 0), pero el código asumía orden cronológico.

**Fix:**

```python
# Trades nuevos = total actual - último count
new_trades_count = len(trades) - last_trade_count
new_trades = trades[:new_trades_count]  # Primeros N trades son los nuevos
```

---

## Resultado

Después del fix:

```
✅ 76 trades nuevos detectados
✅ Auto-retrain ejecutado exitosamente
✅ Accuracy: 80.72%
✅ Nuevas predicciones DEFENSIVE generadas
```

---

## Prevención Futura

1. **Usar `os.path.expandvars()`** o `os.environ['HOME']` en lugar de `$HOME` literal
2. **Usar `os.path.join()`** para construir rutas
3. **Considerar pathlib.Path** para manejo más robusto de rutas
4. **Agregar tests** que verifiquen que las rutas existen antes de usarlas

---

## Metadata

- **Detectado:** 18 Mayo 2026
- **Fix aplicado:** 18 Mayo 2026
- **Scripts corregidos:** `ml/auto-retrain.py`, `ml/predict-tp.py`
- **Impacto:** Alto (ML sin re-entrenar por días)
- **Prioridad:** Alta

---

## Checklist

- [x] Bug identificado
- [x] Root cause analizado
- [x] Fix aplicado en auto-retrain.py
- [x] Fix aplicado en predict-tp.py
- [x] Re-entrenamiento manual ejecutado
- [x] Nuevas predicciones generadas
- [ ] Issue creado en GitHub
- [ ] Documentación actualizada
