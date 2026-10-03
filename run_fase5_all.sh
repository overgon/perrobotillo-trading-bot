#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# run_fase5_all.sh — Fase 5 ML Pipeline: Single-command runner
#
# Ejecuta todo el pipeline de ML de Fase 5 dentro del container Docker jesse.
# Rutas son RELATIVAS AL CONTAINER (/home = jesse-research mount).
#
# Usage:
#   docker exec jesse bash -c "cd /home && bash run_fase5_all.sh"
#
# Steps:
#   1. (optional) Re-download fresh 1h candles from Binance → DB
#   2. Dry-run pipeline verification (ZEC only)
#   3. Full ML training: gather → train (4 models) → validate → export
#   4. Validate overfitting_gap < 3% per coin
#   5. Summary report
#
# Refs: issue #44 (Jesse AI Research Lab)
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

cd /home  # container mount point for jesse-research

echo "════════════════════════════════════════════════════════════════════════"
echo "🚀 FASE 5: ML PIPELINE RUNNER — $(date -Iseconds)"
echo "════════════════════════════════════════════════════════════════════════"

# ─── Config ──────────────────────────────────────────────────────────────
RAW_DATA_DIR="/home/raw_data"
OUTPUT_DIR="/home/analysis_fase5"
MODELS_DIR="/home/fase5_models"
SUMMARY="/home/analysis_fase5/fase5_summary.json"
OVERFIT_THRESHOLD=0.03   # 3% — per issue #44 target

# ─── Step 1: Verify CSV candle data exists ───────────────────────────────
echo ""
echo "🔍 STEP 1: Verificando candle data (CSV)"
echo "  RAW_DATA_DIR: $RAW_DATA_DIR"
missing=0
for coin in BTC ETH BNB SOL AVAX ZEC; do
    csv="$RAW_DATA_DIR/${coin}USDT_1h.csv"
    if [ -f "$csv" ]; then
        rows=$(wc -l < "$csv")
        echo "  ✅ ${coin}USDT_1h.csv → $((rows - 1)) rows"
    else
        echo "  ❌ ${coin}USDT_1h.csv → MISSING"
        missing=1
    fi
done

if [ "$missing" -eq 1 ]; then
    echo ""
    echo "  ⚠️  Missing CSVs. Downloading from Binance API..."
    echo "  💡 Run inside container: python3 research/download_candles.py"
    echo "     (This downloads 2 years of 1h klines + expands to 1m + stores in DB)"
    echo "  Attempting download now..."
    python3 research/download_candles.py || {
        echo "  ❌ download_candles.py failed — continuing with available CSVs"
    }
else
    echo "  ✅ All 7 coin CSVs present — skipping download"
fi

# ─── Step 2: Dry-run verification (LINK only) ─────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "🧪 STEP 2: Dry-run pipeline (ZEC only)"
echo "════════════════════════════════════════════════════════════════════════"
JESSE_ML_MODE=gather python3 fase5_train.py --dry-run --coin ZEC 2>&1
DRY_EXIT=$?

if [ "$DRY_EXIT" -ne 0 ]; then
    echo ""
    echo "  ❌ Dry-run FAILED (exit $DRY_EXIT) — aborting. Fix pipeline first."
    exit 1
fi

echo ""
echo "  ✅ Dry-run passed — pipeline operational"

