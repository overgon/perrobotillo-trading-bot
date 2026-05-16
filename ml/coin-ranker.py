#!/usr/bin/env python3
"""
🪙 Coin Ranker - Ranking Simple de Performance por Coin
Sin ML, solo estadísticas básicas del historial

Output:
- Ranking por win rate
- P&L por coin
- Sugerencia de coins a pausar
"""

import json
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = "/home/overgon/.openclaw/workspace"
CRYPTO_BOTS = os.path.join(WORKSPACE, "crypto-bots")
ML_DIR = os.path.join(WORKSPACE, "ml")

TRADE_HISTORY_FILE = os.path.join(CRYPTO_BOTS, "trade-history.json")
RANKING_FILE = os.path.join(ML_DIR, "coin-ranking.json")

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# Umbrales para sugerencias
MIN_TRADES_FOR_RANKING = 3  # Mínimo trades para considerar ranking
LOW_WINRATE_THRESHOLD = 0.70  # < 70% → considerar pausar
HIGH_WINRATE_THRESHOLD = 0.90  # > 90% → priorizar

# ════════════════════════════════════════════════════════
# CARGAR HISTORIAL
# ════════════════════════════════════════════════════════

def load_trade_history():
    """Cargar historial de trades"""
    if not os.path.exists(TRADE_HISTORY_FILE):
        print(f"❌ No hay historial en {TRADE_HISTORY_FILE}")
        return None
    
    with open(TRADE_HISTORY_FILE, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', [])
    print(f"✅ Cargados {len(trades)} trades del historial")
    
    return trades

# ════════════════════════════════════════════════════════
# CALCULAR ESTADÍSTICAS POR COIN
# ════════════════════════════════════════════════════════

def calculate_coin_stats(trades):
    """Calcular estadísticas por coin"""
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
    df['pnlUSDT'] = df['pnlUSDT'].astype(float)
    df['is_win'] = df['pnlUSDT'] > 0
    
    stats = {}
    
    for coin in COINS:
        coin_trades = df[df['symbol'] == coin]
        
        if len(coin_trades) == 0:
            stats[coin] = {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'trades_24h': 0,
                'win_rate_24h': 0,
                'pnl_24h': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'consecutive_wins': 0,
                'consecutive_losses': 0
            }
            continue
        
        # Estadísticas generales
        total_trades = len(coin_trades)
        wins = coin_trades[coin_trades['pnlUSDT'] > 0]
        losses = coin_trades[coin_trades['pnlUSDT'] < 0]
        
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        total_pnl = coin_trades['pnlUSDT'].sum()
        avg_pnl = coin_trades['pnlUSDT'].mean()
        avg_win = wins['pnlUSDT'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['pnlUSDT'].mean()) if len(losses) > 0 else 0
        
        # Profit factor
        gross_profit = wins['pnlUSDT'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnlUSDT'].sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        
        # Últimas 24h
        now = datetime.now(timezone.utc)
        trades_24h = coin_trades[coin_trades['timestamp'] >= (now - timedelta(hours=24))]
        trades_24h_count = len(trades_24h)
        win_rate_24h = (trades_24h['pnlUSDT'] > 0).mean() if trades_24h_count > 0 else 0
        pnl_24h = trades_24h['pnlUSDT'].sum() if trades_24h_count > 0 else 0
        
        # Largest win/loss
        largest_win = wins['pnlUSDT'].max() if len(wins) > 0 else 0
        largest_loss = abs(losses['pnlUSDT'].min()) if len(losses) > 0 else 0
        
        # Rachas (últimos 10 trades)
        recent = coin_trades.sort_values('timestamp', ascending=False).head(10)
        if len(recent) > 0:
            win_streak = 0
            loss_streak = 0
            current_win = 0
            current_loss = 0
            
            for _, row in recent.iterrows():
                if row['pnlUSDT'] > 0:
                    current_win += 1
                    current_loss = 0
                    win_streak = max(win_streak, current_win)
                else:
                    current_loss += 1
                    current_win = 0
                    loss_streak = max(loss_streak, current_loss)
        else:
            win_streak = 0
            loss_streak = 0
        
        stats[coin] = {
            'total_trades': total_trades,
            'wins': win_count,
            'losses': loss_count,
            'win_rate': round(win_rate, 4),
            'total_pnl': round(total_pnl, 8),
            'avg_pnl': round(avg_pnl, 8),
            'avg_win': round(avg_win, 8),
            'avg_loss': round(avg_loss, 8),
            'profit_factor': round(profit_factor, 4),
            'trades_24h': trades_24h_count,
            'win_rate_24h': round(win_rate_24h, 4),
            'pnl_24h': round(pnl_24h, 8),
            'largest_win': round(largest_win, 8),
            'largest_loss': round(largest_loss, 8),
            'consecutive_wins': win_streak,
            'consecutive_losses': loss_streak
        }
    
    return stats

# ════════════════════════════════════════════════════════
# GENERAR RANKING
# ════════════════════════════════════════════════════════

def generate_ranking(stats):
    """Generar ranking de coins"""
    
    # Filtrar coins con al menos MIN_TRADES_FOR_RANKING trades
    eligible_coins = {
        coin: data for coin, data in stats.items()
        if data['total_trades'] >= MIN_TRADES_FOR_RANKING
    }
    
    if not eligible_coins:
        print("⚠️ No hay coins con suficientes trades para ranking")
        return []
    
    # Ranking por win rate (mínimo 3 trades)
    ranking_by_winrate = sorted(
        eligible_coins.items(),
        key=lambda x: x[1]['win_rate'],
        reverse=True
    )
    
    # Ranking por P&L total
    ranking_by_pnl = sorted(
        eligible_coins.items(),
        key=lambda x: x[1]['total_pnl'],
        reverse=True
    )
    
    # Ranking por performance 24h
    ranking_24h = sorted(
        [(coin, data) for coin, data in eligible_coins.items() if data['trades_24h'] > 0],
        key=lambda x: x[1]['win_rate_24h'],
        reverse=True
    )
    
    return {
        'by_winrate': ranking_by_winrate,
        'by_pnl': ranking_by_pnl,
        'by_24h': ranking_24h
    }

# ════════════════════════════════════════════════════════
# GENERAR SUGERENCIAS
# ════════════════════════════════════════════════════════

def generate_suggestions(stats, ranking):
    """Generar sugerencias basadas en performance"""
    
    suggestions = {
        'prioritize': [],
        'normal': [],
        'consider_pause': [],
        'pause': []
    }
    
    for coin, data in stats.items():
        if data['total_trades'] < MIN_TRADES_FOR_RANKING:
            suggestions['normal'].append({
                'coin': coin,
                'reason': f'Insuficientes trades ({data["total_trades"]})'
            })
            continue
        
        win_rate = data['win_rate']
        win_rate_24h = data['win_rate_24h']
        pnl_24h = data['pnl_24h']
        
        # Priorizar: win rate > 90% y performance 24h positivo
        if win_rate >= HIGH_WINRATE_THRESHOLD and (pnl_24h >= 0 or win_rate_24h >= HIGH_WINRATE_THRESHOLD):
            suggestions['prioritize'].append({
                'coin': coin,
                'reason': f'Win rate {win_rate:.1%} | 24h: {win_rate_24h:.1%}'
            })
        
        # Pausar: win rate < 70% con múltiples trades
        elif win_rate < LOW_WINRATE_THRESHOLD and data['total_trades'] >= 5:
            suggestions['pause'].append({
                'coin': coin,
                'reason': f'Win rate bajo {win_rate:.1%} ({data["wins"]}/{data["total_trades"]})'
            })
        
        # Considerar pausa: win rate < 75% o pérdidas 24h
        elif win_rate < 0.75 or (data['trades_24h'] >= 3 and pnl_24h < 0):
            suggestions['consider_pause'].append({
                'coin': coin,
                'reason': f'Win rate {win_rate:.1%} | 24h P&L: ${pnl_24h:.2f}'
            })
        
        # Normal: resto
        else:
            suggestions['normal'].append({
                'coin': coin,
                'reason': f'Win rate {win_rate:.1%} - performance estable'
            })
    
    return suggestions

# ════════════════════════════════════════════════════════
# IMPRIMIR RANKING
# ════════════════════════════════════════════════════════

def print_ranking(stats, ranking, suggestions):
    """Imprimir ranking formateado"""
    
    print("\n" + "="*70)
    print("🪙 COIN RANKING - PERFORMANCE POR COIN")
    print("="*70)
    
    print("\n📊 RANKING POR WIN RATE (mínimo 3 trades):")
    print("-" * 70)
    print(f"{'#':<3} {'Coin':<6} {'Win Rate':<10} {'Trades':<8} {'P&L Total':<12} {'24h':<8}")
    print("-" * 70)
    
    for i, (coin, data) in enumerate(ranking['by_winrate'], 1):
        medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else ' '
        print(f"{medal} {i:<2} {coin:<6} {data['win_rate']:.1%}{'':>5} {data['total_trades']:<8} ${data['total_pnl']:<11.2f} {data['win_rate_24h']:.0%} ({data['trades_24h']})")
    
    print("\n💰 RANKING POR P&L TOTAL:")
    print("-" * 70)
    for i, (coin, data) in enumerate(ranking['by_pnl'][:5], 1):
        print(f"  {i}. {coin}: ${data['total_pnl']:.2f} ({data['wins']}/{data['total_trades']} wins)")
    
    print("\n🔥 RANKING 24 HORAS:")
    print("-" * 70)
    if ranking['by_24h']:
        for i, (coin, data) in enumerate(ranking['by_24h'][:5], 1):
            print(f"  {i}. {coin}: {data['win_rate_24h']:.0%} ({data['trades_24h']} trades, ${data['pnl_24h']:.2f})")
    else:
        print("  Sin trades en últimas 24h")
    
    print("\n" + "="*70)
    print("💡 SUGERENCIAS:")
    print("="*70)
    
    if suggestions['prioritize']:
        print("\n✅ PRIORIZAR (alto performance):")
        for item in suggestions['prioritize']:
            print(f"   • {item['coin']}: {item['reason']}")
    
    if suggestions['normal']:
        print("\n👌 NORMAL (performance estable):")
        for item in suggestions['normal']:
            print(f"   • {item['coin']}: {item['reason']}")
    
    if suggestions['consider_pause']:
        print("\n⚠️  CONSIDERAR PAUSAR (performance bajo):")
        for item in suggestions['consider_pause']:
            print(f"   • {item['coin']}: {item['reason']}")
    
    if suggestions['pause']:
        print("\n🛑 PAUSAR RECOMENDADO (muy bajo performance):")
        for item in suggestions['pause']:
            print(f"   • {item['coin']}: {item['reason']}")
    
    print("\n" + "="*70)

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🪙 COIN RANKER - PERFORMANCE RANKING                 ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    trades = load_trade_history()
    if not trades:
        return None
    
    print("\n⏳ Calculando estadísticas...")
    stats = calculate_coin_stats(trades)
    
    print("⏳ Generando ranking...")
    ranking = generate_ranking(stats)
    
    print("⏳ Generando sugerencias...")
    suggestions = generate_suggestions(stats, ranking)
    
    # Imprimir ranking
    print_ranking(stats, ranking, suggestions)
    
    # Guardar resultado
    output = {
        'timestamp': datetime.now().isoformat(),
        'total_trades': len(trades),
        'stats': stats,
        'ranking': {
            'by_winrate': [(coin, data) for coin, data in ranking['by_winrate']],
            'by_pnl': [(coin, data) for coin, data in ranking['by_pnl']],
            'by_24h': [(coin, data) for coin, data in ranking['by_24h']]
        },
        'suggestions': suggestions
    }
    
    # Convertir a formato JSON serializable
    output['ranking'] = {
        'by_winrate': [[coin, data] for coin, data in ranking['by_winrate']],
        'by_pnl': [[coin, data] for coin, data in ranking['by_pnl']],
        'by_24h': [[coin, data] for coin, data in ranking['by_24h']]
    }
    
    with open(RANKING_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Ranking guardado: {RANKING_FILE}")
    
    return output

if __name__ == "__main__":
    main()
