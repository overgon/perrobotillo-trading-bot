#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║  🎯 OPTIMIZADOR FASE 1 v2 - TARGET $0.8-2/TRADE      ║
║  Perrobotillo Trading Bot                             ║
╚═══════════════════════════════════════════════════════╝
"""

import json
import csv
from datetime import datetime
import sys
sys.path.insert(0, '/home/overgon/.openclaw/workspace/backtest')

from backtest_engine import BacktestEngine, COINS

# ============================================
# CONFIGURACIÓN OBJETIVO
# ============================================

TARGET_PROFIT_PER_TRADE = 1.5  # $1.5 USDT promedio (rango: $0.8-2)
TRADES_PER_MONTH_EST = 20  # Estimado con 21 slots
TARGET_MONTHLY_PROFIT = TARGET_PROFIT_PER_TRADE * TRADES_PER_MONTH_EST  # $30/mes

# ============================================
# ESCENARIOS A TESTEAR
# ============================================

escenarios = [
    {
        'name': 'CONSERVADOR (Target $0.8-1/trade)',
        'params': {
            'TP1': 2.0,
            'TP2': 4.0,
            'TP3': 6.0,
            'SL_BTC': 2.5,
            'SL_ETH': 3.0,
            'SL_BNB': 2.5,
            'SL_SOL': 5.0,
            'SL_LINK': 4.0,
            'SL_XRP': 3.0,
            'SL_AVAX': 4.0,
            'TRAILING_AFTER_TP1': 0.5,
            'TRAILING_AFTER_TP2': 2.5,
        }
    },
    {
        'name': 'BALANCEADO (Target $1-1.5/trade)',
        'params': {
            'TP1': 2.5,
            'TP2': 5.0,
            'TP3': 8.0,
            'SL_BTC': 2.5,
            'SL_ETH': 3.0,
            'SL_BNB': 2.5,
            'SL_SOL': 5.0,
            'SL_LINK': 4.0,
            'SL_XRP': 3.0,
            'SL_AVAX': 4.0,
            'TRAILING_AFTER_TP1': 0.5,
            'TRAILING_AFTER_TP2': 3.0,
        }
    },
    {
        'name': 'AGRESIVO (Target $1.5-2/trade)',
        'params': {
            'TP1': 3.0,
            'TP2': 6.0,
            'TP3': 10.0,
            'SL_BTC': 2.0,
            'SL_ETH': 2.5,
            'SL_BNB': 2.0,
            'SL_SOL': 4.5,
            'SL_LINK': 3.5,
            'SL_XRP': 2.5,
            'SL_AVAX': 3.5,
            'TRAILING_AFTER_TP1': 0.5,
            'TRAILING_AFTER_TP2': 3.5,
        }
    },
    {
        'name': 'BNB+AVAX ONLY (100% win rate coins)',
        'params': {
            'TP1': 2.5,
            'TP2': 5.0,
            'TP3': 8.0,
            'SL_BTC': 2.5,
            'SL_ETH': 3.0,
            'SL_BNB': 2.5,
            'SL_SOL': 5.0,
            'SL_LINK': 4.0,
            'SL_XRP': 3.0,
            'SL_AVAX': 4.0,
            'TRAILING_AFTER_TP1': 0.5,
            'TRAILING_AFTER_TP2': 3.0,
        },
        'coins_only': ['BNB', 'AVAX']
    }
]

# ============================================
# FUNCIONES
# ============================================

def load_data():
    """Cargar datos históricos"""
    DATA_DIR = '/home/overgon/.openclaw/workspace/backtest/data'
    all_data = []
    
    coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'LINKUSDT', 'XRPUSDT', 'AVAXUSDT']
    
    for coin in coins:
        filepath = f"{DATA_DIR}/{coin}_1h_90days.csv"
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_data.append({
                    'timestamp': row['timestamp'],
                    'coin': coin.replace('USDT', ''),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
    
    return all_data

def run_scenario(data, scenario):
    """Ejecutar backtest con escenario específico"""
    import backtest_engine as be
    
    # Guardar valores originales
    orig_params = {
        'TP1': be.TP1_PERCENT,
        'TP2': be.TP2_PERCENT,
        'TP3': be.TP3_PERCENT,
        'TRAILING_AFTER_TP1': be.TRAILING_AFTER_TP1,
        'TRAILING_AFTER_TP2': be.TRAILING_AFTER_TP2,
    }
    
    orig_coins = {}
    for coin, config in be.COINS.items():
        orig_coins[coin] = config.stop_loss
    
    # Aplicar nuevos parámetros
    be.TP1_PERCENT = scenario['params']['TP1']
    be.TP2_PERCENT = scenario['params']['TP2']
    be.TP3_PERCENT = scenario['params']['TP3']
    be.TRAILING_AFTER_TP1 = scenario['params']['TRAILING_AFTER_TP1']
    be.TRAILING_AFTER_TP2 = scenario['params']['TRAILING_AFTER_TP2']
    
    # Aplicar SLs por coin
    for coin in be.COINS.keys():
        sl_key = f'SL_{coin}'
        if sl_key in scenario['params']:
            be.COINS[coin].stop_loss = scenario['params'][sl_key]
    
    # Filtrar coins si es necesario
    if 'coins_only' in scenario:
        original_slots = {}
        for coin in list(be.COINS.keys()):
            if coin not in scenario['coins_only']:
                del be.COINS[coin]
    
    # Ejecutar backtest
    engine = BacktestEngine(initial_capital=2000.0)
    report = engine.run(data)
    
    # Restaurar valores originales
    be.TP1_PERCENT = orig_params['TP1']
    be.TP2_PERCENT = orig_params['TP2']
    be.TP3_PERCENT = orig_params['TP3']
    be.TRAILING_AFTER_TP1 = orig_params['TRAILING_AFTER_TP1']
    be.TRAILING_AFTER_TP2 = orig_params['TRAILING_AFTER_TP2']
    
    for coin, sl in orig_coins.items():
        be.COINS[coin].stop_loss = sl
    
    # Restaurar coins originales
    if 'coins_only' in scenario:
        be.COINS = orig_coins
    
    return report

def analyze_scenario(scenario_name, report):
    """Analizar resultados del escenario"""
    if 'error' in report:
        return None
    
    total_trades = report['total_trades']
    net_pnl = report['net_pnl']
    win_rate = report['win_rate']
    avg_win = report['avg_win']
    avg_loss = report['avg_loss']
    profit_factor = report['profit_factor']
    
    # Calcular promedio por trade
    avg_per_trade = net_pnl / total_trades if total_trades > 0 else 0
    
    # Proyección mensual (90 días = 3 meses)
    monthly_pnl = net_pnl / 3
    monthly_trades = total_trades / 3
    
    return {
        'scenario': scenario_name,
        'total_trades': total_trades,
        'net_pnl': net_pnl,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'avg_per_trade': avg_per_trade,
        'monthly_pnl': monthly_pnl,
        'monthly_trades': monthly_trades,
        'meets_target': 0.8 <= avg_per_trade <= 2.0,
        'profit_factor_ok': profit_factor >= 1.5,
        'win_rate_ok': win_rate >= 25,
    }

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🎯 OPTIMIZADOR FASE 1 v2 - TARGET $0.8-2/TRADE      ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    # Cargar datos
    print("📥 Cargando datos históricos...")
    data = load_data()
    print(f"   ✅ {len(data)} velas cargadas")
    print()
    
    # Ejecutar escenarios
    results = []
    
    for i, scenario in enumerate(escenarios, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(escenarios)}] Escenario: {scenario['name']}")
        print(f"{'='*60}")
        
        # Restaurar COINS originales antes de cada escenario
        import backtest_engine as be
        be.COINS = {
            'BTC': be.CoinConfig('BTC', 3.5, '2-4%'),
            'ETH': be.CoinConfig('ETH', 4.5, '3-5%'),
            'BNB': be.CoinConfig('BNB', 3.5, '2-4%'),
            'SOL': be.CoinConfig('SOL', 7.0, '5-8%'),
            'LINK': be.CoinConfig('LINK', 5.5, '4-6%'),
            'XRP': be.CoinConfig('XRP', 4.5, '3-5%'),
            'AVAX': be.CoinConfig('AVAX', 6.0, '4-7%'),
        }
        
        report = run_scenario(data, scenario)
        analysis = analyze_scenario(scenario['name'], report)
        
        if analysis:
            results.append(analysis)
            
            print(f"\n📊 RESULTADOS:")
            print(f"   Total Trades:     {analysis['total_trades']}")
            print(f"   Win Rate:         {analysis['win_rate']:.1f}%")
            print(f"   P&L Neto:         ${analysis['net_pnl']:+.2f}")
            print(f"   Avg por Trade:    ${analysis['avg_per_trade']:+.2f}")
            print(f"   Mensual (proj):   ${analysis['monthly_pnl']:+.2f} ({analysis['monthly_trades']:.0f} trades)")
            print(f"   Profit Factor:    {analysis['profit_factor']:.2f}")
            print(f"   Avg Win:          ${analysis['avg_win']:.2f}")
            print(f"   Avg Loss:         ${analysis['avg_loss']:.2f}")
            
            print(f"\n🎯 VALIDACIÓN TARGET ($0.8-2/trade):")
            target_status = "✅ CUMPLE" if analysis['meets_target'] else "❌ NO CUMPLE"
            pf_status = "✅" if analysis['profit_factor_ok'] else "❌"
            wr_status = "✅" if analysis['win_rate_ok'] else "❌"
            
            print(f"   Target $0.8-2:    {target_status} (${analysis['avg_per_trade']:+.2f})")
            print(f"   Profit Factor:    {pf_status} ({analysis['profit_factor']:.2f})")
            print(f"   Win Rate:         {wr_status} ({analysis['win_rate']:.1f}%)")
    
    # Resumen final
    print(f"\n\n{'='*60}")
    print("📋 RESUMEN DE ESCENARIOS")
    print(f"{'='*60}")
    
    print(f"\n{'Escenario':<35} {'Avg/Trade':<12} {'PF':<8} {'Win%':<8} {'Status'}")
    print(f"{'-'*60}")
    
    best_scenario = None
    best_avg = -999
    
    for r in results:
        status = "✅" if r['meets_target'] and r['profit_factor_ok'] else "⚠️"
        print(f"{r['scenario']:<35} ${r['avg_per_trade']:+8.2f}  {r['profit_factor']:8.2f}  {r['win_rate']:5.1f}%  {status}")
        
        # Encontrar mejor escenario que cumpla target
        if r['meets_target'] and r['profit_factor_ok'] and r['avg_per_trade'] > best_avg:
            best_avg = r['avg_per_trade']
            best_scenario = r
    
    print(f"\n{'='*60}")
    
    if best_scenario:
        print(f"\n🏆 MEJOR ESCENARIO: {best_scenario['scenario']}")
        print(f"   Avg por Trade: ${best_scenario['avg_per_trade']:+.2f}")
        print(f"   Mensual:       ${best_scenario['monthly_pnl']:+.2f}")
        print(f"   Win Rate:      {best_scenario['win_rate']:.1f}%")
        print(f"   Profit Factor: {best_scenario['profit_factor']:.2f}")
        
        # Guardar recomendación
        recommendation = {
            'best_scenario': best_scenario['scenario'],
            'target_met': True,
            'avg_per_trade': best_scenario['avg_per_trade'],
            'monthly_projection': best_scenario['monthly_pnl'],
            'win_rate': best_scenario['win_rate'],
            'profit_factor': best_scenario['profit_factor'],
            'recommendation': 'APLICAR ESTOS PARÁMETROS'
        }
        
        with open('/home/overgon/.openclaw/workspace/backtest/optimization_recommendation.json', 'w') as f:
            json.dump(recommendation, f, indent=2)
        
        print(f"\n💾 Recomendación guardada en: optimization_recommendation.json")
    else:
        print("\n⚠️  NINGÚN ESCENARIO CUMPLE TODOS LOS CRITERIOS")
        print("   Se recomienda ajustar parámetros o revisar estrategia")
    
    print(f"\n{'='*60}")
