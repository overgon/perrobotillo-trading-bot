"""
Run backtest with Perrobotillo strategy in Jesse.
=================================================

Uses imported Perrobotillo 1h candle data (stored as 1m in DB).
Routes are configured for all 7 coins on Binance Spot 1h timeframe.
Compares results with Perrobotillo production trade history.

Fixes applied:
  - Exchange name: 'Binance Spot' (title case, matches DB)
  - Candles: 1m format (Jesse validates and resamples internally)
  - candles dict: string keys '{exchange}-{symbol}' with nested format
  - Data routes: BTC at 1h (not 4h/1D, since we only have 1h→1m)
  - Config: includes exchange, simulation_model, warm_up_candles
"""

import sys
import os
import json
import datetime
import time
import numpy as np

sys.path.insert(0, '/home')

from jesse.research import backtest, get_candles

# Perrobotillo coin portfolio (same 7 coins)
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'  # Strategy trades on 1h, but candles are stored as 1m


def get_routes():
    """Build routes matching Perrobotillo's trading setup."""
    routes = []
    for coin in COINS:
        routes.append({
            'exchange': EXCHANGE,
            'symbol': f'{coin}-USDT',
            'timeframe': TIMEFRAME,
            'strategy': 'perrobotillo',
            'stake': 1000.0,
        })
    return routes


