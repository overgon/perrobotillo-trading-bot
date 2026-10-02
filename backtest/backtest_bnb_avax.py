#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║  🎯 PERROBOTILLO BNB+AVAX SPECIAL EDITION             ║
║  Validación 6 meses - Target $0.8-2/trade            ║
╚═══════════════════════════════════════════════════════╝
"""

import sys
import os
sys.path.insert(0, '/home/overgon/.openclaw/workspace/backtest')

from backtest_engine import BacktestEngine, COINS, CoinConfig
import csv
import json
from datetime import datetime

# ============================================
# CONFIGURACIÓN OPTIMIZADA BNB+AVAX
# ============================================

# Sobrescribir configuración de coins
COINS = {
    'BNB': CoinConfig('BNB', 2.5, '2-4%'),   # SL 2.5%
    'AVAX': CoinConfig('AVAX', 4.0, '4-7%'), # SL 4.0%
}

# Parámetros FASE 1 v2 OPTIMIZADA
TRADE_PERCENT = 30
TP1_PERCENT = 2.5   # Aumentado de 1.5%
TP2_PERCENT = 5.0   # Aumentado de 3.0%
TP3_PERCENT = 8.0   # Aumentado de 3.5%
TP1_PORTION = 0.35
TP2_PORTION = 0.30
TP3_PORTION = 0.30

TRAILING_AFTER_TP1 = 0.5  # Breakeven más conservador
TRAILING_AFTER_TP2 = 3.0  # Trailing más amplio para capturar trends

MAX_SLOTS = 3
INITIAL_CAPITAL = 2000.0

# ============================================
# FUNCIONES
# ============================================

def load_data():
    """Cargar datos de BNB y AVAX (6 meses)"""
    DATA_DIR = '/home/overgon/.openclaw/workspace/backtest/data'
    all_data = []
    
    coins = ['BNBUSDT', 'AVAXUSDT']
    
    for coin in coins:
        filepath = f"{DATA_DIR}/{coin}_1h_180days.csv"
        
        if not os.path.exists(filepath):
            print(f"⚠️  Archivo no encontrado: {filepath}")
            continue
        
        print(f"📥 Cargando {coin}...")
        
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
    
    print(f"✅ {len(all_data)} velas cargadas en total")
    return all_data

def run_backtest(data):
    """Ejecutar backtest con configuración optimizada"""
    
    # Importar y modificar parámetros del engine
    import backtest_engine as be
    
    # Guardar originales
    orig_coins = be.COINS.copy()
    orig_tp1 = be.TP1_PERCENT
    orig_tp2 = be.TP2_PERCENT
    orig_tp3 = be.TP3_PERCENT
    orig_trailing1 = be.TRAILING_AFTER_TP1
    orig_trailing2 = be.TRAILING_AFTER_TP2
    
    # Aplicar configuración optimizada
    be.COINS = COINS
    be.TP1_PERCENT = TP1_PERCENT
    be.TP2_PERCENT = TP2_PERCENT
    be.TP3_PERCENT = TP3_PERCENT
    be.TRAILING_AFTER_TP1 = TRAILING_AFTER_TP1
    be.TRAILING_AFTER_TP2 = TRAILING_AFTER_TP2
    
    # Ejecutar backtest
    engine = BacktestEngine(initial_capital=INITIAL_CAPITAL)
    report = engine.run(data)
    
    # Restaurar originales
    be.COINS = orig_coins
    be.TP1_PERCENT = orig_tp1
    be.TP2_PERCENT = orig_tp2
    be.TP3_PERCENT = orig_tp3
    be.TRAILING_AFTER_TP1 = orig_trailing1
    be.TRAILING_AFTER_TP2 = orig_trailing2
    
    return report

def generate_report(report):
    """Generar reporte bonito"""
    
    total_trades = report['total_trades']
    wins = report['wins']
    losses = report['losses']
    win_rate = report['win_rate']
    net_pnl = report['net_pnl']
    profit_factor = report['profit_factor']
    avg_win = report['avg_win']
    avg_loss = report['avg_loss']
    return_pct = report['return_percent']
    max_dd = report['max_drawdown']
    
    # Proyecciones
    monthly_trades = total_trades / 6  # 6 meses
    monthly_pnl = net_pnl / 6
    avg_per_trade = net_pnl / total_trades if total_trades > 0 else 0
    
    # Validación
    target_met = 0.8 <= avg_per_trade <= 2.0
    win_rate_ok = win_rate >= 70
    profit_factor_ok = profit_factor >= 1.5
    
    report_text = f"""
