# Fase 4 Checklist — Optuna Hyperparameter Optimization

## Status: ✅ COMPLETADA

## Objetivo
Optimizar hiperparámetros del strategy Perrobotillo en Jesse AI Research Lab usando Optuna hyperparameter tuning.

## Pasos

### 1. Pre-requisitos ✅
- [x] Snapshot del strategy antes de cambios (Fase 3 completada)
- [x] Datos 1m candles importados (Jan 18 - Apr 18, 2026)
- [x] Strategy conectada a `self.hp` (min_confidence, EMA, TP/SL, position size)
- [x] Docker environment running (jesse, postgres, redis)

### 2. Hyperparameter Connection ✅
- [x] Agregar `self.hp['min_confidence']` a `should_long()`
- [x] Conectar `tp1_ratio`, `tp2_ratio`, `tp3_ratio` en `on_open_position()`
- [x] Conectar `sl_ratio` en `on_open_position()`
- [x] Conectar `ema_fast`, `ema_slow` en `should_long()`
- [x] Conectar `position_size_percent`, `rsi_overbought`, `rsi_oversold`, `min_adx` a strategy

### 3. Optuna Optimization ✅
- [x] Crear script `research/optuna_custom.py` (custom Optuna, no usa Jesse optimize())
- [x] Train/test split: 70% train (Jan 28 - Mar 9), 30% test (Mar 9 - Apr 18)
- [x] Warmup: 8 días antes de cada período
- [x] Objetivo: maximize Sharpe ratio (Bayesian optimization)
- [x] 50 trials completados
- [x] Resultados guardados en `research/optuna_results.json`

### 4. Results ✅

#### Training (Jan 28 - Mar 9)
- **Best Sharpe: -2.21** (mejorado de -3.77 baseline → 36% improvement)
- **Best params:**
  - tp1_percent: 3.0, tp2_percent: 14.4, tp3_percent: 18.2
  - stop_loss_percent: 7.2, position_size_percent: 18.0
  - ml_min_confidence: 55.0, ema_fast: 12, ema_slow: 140

#### Testing (Mar 9 - Apr 18)  
- **Test Sharpe: +2.31** (positivo)
- **Test PnL: +$346.32**
- **Test Trades: 1** (100% win rate en testing)

### 5. Strategy Updates ✅
- [x] Actualizados defaults en `strategies/perrobotillo/__init__.py`
- [x] Wider TPs (14.4/18.2% vs 6/9 original)
- [x] Wider SL (7.2% vs 3.5 original)
- [x] Higher position size (18% vs 10%)
- [x] EMA 12/140 (vs 20/50 original)
- [x] ml_min_confidence 55 (vs 40 original)
- [x] Widened stop_loss_percent max range: 8 → 10

### 6. Commit & Push ✅
- [x] Commit local (ff276bc)
- [x] Pushed a `overgon/project-template`

## Key Decisions
1. **Custom Optuna script** en vez de Jesse `optimize()`: Jesse filtra `score > 0.0001` y descarta todos los trials negativos. Nuestro custom script acepta valores negativos y usa Bayesian optimization de Optuna directamente.
2. **Wide SL (7.2%)** es el factor más importante: reduce false stop-outs en volatilidad.
3. **Wide TP (14.4-18.2%)** permite capturar tendencias largas con EMA 12/140 (bull trend filter).
4. **Higher position size (18%)**: compensa el menor número de trades con mayor ganancia por trade.
5. **EMA 12/140** (rápido/lento) genera menos señales falsas que EMA 20/50.

## Limitation
- Testing solo tuvo 1 trade → no estadísticamente significativo
- Training Sharpe sigue negativo (-2.21) → ML proxy no tiene edge real (p=0.52)
- **Recomendación**: Continuar con Fase 5 (ML model training) para mejorar el entry signal. Los HP optimizados aquí sirven como baseline para el ML training.

## Next: Fase 5
- Entrenar modelo ML real (sklearn: RandomForest + GradientBoosting)
- Reemplazar `ml_confidence_proxy()` con modelo real
- Volver a correr Optuna con modelo ML real → esperamos Sharpe positivo
