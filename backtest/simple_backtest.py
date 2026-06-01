#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - SIMPLE BACKTEST
# ════════════════════════════════════════════════════════
# Backtest simplificado usando datos locales existentes
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
LOGS_DIR = WORKSPACE.parent / "logs"
REPORTS_DIR = WORKSPACE / "backtest" / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

def load_trade_log(coin: str) -> pd.DataFrame:
    """Cargar logs de trades históricos"""
    log_file = LOGS_DIR / f"trade-{coin}.log"
    
    if not log_file.exists():
        return pd.DataFrame()
    
    trades = []
    with open(log_file, 'r') as f:
        for line in f:
            if "TP1 HIT" in line or "TP2 HIT" in line or "TP3 HIT" in line or "SL HIT" in line or "Trailing stop" in line:
                # Extraer fecha
                try:
                    date_str = line.split(']')[0].replace('[', '')
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Determinar tipo de salida
                    if "TP1" in line:
                        exit_type = "TP1"
                        pnl_pct = 0.025  # 2.5%
                    elif "TP2" in line:
                        exit_type = "TP2"
                        pnl_pct = 0.050  # 5.0%
                    elif "TP3" in line:
                        exit_type = "TP3"
                        pnl_pct = 0.080  # 8.0%
                    elif "SL HIT" in line or "Trailing stop" in line:
                        exit_type = "SL"
                        pnl_pct = -0.035  # -3.5%
                    else:
                        continue
                    
                    trades.append({
                        "date": date,
                        "coin": coin,
                        "exit_type": exit_type,
                        "pnl_pct": pnl_pct
                    })
                except:
                    continue
    
    return pd.DataFrame(trades)

