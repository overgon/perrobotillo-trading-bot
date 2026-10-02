# 🚶 Walk-Forward Backtest Report - AVAX

_Generado: 2026-05-31 20:33:27_

---

## 📊 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Moneda** | AVAX |
| **N° Splits** | 5 |
| **Splits Completados** | 5 |
| **Consistencia General** | 30.7% |
| **Overfitting Detectado** | ⚠️ SÍ |

---

## 🎯 Métricas por Split

| Split | Accuracy | Precision | Recall | F1 Score |
|-------|----------|-----------|--------|----------|
| 1 | 94.07% | 88.49% | 94.07% | 91.19% |
| 2 | 78.81% | 62.12% | 78.81% | 69.48% |
| 3 | 67.80% | 45.96% | 67.80% | 54.79% |
| 4 | 75.42% | 58.02% | 75.42% | 65.59% |
| 5 | 92.37% | 92.48% | 92.37% | 92.17% |

---

## 📈 Estadísticas Agregadas

### Accuracy
- **Media:** 81.69%
- **Desviación Std:** 11.27%
- **Consistencia:** 43.7%

### F1 Score
- **Media:** 74.64%
- **Desviación Std:** 16.46%
- **Consistencia:** 17.7%

---

## 🔍 Interpretación

⚠️ POSIBLE OVERFITTING - El modelo varía mucho entre ventanas

### Criterios de Evaluación:

| Consistencia | Interpretación | Acción Recomendada |
|--------------|----------------|---------------------|
| >80% | ✅ Muy consistente | Modelo listo para producción |
| 60-80% | ✅ Consistente | Aceptable, monitorear |
| 40-60% | ⚠️ Poco consistente | Revisar features/parámetros |
| <40% | ❌ Inconsistente | Re-entrenar o cambiar modelo |

---

## 💡 Recomendaciones

**⚠️ POSIBLE OVERFITTING** - Las métricas varían significativamente entre ventanas. Se recomienda:

- Reducir complejidad del modelo (menos features, menor max_depth)
- Aumentar datos de entrenamiento
- Considerar regularización más fuerte
- Validar con Monte Carlo analysis

---

## 📝 Notas Técnicas

- **Walk-forward splits:** 5 ventanas consecutivas
- **Train size:** ~118 samples por split
- **Test size:** ~118 samples por split
- **Modelo:** Random Forest (100 estimators, max_depth=10)
- **Clases balanceadas:** Sí (class_weight='balanced')

---

_Generado por Perrobotillo Walk-Forward Backtest Engine 🐕_  
*"¡Nunca confiar, siempre verificar!"*_
