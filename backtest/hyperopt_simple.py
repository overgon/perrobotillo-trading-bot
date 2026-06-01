#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - HYPEROPT SIMPLE
# ════════════════════════════════════════════════════════
# Hyperopt usando resultados de backtest existentes
# ════════════════════════════════════════════════════════

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from itertools import product
import random

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
REPORTS_DIR = WORKSPACE / "backtest" / "hyperopt"
BACKTEST_REPORTS_DIR = WORKSPACE / "backtest" / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# Parámetros base actuales
DEFAULT_PARAMS = {
    "stoploss": -0.035,
    "take_profit_1": 0.025,
    "take_profit_2": 0.050,
    "take_profit_3": 0.080
}

# Rangos de optimización
PARAM_RANGES = {
    "stoploss": [-0.05, -0.04, -0.035, -0.03, -0.025],
    "take_profit_1": [0.02, 0.025, 0.03, 0.035],
    "take_profit_2": [0.04, 0.045, 0.05, 0.055],
    "take_profit_3": [0.07, 0.08, 0.09, 0.10]
}

def load_backtest_results(coin: str) -> dict:
    """Cargar resultados de backtest existente"""
    
    # Buscar el archivo de backtest más reciente
    backtest_files = list(BACKTEST_REPORTS_DIR.glob(f"backtest_{coin}_*.json"))
    
    if not backtest_files:
        return None
    
    # Usar el más reciente
    latest_file = max(backtest_files, key=lambda f: f.stat().st_mtime)
    
    with open(latest_file, 'r') as f:
        return json.load(f)

def simulate_param_impact(base_results: dict, new_params: dict) -> dict:
    """Simular cómo cambiarían los resultados con nuevos parámetros"""
    
    # Esta es una aproximación basada en el cambio de parámetros
    # En una implementación real, volveríamos a ejecutar el backtest
    
    base_sl = abs(DEFAULT_PARAMS['stoploss'])
    base_tp1 = DEFAULT_PARAMS['take_profit_1']
    base_tp2 = DEFAULT_PARAMS['take_profit_2']
    base_tp3 = DEFAULT_PARAMS['take_profit_3']
    
    new_sl = abs(new_params['stoploss'])
    new_tp1 = new_params['take_profit_1']
    new_tp2 = new_params['take_profit_2']
    new_tp3 = new_params['take_profit_3']
    
    # Factores de ajuste
    sl_factor = new_sl / base_sl  # SL más amplio = menos losses pero más pérdida por trade
    tp1_factor = new_tp1 / base_tp1
    tp2_factor = new_tp2 / base_tp2
    tp3_factor = new_tp3 / base_tp3
    
    # Ajustar win rate (SL más amplio = más wins)
    adjusted_win_rate = base_results['win_rate'] * (1 + (sl_factor - 1) * 0.3)
    
    # Ajustar profit factor (TPs más altos = más profit por win)
    avg_tp_factor = (tp1_factor + tp2_factor + tp3_factor) / 3
    adjusted_profit_factor = base_results['profit_factor'] * avg_tp_factor if base_results['profit_factor'] != "∞" else "∞"
    
    # Ajustar P&L
    pnl_adjustment = (sl_factor * 0.5) + (avg_tp_factor * 0.5)
    adjusted_pnl = base_results['total_pnl_usdt'] * pnl_adjustment
    
    # Drawdown (SL más amplio = más drawdown potencial)
    adjusted_drawdown = base_results['max_drawdown_percent'] * sl_factor
    
    return {
        "win_rate": round(min(max(adjusted_win_rate, 0), 100), 2),
        "profit_factor": round(adjusted_profit_factor, 2) if adjusted_profit_factor != "∞" else "∞",
        "total_pnl_usdt": round(adjusted_pnl, 2),
        "max_drawdown_percent": round(min(adjusted_drawdown, 100), 2),
        "params": new_params
    }

def calculate_score(metrics: dict) -> float:
    """Calcular score para un conjunto de métricas"""
    
    win_rate_score = metrics['win_rate']
    pf = metrics['profit_factor']
    profit_factor_score = min(pf * 20, 100) if pf != "∞" else 100
    pnl_score = min(max(metrics['total_pnl_usdt'] * 0.5, -50), 50)
    drawdown_penalty = min(metrics['max_drawdown_percent'], 50)
    
    return win_rate_score + profit_factor_score + pnl_score - drawdown_penalty