def run_backtest(coin: str, days: int = 30):
    """Ejecutar backtest desde logs históricos"""
    print(f"\n{'='*60}")
    print(f"🐕 Backtest para {coin} (últimos {days} días)")
    print(f"{'='*60}")
    
    # Cargar trades
    df = load_trade_log(coin)
    
    if df.empty:
        print(f"❌ No hay trades históricos para {coin}")
        return None
    
    # Filtrar por días
    cutoff_date = datetime.now() - pd.Timedelta(days=days)
    df = df[df['date'] >= cutoff_date]
    
    if len(df) == 0:
        print(f"❌ No hay trades en los últimos {days} días")
        return None
    
    print(f"✅ {len(df)} trades encontrados")
    
    # Calcular métricas
    total_trades = len(df)
    winning_trades = len(df[df['pnl_pct'] > 0])
    losing_trades = len(df[df['pnl_pct'] < 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # P&L (asumiendo $50 por trade)
    stake_per_trade = 50
    total_pnl = (df['pnl_pct'] * stake_per_trade).sum()
    total_pnl_pct = (total_pnl / (stake_per_trade * total_trades)) * 100
    
    # Contar por tipo
    tp1_count = len(df[df['exit_type'] == 'TP1'])
    tp2_count = len(df[df['exit_type'] == 'TP2'])
    tp3_count = len(df[df['exit_type'] == 'TP3'])
    sl_count = len(df[df['exit_type'] == 'SL'])
    
    # Drawdown máximo (simplificado)
    cumulative = (df['pnl_pct'] * stake_per_trade).cumsum()
    peak = cumulative.cummax()
    drawdown = (peak - cumulative) / peak * 100
    max_drawdown = drawdown.max() if len(drawdown) > 0 else 0
    
    # Profit factor
    gross_profit = df[df['pnl_pct'] > 0]['pnl_pct'].abs().sum() * stake_per_trade
    gross_loss = df[df['pnl_pct'] < 0]['pnl_pct'].abs().sum() * stake_per_trade
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    results = {
        "coin": coin,
        "period_days": days,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "tp1_count": tp1_count,
        "tp2_count": tp2_count,
        "tp3_count": tp3_count,
        "sl_count": sl_count,
        "total_pnl_usdt": round(total_pnl, 2),
        "total_pnl_percent": round(total_pnl_pct, 2),
        "max_drawdown_percent": round(max_drawdown, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
        "avg_trade_pnl": round(total_pnl / total_trades, 2) if total_trades > 0 else 0
    }
    
    # Imprimir resultados
    print(f"\n📊 RESULTADOS:")
    print(f"  Total Trades:     {results['total_trades']}")
    print(f"  Wins:             {results['winning_trades']} ({results['win_rate']}%)")
    print(f"  Losses:           {results['losing_trades']}")
    print(f"  TP1/TP2/TP3:      {tp1_count}/{tp2_count}/{tp3_count}")
    print(f"  P&L Total:        ${results['total_pnl_usdt']} USDT ({results['total_pnl_percent']}%)")
    print(f"  Max Drawdown:     {results['max_drawdown_percent']}%")
    print(f"  Profit Factor:    {results['profit_factor']}")
    print(f"  Avg por Trade:    ${results['avg_trade_pnl']}")
    
    # Guardar reporte
    report_file = REPORTS_DIR / f"backtest_{coin}_{days}d.md"
    with open(report_file, 'w') as f:
        f.write(f"""# 🐕 Backtest Report - {coin}

_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
_Periodo: Últimos {days} días_

---

## 📊 Resumen de Performance

| Métrica | Valor |
|---------|-------|
| **Total Trades** | {results['total_trades']} |
| **Winning Trades** | {results['winning_trades']} ✅ |
| **Losing Trades** | {results['losing_trades']} ❌ |
| **Win Rate** | {results['win_rate']}% |
| **TP1 / TP2 / TP3** | {tp1_count} / {tp2_count} / {tp3_count} |
| **Stop Losses** | {sl_count} |
| **Total P&L** | ${results['total_pnl_usdt']} USDT ({results['total_pnl_percent']}%) |
| **Max Drawdown** | {results['max_drawdown_percent']}% |
| **Profit Factor** | {results['profit_factor']} |
| **Avg por Trade** | ${results['avg_trade_pnl']} |

---

## 📈 Distribución de Salidas

- 🎯 **TP1** (2.5%): {tp1_count} trades
- 🎯🎯 **TP2** (5.0%): {tp2_count} trades  
- 🎯🎯🎯 **TP3** (8.0%): {tp3_count} trades
- ❌ **SL** (-3.5%): {sl_count} trades

---

## 📝 Notas

- Backtest basado en trades reales ejecutados
- Datos extraídos de logs históricos
- Stake asumido: $50 USDT por trade
- Fees no incluidos

---

_Generado por Perrobotillo Backtest Engine 🐕_  
*"¡Nunca confiar, siempre verificar!"*
""")
    
    # Guardar JSON
    json_file = REPORTS_DIR / f"backtest_{coin}_{days}d.json"
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Reporte guardado: {report_file}")
    
    return results

def run_all_coins(days: int = 30):
    """Ejecutar backtest para todas las monedas"""
    print(f"\n{'='*60}")
    print("🐕 PERROBOTILLO BACKTEST - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    all_results = {}
    
    for coin in COINS:
        try:
            results = run_backtest(coin, days)
            if results:
                all_results[coin] = results
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
    
    # Resumen consolidado
    print(f"\n{'='*60}")
    print("🏆 RESUMEN CONSOLIDADO")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'Trades':<6} | {'Win Rate':<10} | {'P&L $':<10} | {'PF':<6}")
    print("-"*60)
    
    total_pnl = 0
    total_trades = 0
    total_wins = 0
    
    for coin, results in all_results.items():
        print(f"{coin:<6} | {results['total_trades']:<6} | {results['win_rate']:<10}% | ${results['total_pnl_usdt']:<9} | {results['profit_factor']:<6}")
        total_pnl += results['total_pnl_usdt']
        total_trades += results['total_trades']
        total_wins += results['winning_trades']
    
    print("-"*60)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    print(f"TOTAL  | {total_trades:<6} | {overall_win_rate:<10}% | ${total_pnl:<9} |")
    print(f"{'='*60}\n")
    
    return all_results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_all_coins(days)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_backtest(coin, days)
    else:
        print("Uso: python3 simple_backtest.py [--all|<COIN>] [days]")
        print("Ejemplo: python3 simple_backtest.py BTC 30")
        print("Ejemplo: python3 simple_backtest.py --all 60")