╔═══════════════════════════════════════════════════════╗
║  🎯 REPORTE BNB+AVAX - PERROBOTILLO                  ║
║  Validación 6 Meses - FASE 1 v2 OPTIMIZADA           ║
╚═══════════════════════════════════════════════════════╝

📊 ESTADÍSTICAS GENERALES (6 MESES):
═══════════════════════════════════════════════════════

   Total Trades:        {total_trades}
   Wins:                {wins}
   Losses:              {losses}
   Win Rate:            {win_rate:.1f}% {'✅' if win_rate >= 70 else '⚠️'}
   
💰 RESULTADOS FINANCIEROS:
═══════════════════════════════════════════════════════

   Capital Inicial:     ${INITIAL_CAPITAL:.2f}
   Capital Final:       ${report['final_capital']:.2f}
   P&L Neto:            ${net_pnl:+.2f}
   Retorno:             {return_pct:+.2f}%
   Profit Factor:       {profit_factor:.2f} {'✅' if profit_factor >= 1.5 else '⚠️'}
   Max Drawdown:        {max_dd:.2f}% {'✅' if max_dd <= 15 else '⚠️'}

📈 PROMEDIOS:
═══════════════════════════════════════════════════════

   Avg por Trade:       ${avg_per_trade:+.2f} {'✅' if target_met else '⚠️'}
   Avg Win:             ${avg_win:.2f}
   Avg Loss:            ${avg_loss:.2f}
   Win/Loss Ratio:      {avg_win/avg_loss:.2f}' if avg_loss > 0 else 'N/A

📅 PROYECCIÓN MENSUAL:
═══════════════════════════════════════════════════════

   Trades/Mes:          {monthly_trades:.0f}
   P&L Mensual:         ${monthly_pnl:+.2f}
   P&L Anual:           ${monthly_pnl * 12:+.2f}

🪙 POR COIN:
═══════════════════════════════════════════════════════
"""
    
    for coin in ['BNB', 'AVAX']:
        if coin in report['trades_by_coin']:
            stats = report['trades_by_coin'][coin]
            coin_wr = (stats['wins'] / stats['count']) * 100 if stats['count'] > 0 else 0
            report_text += f"   {coin:4s}: {stats['count']:3d} trades | {stats['wins']:2d} wins ({coin_wr:5.1f}%) | P&L: ${stats['net_pnl']:+.2f}\n"
    
    report_text += f"""
🎯 VALIDACIÓN TARGET ($0.8-2/trade):
═══════════════════════════════════════════════════════

   Target $0.8-2:       {'✅ CUMPLE' if target_met else '❌ NO CUMPLE'} (${avg_per_trade:+.2f})
   Win Rate >70%:       {'✅ CUMPLE' if win_rate_ok else '❌ NO CUMPLE'} ({win_rate:.1f}%)
   Profit Factor >1.5:  {'✅ CUMPLE' if profit_factor_ok else '❌ NO CUMPLE'} ({profit_factor:.2f})
   Drawdown <15%:       {'✅ CUMPLE' if max_dd <= 15 else '⚠️ ALTO'} ({max_dd:.1f}%)

🏆 VEREDICTO:
═══════════════════════════════════════════════════════

