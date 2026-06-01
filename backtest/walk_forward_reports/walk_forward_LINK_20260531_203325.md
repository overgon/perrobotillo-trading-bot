# 🚶 Walk-Forward Backtest Report - LINK

_Generado: 2026-05-31 20:33:25_

---

## 📊 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Moneda** | LINK |
| **N° Splits** | 5 |
| **Splits Completados** | 5 |
| **Consistencia General** | 33.2% |
| **Overfitting Detectado** | ⚠️ SÍ |

---

## 🎯 Métricas por Split

| Split | Accuracy | Precision | Recall | F1 Score |
|-------|----------|-----------|--------|----------|
| 1 | 96.61% | 93.34% | 96.61% | 94.94% |
| 2 | 89.83% | 80.70% | 89.83% | 85.02% |
| 3 | 71.19% | 50.68% | 71.19% | 59.20% |
| 4 | 75.42% | 64.33% | 75.42% | 66.71% |
| 5 | 93.22% | 86.90% | 93.22% | 89.95% |

---

## 📈 Estadísticas Agregadas

### Accuracy
- **Media:** 85.25%
- **Desviación Std:** 11.27%
- **Consistencia:** 43.7%

### F1 Score
- **Media:** 79.17%
- **Desviación Std:** 15.44%
- **Consistencia:** 22.8%

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
