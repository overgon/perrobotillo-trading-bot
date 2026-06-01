#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - HYPEROPT ENGINE
# ════════════════════════════════════════════════════════
# Optimización automática de parámetros SL/TP
# Inspirado en Freqtrade Hyperopt pero simplificado
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
from itertools import product
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
LOGS_DIR = Path("/home/overgon/.openclaw/logs")
REPORTS_DIR = WORKSPACE / "backtest" / "hyperopt"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# Rangos de parámetros a optimizar
PARAM_RANGES = {
    "stoploss": [-0.05, -0.04, -0.035, -0.03, -0.025, -0.02],  # 2% a 5% SL
    "take_profit_1": [0.015, 0.02, 0.025, 0.03],  # 1.5% a 3% TP1
    "take_profit_2": [0.03, 0.04, 0.05, 0.06],  # 3% a 6% TP2
    "take_profit_3": [0.06, 0.07, 0.08, 0.10],  # 6% a 10% TP3
    "trailing_stop": [True, False]
}

# ════════════════════════════════════════════════════════
# BACKTEST SIMPLIFICADO PARA HYPEROPT
# ════════════════════════════════════════════════════════

def load_trade_signals(coin: str, days: int = 30) -> pd.DataFrame:
    """Cargar señales de trading desde logs históricos"""
    
    log_file = LOGS_DIR / f"trade-{coin}.log"
    
    if not log_file.exists():
        return pd.DataFrame()
    
    signals = []
    
    with open(log_file, 'r') as f:
        current_entry = None
        
        for line in f:
            # Detectar entrada de trade (simplificado - usamos cualquier línea de entrada)
            if "Slot" in line and "LONG" in line or "Slot" in line and "SHORT" in line:
                try:
                    date_str = line.split(']')[0].replace('[', '')
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Extraer precio de entrada (aproximado)
                    if "Entry:" in line:
                        entry_price = float(line.split("Entry:")[1].split()[0].replace('$', ''))
                    else:
                        continue
                    
                    current_entry = {
                        "date": date,
                        "coin": coin,
                        "entry_price": entry_price,
                        "exit_price": None,
                        "exit_type": None
                    }
                
                except:
                    continue
            
            # Detectar salida de trade
            elif current_entry and ("TP1 HIT" in line or "TP2 HIT" in line or "TP3 HIT" in line or "SL HIT" in line or "Trailing stop" in line):
                try:
                    date_str = line.split(']')[0].replace('[', '')
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Determinar tipo de salida y precio
                    if "TP1" in line:
                        exit_type = "TP1"
                    elif "TP2" in line:
                        exit_type = "TP2"
                    elif "TP3" in line:
                        exit_type = "TP3"
                    elif "SL HIT" in line or "Trailing stop" in line:
                        exit_type = "SL"
                    else:
                        continue
                    
                    # Extraer precio de salida si está disponible
                    if "$" in line:
                        try:
                            exit_price = float(line.split("$")[1].split()[0])
                        except:
                            exit_price = current_entry['entry_price']  # Fallback
                    else:
                        exit_price = current_entry['entry_price']
                    
                    signals.append({
                        "date": date,
                        "coin": coin,
                        "entry_price": current_entry['entry_price'],
                        "exit_price": exit_price,
                        "exit_type": exit_type
                    })
                    
                    current_entry = None
                
                except:
                    continue
    
    df = pd.DataFrame(signals)
    
    if len(df) == 0:
        return df
    
    # Calcular P&L real desde logs
    df['pnl_pct'] = (df['exit_price'] - df['entry_price']) / df['entry_price']
    
    # Filtrar por días
    cutoff_date = datetime.now() - pd.Timedelta(days=days)
    df = df[df['date'] >= cutoff_date]
    
    return df