"""
    
    if target_met and win_rate_ok and profit_factor_ok:
        report_text += "   ✅✅✅ FASE 1 v2 OPTIMIZADA APROBADA ✅✅✅\n\n"
        report_text += "   🎯 ESTRATEGIA VIABLE Y RENTABLE\n"
        report_text += "   🚀 RECOMENDACIÓN: IMPLEMENTAR INMEDIATAMENTE\n"
        verdict = "APROBADA"
    elif win_rate_ok and profit_factor_ok:
        report_text += "   ✅✅ FASE 1 v2 OPTIMIZADA APROBADA (CON RESERVAS) ✅✅\n\n"
        report_text += "   ⚠️ ESTRATEGIA VIABLE PERO TARGET NO ALCANZADO\n"
        report_text += "   🤔 RECOMENDACIÓN: AJUSTAR TPs O REDUCIR SL\n"
        verdict = "APROBADA_CON_RESERVAS"
    else:
        report_text += "   ❌ FASE 1 v2 OPTIMIZADA NO APROBADA ❌\n\n"
        report_text += "   ⚠️ ESTRATEGIA REQUIERE MÁS VALIDACIÓN\n"
        report_text += "   🛑 RECOMENDACIÓN: PAUSAR Y REVISAR\n"
        verdict = "NO_APROBADA"
    
    report_text += f"""
📋 CRITERIOS APROBADOS: {sum([target_met, win_rate_ok, profit_factor_ok, max_dd <= 15])}/4

═══════════════════════════════════════════════════════
"""
    
    return report_text, verdict

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🐕 PERROBOTILLO BNB+AVAX SPECIAL EDITION             ║")
    print("║  🎯 Validación 6 Meses - Target $0.8-2/trade          ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    # Cargar datos
    print("📥 Cargando datos históricos (6 meses)...")
    data = load_data()
    
    if not data:
        print("\n❌ No se encontraron datos.")
        print("   Ejecuta primero: download_binance_data.py")
        print("   (Descarga 6 meses de BNB y AVAX)")
        sys.exit(1)
    
    print(f"\n🔧 Configuración Optimizada:")
    print(f"   TP1: {TP1_PERCENT}% | TP2: {TP2_PERCENT}% | TP3: {TP3_PERCENT}%")
    print(f"   SL BNB: 2.5% | SL AVAX: 4.0%")
    print(f"   Trailing: {TRAILING_AFTER_TP1}% (TP1) | {TRAILING_AFTER_TP2}% (TP2)")
    print()
    
    # Ejecutar backtest
    print("🚀 Ejecutando backtest...")
    report = run_backtest(data)
    
    if 'error' in report:
        print(f"\n❌ Error: {report['error']}")
        sys.exit(1)
    
    # Generar reporte
    report_text, verdict = generate_report(report)
    print(report_text)
    
    # Guardar reporte
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # JSON
    json_file = f'/home/overgon/.openclaw/workspace/backtest/bnb_avax_report_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Markdown
    md_file = f'/home/overgon/.openclaw/workspace/backtest/BNB_AVAX_VALIDATION_{timestamp}.md'
    with open(md_file, 'w') as f:
        f.write(f"# 🎯 VALIDACIÓN BNB+AVAX - {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(report_text)
    
    # Guardar veredicto
    with open('/home/overgon/.openclaw/workspace/backtest/validation_verdict.json', 'w') as f:
        json.dump({
            'verdict': verdict,
            'timestamp': datetime.now().isoformat(),
            'period': '6 months',
            'coins': ['BNB', 'AVAX'],
            'win_rate': report['win_rate'],
            'profit_factor': report['profit_factor'],
            'avg_per_trade': report['net_pnl'] / report['total_trades'] if report['total_trades'] > 0 else 0
        }, f, indent=2)
    
    print(f"\n💾 Reportes guardados:")
    print(f"   • {json_file}")
    print(f"   • {md_file}")
    print(f"   • validation_verdict.json")
    
    print("\n" + "═"*60)
    if verdict == "APROBADA":
        print("🎉 ¡VALIDACIÓN EXITOSA! LISTO PARA IMPLEMENTAR 🎉")
    elif verdict == "APROBADA_CON_RESERVAS":
        print("⚠️  VALIDACIÓN PARCIAL - REQUIERE AJUSTES")
    else:
        print("🛑 VALIDACIÓN FALLIDA - NO IMPLEMENTAR")
    print("═"*60)
