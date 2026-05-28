#!/usr/bin/env python3
"""
💰 Dynamic Position Sizing - Ajuste automático de posición por moneda
Basado en performance histórico y condiciones actuales
"""

import json
import os
from datetime import datetime, timezone

WORKSPACE = "/home/overgon/.openclaw/workspace"
TRADE_HISTORY = f"{WORKSPACE}/crypto-bots/trade-history.json"
POSITION_SIZING_CONFIG = f"{WORKSPACE}/crypto-bots/position-sizing-config.json"
DYNAMIC_CONFIG = f"{WORKSPACE}/crypto-bots/dynamic-config.env"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
BASE_POSITION_SIZE = 15
WR_HIGH_THRESHOLD = 70
WR_LOW_THRESHOLD = 50
MIN_TRADES_FOR_ADJ = 10
MAX_POSITION_PCT = 25
MIN_POSITION_PCT = 5

def load_trade_history():
    if not os.path.exists(TRADE_HISTORY):
        return []
    with open(TRADE_HISTORY, 'r') as f:
        data = json.load(f)
    return data.get('trades', []) if isinstance(data, dict) else data

def calculate_coin_stats(trades, coin):
    coin_trades = [t for t in trades if t.get('symbol') == coin]
    if len(coin_trades) == 0:
        return {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0, 'recent_wr': 0, 'recent_pnl': 0}
    
    wins = [t for t in coin_trades if t.get('pnlUSDT', 0) > 0]
    losses = [t for t in coin_trades if t.get('pnlUSDT', 0) <= 0]
    total_pnl = sum(t.get('pnlUSDT', 0) for t in coin_trades)
    win_rate = len(wins) / len(coin_trades) * 100
    
    coin_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    recent = coin_trades[:10]
    recent_wins = [t for t in recent if t.get('pnlUSDT', 0) > 0]
    recent_wr = len(recent_wins) / len(recent) * 100 if len(recent) > 0 else 0
    recent_pnl = sum(t.get('pnlUSDT', 0) for t in recent)
    
    return {
        'trades': len(coin_trades), 'wins': len(wins), 'losses': len(losses),
        'win_rate': win_rate, 'total_pnl': total_pnl, 'avg_pnl': total_pnl / len(coin_trades),
        'recent_wr': recent_wr, 'recent_pnl': recent_pnl
    }

def calculate_position_size(stats):
    if stats['trades'] < MIN_TRADES_FOR_ADJ:
        return BASE_POSITION_SIZE, "INSUFFICIENT_DATA"
    
    recent_wr = stats['recent_wr']
    recent_pnl = stats['recent_pnl']
    
    if recent_wr >= WR_HIGH_THRESHOLD:
        adjustment = 1.33
        reason = f"WR {recent_wr:.1f}% >= {WR_HIGH_THRESHOLD}% (alto)"
    elif recent_wr >= WR_LOW_THRESHOLD:
        adjustment = 1.0
        reason = f"WR {recent_wr:.1f}% ({WR_LOW_THRESHOLD}-{WR_HIGH_THRESHOLD}%, medio)"
    else:
        adjustment = 0.67
        reason = f"WR {recent_wr:.1f}% < {WR_LOW_THRESHOLD}% (bajo)"
    
    if recent_pnl < 0:
        adjustment *= 0.9
        reason += " + PnL negativo reciente"
    
    position_size = BASE_POSITION_SIZE * adjustment
    position_size = max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, position_size))
    
    return round(position_size, 1), reason

def main():
    print("=" * 60)
    print("  DYNAMIC POSITION SIZING CALCULATOR")
    print("=" * 60)
    
    trades = load_trade_history()
    if len(trades) == 0:
        print("No hay trades")
        return
    
    config = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_position_size': BASE_POSITION_SIZE,
        'coins': {}
    }
    
    print(f"\nBase Position Size: {BASE_POSITION_SIZE}%\n")
    
    for coin in COINS:
        stats = calculate_coin_stats(trades, coin)
        position_size, reason = calculate_position_size(stats)
        
        config['coins'][coin] = {
            'position_size': position_size,
            'reason': reason,
            'stats': stats
        }
        
        emoji = "OK" if position_size >= BASE_POSITION_SIZE else "LOW"
        print(f"[{emoji}] {coin}: {position_size}% - {reason}")
        print(f"       Trades: {stats['trades']}, WR: {stats['recent_wr']:.1f}%, PnL: ${stats['recent_pnl']:.2f}")
    
    # Guardar config
    with open(POSITION_SIZING_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\nConfig guardada: {POSITION_SIZING_CONFIG}")
    
    # Actualizar dynamic-config.env
    with open(DYNAMIC_CONFIG, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    added = False
    for line in lines:
        if any(f"POSITION_SIZE_{coin}" in line for coin in COINS):
            continue
        new_lines.append(line)
        if line.startswith('export POSITION_SIZE=') and not added:
            new_lines.append("\n# Position Size por Moneda\n")
            for coin in COINS:
                pct = config['coins'][coin]['position_size']
                new_lines.append(f"export POSITION_SIZE_{coin}={pct}\n")
            added = True
    
    with open(DYNAMIC_CONFIG, 'w') as f:
        f.writelines(new_lines)
    print("dynamic-config.env actualizado")
    
    print("\n✅ Position sizing completado")

if __name__ == "__main__":
    main()