def simulate_trades_with_params(df: pd.DataFrame, params: dict) -> dict:
    """Simular trades con parámetros específicos y calcular métricas"""
    
    if len(df) == 0:
        return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}
    
    trades = []
    
    for _, row in df.iterrows():
        actual_pnl = row['pnl_pct']
        entry_price = row['entry_price']
        
        # Determinar qué habría pasado con estos parámetros
        if actual_pnl >= params['take_profit_3']:
            exit_type = "TP3"
            pnl = params['take_profit_3']
        elif actual_pnl >= params['take_profit_2']:
            exit_type = "TP2"
            pnl = params['take_profit_2']
        elif actual_pnl >= params['take_profit_1']:
            exit_type = "TP1"
            pnl = params['take_profit_1']
        elif actual_pnl <= params['stoploss']:
            exit_type = "SL"
            pnl = params['stoploss']
        else:
            # Trade aún abierto o cerrado manualmente - usar P&L real
            exit_type = "CLOSED"
            pnl = actual_pnl
        
        trades.append({
            "exit_type": exit_type,
            "pnl": pnl
        })
    
    # Calcular métricas
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    losing_trades = sum(1 for t in trades if t['pnl'] <= 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # P&L total (asumiendo $50 por trade)
    stake_per_trade = 50
    total_pnl = sum(t['pnl'] * stake_per_trade for t in trades)
    total_pnl_pct = (total_pnl / (stake_per_trade * total_trades)) * 100 if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = sum(t['pnl'] * stake_per_trade for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] * stake_per_trade for t in trades if t['pnl'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Drawdown máximo (simplificado)
    cumulative = np.cumsum([t['pnl'] * stake_per_trade for t in trades])
    if len(cumulative) > 0:
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak * 100
        max_drawdown = float(np.max(drawdown))
    else:
        max_drawdown = 0
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl_usdt": round(total_pnl, 2),
        "total_pnl_percent": round(total_pnl_pct, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
        "max_drawdown": round(max_drawdown, 2),
        "trades": trades
    }

def evaluate_params(df: pd.DataFrame, params: dict) -> dict:
    """Evaluar un conjunto de parámetros y retornar score"""
    
    results = simulate_trades_with_params(df, params)
    
    # Score function: combinamos win rate, profit factor y total PnL
    # Queremos maximizar: Win Rate + Profit Factor + (PnL normalizado)
    
    win_rate_score = results['win_rate']
    profit_factor_score = min(results['profit_factor'] * 20, 100) if results['profit_factor'] != "∞" else 100
    pnl_score = min(max(results['total_pnl_percent'] * 2, -50), 50)  # Clamp entre -50 y 50
    
    # Penalizar drawdown alto
    drawdown_penalty = min(results['max_drawdown'], 50)
    
    total_score = win_rate_score + profit_factor_score + pnl_score - drawdown_penalty
    
    results['score'] = round(total_score, 2)
    results['params'] = params.copy()
    
    return results

# ════════════════════════════════════════════════════════
# HYPEROPT ENGINE
# ════════════════════════════════════════════════════════

class HyperoptEngine:
    def __init__(self, coin: str, days: int = 30):
        self.coin = coin
        self.days = days
        self.df = load_trade_signals(coin, days)
        self.best_results = None
        self.all_results = []
    
    def run_grid_search(self, n_combinations: int = None) -> dict:
        """Ejecutar Grid Search sobre todos los parámetros"""
        
        print(f"\n{'='*60}")
        print(f"🔬 HYPEROPT - {self.coin}")
        print(f"{'='*60}")
        
        if len(self.df) == 0:
            print(f"❌ No hay datos de trades para {self.coin}")
            return None
        
        print(f"📊 Trades históricos encontrados: {len(self.df)}")
        
        # Generar todas las combinaciones posibles
        param_keys = list(PARAM_RANGES.keys())
        param_values = [PARAM_RANGES[key] for key in param_keys]
        
        all_combinations = list(product(*param_values))
        
        if n_combinations:
            # Sample aleatorio si hay demasiadas combinaciones
            import random
            all_combinations = random.sample(all_combinations, min(n_combinations, len(all_combinations)))
        
        print(f"🔍 Evaluando {len(all_combinations)} combinaciones de parámetros...")
        
        # Evaluar cada combinación
        best_score = -float('inf')
        
        for i, combo in enumerate(all_combinations):
            params = dict(zip(param_keys, combo))
            results = evaluate_params(self.df, params)
            
            self.all_results.append(results)
            
            if results['score'] > best_score:
                best_score = results['score']
                self.best_results = results
            
            # Progreso
            if (i + 1) % 50 == 0:
                print(f"  Progreso: {i+1}/{len(all_combinations)} ({(i+1)/len(all_combinations)*100:.1f}%)")
        
        print(f"\n✅ Hyperopt completado")
        
        return self.best_results
    
    def get_top_results(self, n: int = 10) -> list:
        """Obtener top N resultados"""
        sorted_results = sorted(self.all_results, key=lambda x: x['score'], reverse=True)
        return sorted_results[:n]
    
    def save_results(self, output_file: str = None):
        """Guardar resultados"""
        
        if not output_file:
            output_file = REPORTS_DIR / f"hyperopt_{self.coin}_{self.days}d.json"
        
        results_to_save = {
            "coin": self.coin,
            "days": self.days,
            "evaluated_combinations": len(self.all_results),
            "best_params": self.best_results['params'] if self.best_results else None,
            "best_metrics": {k: v for k, v in self.best_results.items() if k not in ['params', 'trades']} if self.best_results else None,
            "top_10_results": [
                {k: v for k, v in r.items() if k != 'trades'} 
                for r in self.get_top_results(10)
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_to_save, f, indent=2)
        
        print(f"💾 Resultados guardados en: {output_file}")
    
    def print_best_params(self):
        """Imprimir mejores parámetros"""
        
        if not self.best_results:
            print("❌ No hay resultados para mostrar")
            return
        
        print(f"\n{'='*60}")
        print("🏆 MEJORES PARÁMETROS ENCONTRADOS")
        print(f"{'='*60}")
        
        params = self.best_results['params']
        print(f"  Stop Loss:     {abs(params['stoploss']*100):.1f}%")
        print(f"  Take Profit 1: {params['take_profit_1']*100:.1f}%")
        print(f"  Take Profit 2: {params['take_profit_2']*100:.1f}%")
        print(f"  Take Profit 3: {params['take_profit_3']*100:.1f}%")
        print(f"  Trailing Stop: {params['trailing_stop']}")
        
        print(f"\n📊 MÉTRICAS CON ESTOS PARÁMETROS:")
        metrics = self.best_results
        print(f"  Total Trades:  {metrics['total_trades']}")
        print(f"  Win Rate:      {metrics['win_rate']}%")
        print(f"  P&L Total:     ${metrics['total_pnl_usdt']} USDT ({metrics['total_pnl_percent']}%)")
        print(f"  Profit Factor: {metrics['profit_factor']}")
        print(f"  Max Drawdown:  {metrics['max_drawdown']}%")
        print(f"  Score:         {metrics['score']}")
        print(f"{'='*60}\n")


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def run_hyperopt_for_coin(coin: str, days: int = 30, sample_size: int = 100):
    """Ejecutar hyperopt para una moneda específica"""
    
    engine = HyperoptEngine(coin, days)
    best = engine.run_grid_search(n_combinations=sample_size)
    
    if best:
        engine.print_best_params()
        engine.save_results()
    
    return engine

def run_hyperopt_all_coins(days: int = 30, sample_size: int = 100):
    """Ejecutar hyperopt para todas las monedas"""
    
    print(f"\n{'='*60}")
    print("🐕 PERROBOTILLO HYPEROPT - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    all_best_params = {}
    
    for coin in COINS:
        try:
            engine = run_hyperopt_for_coin(coin, days, sample_size)
            if engine.best_results:
                all_best_params[coin] = {
                    "params": engine.best_results['params'],
                    "metrics": {k: v for k, v in engine.best_results.items() if k not in ['params', 'trades']}
                }
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen consolidado
    print(f"\n{'='*60}")
    print("🏆 RESUMEN DE OPTIMIZACIÓN")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'SL':<6} | {'TP1':<6} | {'TP2':<6} | {'TP3':<6} | {'Win%':<8} | {'P&L $':<10}")
    print("-"*70)
    
    for coin, data in all_best_params.items():
        params = data['params']
        metrics = data['metrics']
        print(f"{coin:<6} | {abs(params['stoploss']*100):<6.1f}% | {params['take_profit_1']*100:<6.1f}% | {params['take_profit_2']*100:<6.1f}% | {params['take_profit_3']*100:<6.1f}% | {metrics['win_rate']:<8}% | ${metrics['total_pnl_usdt']:<9}")
    
    print(f"{'='*60}\n")
    
    # Guardar resumen
    summary_file = REPORTS_DIR / f"hyperopt_summary_{days}d.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "days": days,
            "coins": all_best_params
        }, f, indent=2)
    
    return all_best_params

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        sample = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        run_hyperopt_all_coins(days, sample)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        sample = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        run_hyperopt_for_coin(coin, days, sample)
    else:
        print("Uso: python3 hyperopt_engine.py [--all|<COIN>] [days] [sample_size]")
        print("Ejemplo: python3 hyperopt_engine.py BTC 30 100")
        print("Ejemplo: python3 hyperopt_engine.py --all 60 200")