def get_data_routes():
    """Data routes - BTC for market mode detection at 1h."""
    return [
        {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'},
    ]


def load_all_candles(start_ms, end_ms):
    """Load 1m candles for all coins (main + data routes)."""
    candles = {}
    # Unique symbols from main routes + data routes
    symbols = set(f'{c}-USDT' for c in COINS)
    # BTC is in both main routes and data_routes
    
    for symbol in sorted(symbols):
        try:
            c = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
            if isinstance(c, tuple):
                c = c[1]  # data is in second element
            if c is not None and len(c) > 0:
                key = f'{EXCHANGE}-{symbol}'
                candles[key] = {
                    'exchange': EXCHANGE,
                    'symbol': symbol,
                    'candles': c,
                }
                ts = c[0][0]
                if ts > 1e12:
                    ts = ts / 1000
                dt = datetime.datetime.fromtimestamp(ts)
                print(f'  ✅ {symbol}: {len(c)} 1m candles | {dt.strftime("%Y-%m-%d")} → ')
                ts_end = c[-1][0]
                if ts_end > 1e12:
                    ts_end = ts_end / 1000
                dt_end = datetime.datetime.fromtimestamp(ts_end)
                # Overwrite the print to include end date
                print(f'\r  ✅ {symbol}: {len(c)} 1m candles | {dt.strftime("%Y-%m-%d")} → {dt_end.strftime("%Y-%m-%d")}')
            else:
                print(f'  ❌ {symbol}: empty/None')
        except Exception as e:
            print(f'  ❌ {symbol}: {e}')
    
    return candles


def load_trade_history():
    """Load Perrobotillo production trade history."""
    path = '/home/research/trade-history.json'
    with open(path) as f:
        return json.load(f)


def analyze_production_history(trade_history, start_date=None, end_date=None):
    """Analyze Perrobotillo production trades within a date range."""
    trades = trade_history.get('trades', [])
    
    if start_date or end_date:
        filtered = []
        for t in trades:
            ct = t.get('closeTime', '')
            if not ct:
                continue
            try:
                ct_date = ct[:10]
                if start_date and ct_date < start_date:
                    continue
                if end_date and ct_date > end_date:
                    continue
                filtered.append(t)
            except:
                filtered.append(t)
        trades = filtered
    
    if not trades:
        return None
    
    pnls = [t.get('pnlUSDT', 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    # Per-coin analysis
    by_coin = {}
    for t in trades:
        coin = t.get('coin', '?')
        if coin not in by_coin:
            by_coin[coin] = {'wins': 0, 'losses': 0, 'pnls': [], 'count': 0}
        by_coin[coin]['count'] += 1
        by_coin[coin]['pnls'].append(t.get('pnlUSDT', 0))
        if t.get('pnlUSDT', 0) > 0:
            by_coin[coin]['wins'] += 1
        elif t.get('pnlUSDT', 0) < 0:
            by_coin[coin]['losses'] += 1
    
    pf = 0
    if losses and sum(wins) > 0:
        pf = abs(sum(wins) / sum(losses))
    
    result = {
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(pnls) * 100 if pnls else 0,
        'total_pnl': sum(pnls),
        'avg_win': sum(wins) / len(wins) if wins else 0,
        'avg_loss': sum(losses) / len(losses) if losses else 0,
        'profit_factor': pf if pf > 0 else float('inf'),
        'per_coin': by_coin,
    }
    return result


def run_backtest_coins(coins_subset, start_ms, end_ms):
    """Run backtest for a subset of coins."""
    routes = []
    for coin in coins_subset:
        routes.append({
            'exchange': EXCHANGE,
            'symbol': f'{coin}-USDT',
            'timeframe': TIMEFRAME,
            'strategy': 'perrobotillo',
            'stake': 1000.0,
        })
    
    data_routes = [
        {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'},
    ]
    
    config = {
        'starting_balance': 10000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'annualization': 365,
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }
    
    # Load 1m candles for all needed symbols
    symbols = set(f'{c}-USDT' for c in coins_subset)
    symbols.add('BTC-USDT')  # For data route
    
    candles = {}
    for symbol in sorted(symbols):
        c = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
        if isinstance(c, tuple):
            c = c[1]
        if c is not None and len(c) > 0:
            key = f'{EXCHANGE}-{symbol}'
            candles[key] = {
                'exchange': EXCHANGE,
                'symbol': symbol,
                'candles': c,
            }
    
    if len(candles) < len(coins_subset):
        print(f'  ⚠️  Only {len(candles)}/{len(coins_subset)} coins loaded')
        return None
    
    result = backtest(
        config=config,
        routes=routes,
        data_routes=data_routes,
        candles=candles,
    )
    
    return result


def main():
    # Production analysis
    print("=== Perrobotillo Production Analysis ===")
    trade_history = load_trade_history()
    prod_stats = analyze_production_history(
        trade_history,
        start_date='2026-01-18',
        end_date='2026-04-18'
    )
    
    if prod_stats:
        print(f"  Period: Jan 18 - Apr 18, 2026")
        print(f"  Total trades: {prod_stats['total_trades']}")
        print(f"  Win rate: {prod_stats['win_rate']:.1f}%")
        print(f"  Total PnL: ${prod_stats['total_pnl']:+.2f} USDT")
        print(f"  Avg win: ${prod_stats['avg_win']:+.2f}")
        print(f"  Avg loss: ${prod_stats['avg_loss']:+.2f}")
        print(f"  Profit factor: {prod_stats['profit_factor']:.2f}")
        print(f"\n  Per-coin:")
        for coin, stats in sorted(prod_stats['per_coin'].items()):
            total = stats['wins'] + stats['losses']
            wr = stats['wins'] / total * 100 if total > 0 else 0
            pnls = stats['pnls']
            wins_sum = sum(p for p in pnls if p > 0)
            losses_sum = sum(p for p in pnls if p < 0)
            pf = abs(wins_sum / losses_sum) if losses_sum else float('inf')
            print(f"    {coin:6s} | N={stats['count']:3d} | WR={wr:5.1f}% | PnL={sum(pnls):+8.2f} | PF={pf:.2f}")
    else:
        print("  No production trades in this date range")
        prod_stats = analyze_production_history(trade_history)
        print(f"\n  Full history:")
        print(f"  Total trades: {prod_stats['total_trades']}")
        print(f"  Win rate: {prod_stats['win_rate']:.1f}%")
        print(f"  Total PnL: ${prod_stats['total_pnl']:+.2f} USDT")
    
    print(f"\n{'='*60}")
    
    # Date range (same as Perrobotillo data)
    start_dt = datetime.datetime(2026, 1, 18, 0, 0, 0)
    end_dt = datetime.datetime(2026, 4, 18, 18, 0, 0)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    print(f"\n=== Jesse Backtest (1m candles, 1h strategy) ===")
    print(f"Date range: {start_dt} to {end_dt}")
    print(f"Loading 1m candles...\n")
    
    # Run backtest for BNB first (quick test)
    print("--- BNB (quick test) ---")
    result = run_backtest_coins(['BNB'], start_ms, end_ms)
    
    if result is None:
        print("  ❌ Backtest failed - insufficient data")
        return
    
    print(f"\n  ✅ Backtest completed!")
    metrics = result['metrics']
    print(f"  Total PnL: ${metrics['total']:+.2f}")
    print(f"  Win rate: {metrics['win_rate']:.1f}%")
    print(f"  Net profit %: {metrics['net_profit_percentage']:.2f}%")
    print(f"  Trades: {len(result.get('trades', []))}")
    
    if result.get('trades'):
        total_pnl = 0
        for t in result['trades']:
            print(f"  Trade: qty={t.get('qty', 0):.4f} entry={t.get('entry_price', 0):.4f} exit={t.get('exit_price', 0):.4f}")
    
    print(f"\n{'='*60}")
    print("\n=== Comparison: Production vs Jesse Backtest ===")
    if prod_stats:
        # Find BNB in production stats
        bnb_prod = prod_stats['per_coin'].get('BNB', {})
        if bnb_prod:
            print(f"  BNB Production: {bnb_prod['count']} trades | PnL: ${sum(bnb_prod['pnls']):+.2f}")
        print(f"  BNB Jesse:      {len(result.get('trades', []))} trades | PnL: ${metrics['total']:+.2f}")


if __name__ == '__main__':
    main()