def run_hyperopt(coin: str, n_iterations: int = 100):
    """Ejecutar hyperopt para una moneda"""
    
    print(f"\n{'='*60}")
    print(f"🔬 HYPEROPT - {coin}")
    print(f"{'='*60}")
    
    # Cargar backtest base
    base_results = load_backtest_results(coin)
    
    if not base_results:
        print(f"❌ No se encontraron resultados de backtest para {coin}")
        return None
    
    print(f"📊 Backtest base:")
    print(f"  Trades: {base_results['total_trades']}")
    print(f"  Win Rate: {base_results['win_rate']}%")
    print(f"  P&L: ${base_results['total_pnl_usdt']}")
    print(f"  Profit Factor: {base_results['profit_factor']}")
    
    # Generar combinaciones aleatorias
    param_keys = list(PARAM_RANGES.keys())
    param_values = [PARAM_RANGES[key] for key in param_keys]
    
    best_score = -float('inf')
    best_params = None
    best_metrics = None
    
    print(f"\n🔍 Evaluando {n_iterations} combinaciones...")
    
    for i in range(n_iterations):
        # Seleccionar parámetros aleatorios
        combo = [random.choice(values) for values in param_values]
        params = dict(zip(param_keys, combo))
        
        # Simular impacto
        metrics = simulate_param_impact(base_results, params)
        metrics['score'] = calculate_score(metrics)
        
        if metrics['score'] > best_score:
            best_score = metrics['score']
            best_params = params
            best_metrics = metrics
        
        # Progreso
        if (i + 1) % 25 == 0:
            print(f"  Progreso: {i+1}/{n_iterations}")
    
    # Imprimir mejores parámetros
    print(f"\n{'='*60}")
    print("🏆 MEJORES PARÁMETROS ENCONTRADOS")
    print(f"{'='*60}")
    print(f"  Stop Loss:     {abs(best_params['stoploss']*100):.1f}%")
    print(f"  Take Profit 1: {best_params['take_profit_1']*100:.1f}%")
    print(f"  Take Profit 2: {best_params['take_profit_2']*100:.1f}%")
    print(f"  Take Profit 3: {best_params['take_profit_3']*100:.1f}%")
    
    print(f"\n📊 MÉTRICAS PROYECTADAS:")
    print(f"  Win Rate:      {best_metrics['win_rate']}% (vs {base_results['win_rate']}% base)")
    print(f"  P&L Total:     ${best_metrics['total_pnl_usdt']} (vs ${base_results['total_pnl_usdt']} base)")
    print(f"  Profit Factor: {best_metrics['profit_factor']} (vs {base_results['profit_factor']} base)")
    print(f"  Max Drawdown:  {best_metrics['max_drawdown_percent']}% (vs {base_results['max_drawdown_percent']}% base)")
    print(f"  Score:         {best_metrics['score']}")
    print(f"{'='*60}\n")
    
    # Guardar resultados
    results = {
        "coin": coin,
        "base_params": DEFAULT_PARAMS.copy(),
        "optimized_params": best_params,
        "base_metrics": {k: v for k, v in base_results.items()},
        "optimized_metrics": {k: v for k, v in best_metrics.items() if k != 'params'},
        "improvement": {
            "win_rate_change": best_metrics['win_rate'] - base_results['win_rate'],
            "pnl_change": best_metrics['total_pnl_usdt'] - base_results['total_pnl_usdt'],
            "pf_change": (best_metrics['profit_factor'] - base_results['profit_factor']) if base_results['profit_factor'] != "∞" else "N/A"
        },
        "generated_at": datetime.now().isoformat()
    }
    
    output_file = REPORTS_DIR / f"hyperopt_{coin}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Resultados guardados en: {output_file}")
    
    return results

def run_hyperopt_all(n_iterations: int = 100):
    """Ejecutar hyperopt para todas las monedas"""
    
    print(f"\n{'='*60}")
    print("🐕 PERROBOTILLO HYPEROPT - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    all_results = {}
    
    for coin in COINS:
        try:
            results = run_hyperopt(coin, n_iterations)
            if results:
                all_results[coin] = results
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen consolidado
    print(f"\n{'='*60}")
    print("🏆 RESUMEN DE OPTIMIZACIÓN")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'SL':<6} | {'TP1':<6} | {'TP2':<6} | {'TP3':<6} | {'Win%':<8} | {'P&L $':<10} | {'Mejora':<8}")
    print("-"*80)
    
    for coin, data in all_results.items():
        params = data['optimized_params']
        metrics = data['optimized_metrics']
        improvement = data['improvement']['pnl_change']
        
        print(f"{coin:<6} | {abs(params['stoploss']*100):<6.1f}% | {params['take_profit_1']*100:<6.1f}% | {params['take_profit_2']*100:<6.1f}% | {params['take_profit_3']*100:<6.1f}% | {metrics['win_rate']:<8}% | ${metrics['total_pnl_usdt']:<9} | ${improvement:<7}")
    
    print(f"{'='*60}\n")
    
    # Guardar resumen
    summary_file = REPORTS_DIR / "hyperopt_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "coins": all_results
        }, f, indent=2)
    
    return all_results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        n_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        run_hyperopt_all(n_iter)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        n_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        run_hyperopt(coin, n_iter)
    else:
        print("Uso: python3 hyperopt_simple.py [--all|<COIN>] [iterations]")
        print("Ejemplo: python3 hyperopt_simple.py BTC 100")
        print("Ejemplo: python3 hyperopt_simple.py --all 200")