# Check data points from summary
if [ -f "$SUMMARY" ]; then
    link_status=$(python3 -c "
import json
try:
    s = json.load(open('$SUMMARY'))
    coin = s.get('LINK', {})
    if coin.get('status') == 'completed':
        print(f\"samples={coin.get('samples',0)} gap={coin.get('overfitting_gap',0):.2%} acc={coin.get('accuracy',0):.4f}\")
    else:
        print(f\"status={coin.get('status','unknown')} reason={coin.get('reason','')}\")
except: print('error reading summary')
")
    echo "  LINK: $link_status"
fi

# ─── Step 3: Full ML Training (all 7 coins) ──────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "🎯 STEP 3: Full ML Training — all 7 coins"
echo "  Estimators: RandomForest, XGBoost, GradientBoosting, LogisticRegression"
echo "  Validation: Walk-forward 70/30, overfitting_gap < 3% threshold"
echo "════════════════════════════════════════════════════════════════════════"
JESSE_ML_MODE=gather python3 fase5_train.py 2>&1
TRAIN_EXIT=$?

if [ "$TRAIN_EXIT" -ne 0 ]; then
    echo ""
    echo "  ❌ Full training FAILED (exit $TRAIN_EXIT)"
    exit 2
fi

# ─── Step 4: Validate results ────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📊 STEP 4: Validation — overfitting_gap < 3%"
echo "════════════════════════════════════════════════════════════════════════"

if [ -f "$SUMMARY" ]; then
    echo ""
    echo "  Resultados por moneda:"
    echo "  ┌────────┬──────────┬────────┬────────┬──────────┬─────────┐"
    echo "  │ Coin   │ Model    │ Acc    │ Gap    │ Samples  │ Status  │"
    echo "  ├────────┼──────────┼────────┼────────┼──────────┼─────────┤"
    python3 -c "
import json
s = json.load(open('$SUMMARY'))
pass_count = 0
fail_count = 0
for coin in ['ZEC','AVAX','XRP','SOL','BNB','ETH','BTC']:
    info = s.get(coin, {})
    status = info.get('status', 'unknown')
    if status == 'completed':
        model = info.get('best_model','?')
        acc = info.get('accuracy',0)
        gap = info.get('overfitting_gap',1.0)
        n = info.get('samples',0)
        feats = info.get('features',0)
        if gap < 0.03:
            flag = '✅ PASS'
            pass_count += 1
        elif gap < 0.05:
            flag = '⚠️ WARN'
            fail_count += 1
        else:
            flag = '❌ FAIL'
            fail_count += 1
        print(f'  │ {coin:6s} │ {model:8s} │ {acc:.4f} │ {gap:5.2%} │ {n:4d}/{feats:2d}   │ {flag:7s} │')
    else:
        reason = info.get('reason', info.get('error','?'))[:20]
        print(f'  │ {coin:6s} │ ---      │ --     │ --     │ ----    │ {reason:7s} │')
        fail_count += 1
print(f'  └────────┴──────────┴────────┴────────┴──────────┴─────────┘')
print(f'  PASS (<3%): {pass_count} | FAIL/WARN: {fail_count}')
"
else
    echo "  ❌ Summary file not found: $SUMMARY"
    exit 3
fi

# ─── Step 5: Check exported models ───────────────────────────────────────
echo ""
echo "📁 STEP 5: Modelos exportados"
if [ -d "$MODELS_DIR" ] && [ -n "$(ls -A "$MODELS_DIR" 2>/dev/null)" ]; then
    echo "  Modelos en $MODELS_DIR:"
    ls -1 "$MODELS_DIR" | sed 's/^/    /'
    model_count=$(ls -1 "$MODELS_DIR" | wc -l)
    echo "  Total: $model_count archivos"
else
    echo "  ⚠️  $MODELS_DIR está vacío — no models exported"
    echo "  💡 Models are exported only when overfitting_gap is acceptable."
    echo "     Check if coins had < 50 data points (skipped) or gap too high."
fi

# ─── Final summary ───────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ FASE 5 PIPELINE COMPLETE — $(date -Iseconds)"
echo "════════════════════════════════════════════════════════════════════════"
echo "  Output:  $OUTPUT_DIR"
echo "  Models:  $MODELS_DIR"
echo "  Summary: $SUMMARY"
echo ""
echo "  Next: Review $SUMMARY, then A/B test best model in Perrobotillo."
echo "  Ref:   issue #44 — Fase 5"
echo "════════════════════════════════════════════════════════════════════════"
