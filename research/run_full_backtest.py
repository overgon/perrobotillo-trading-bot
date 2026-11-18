#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# CI BACKTEST — ejecuta el backtest de Perrobotillo y emite backtest.json
# con el formato que consume research/ci_backtest_gate.py:
#   { "baseline": {...}, "latest": { "Sharpe", "totalPnL", "winRate", ... } }
#
# Uso:
#   python research/run_full_backtest.py --symbol BNBUSDT --days 14
#   python research/run_full_backtest.py --symbol BNBUSDT --start 2026-10-01 --end 2026-10-15
#   python research/run_full_backtest.py --symbol ALL --start 2026-01-18 --end 2026-04-18
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, '/home')

from jesse.research import backtest, get_candles  # noqa: E402

EXCHANGE = 'Binance Spot'
ALL_COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']
BASELINE_PATH = Path('research/ci_baseline.json')


def parse_symbol(raw: str) -> str:
    """Acepta BNBUSDT o BNB-USDT y devuelve la notación Jesse (BNB-USDT)."""
    raw = raw.upper()
    return raw if '-USDT' in raw else f'{raw[:-4]}-USDT'


def candle_dict(symbol: str, start_ms: int, end_ms: int):
    c = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
    if isinstance(c, tuple):
        c = c[1]
    if c is None or len(c) == 0:
        raise RuntimeError(f'sin velas para {symbol}; importa primero research/jesse_import_candles.py')
    return {f'{EXCHANGE}-{symbol}': {'exchange': EXCHANGE, 'symbol': symbol, 'candles': c}}


def to_latest(metrics: dict) -> dict:
    """Mapea las métricas de Jesse al formato que consume el gate."""
    return {
        'Sharpe': metrics.get('sharpe_ratio', 0.0),
        'totalPnL': metrics.get('net_profit', 0.0),
        'winRate': metrics.get('win_rate', 0.0),
        'totalTrades': metrics.get('total', 0),
        'netProfitPct': metrics.get('net_profit_percentage', 0.0),
        'maxDrawdown': metrics.get('max_drawdown', 0.0),
        'calmar': metrics.get('calmar_ratio', 0.0),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Backtest de Perrobotillo para el CI gate')
    ap.add_argument('--symbol', default='BNBUSDT', help='BNBUSDT, ETH-USDT o ALL')
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--warmup', type=int, default=200, help='velas 1h de calentamiento')
    ap.add_argument('--baseline', default=str(BASELINE_PATH))
    ap.add_argument('--out', default='backtest.json')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    coins = ALL_COINS if args.symbol.upper() == 'ALL' else [parse_symbol(args.symbol).split('-')[0]]

    if args.start:
        start = datetime.datetime.strptime(args.start, '%Y-%m-%d')
    else:
        start = datetime.datetime.now() - datetime.timedelta(days=args.days)
    end = datetime.datetime.strptime(args.end, '%Y-%m-%d') if args.end else datetime.datetime.now()

    start_ms = int(start.timestamp() * 1000) - args.warmup * 3_600_000
    end_ms = int(end.timestamp() * 1000)

    candles = {}
    for coin in coins:
        candles.update(candle_dict(f'{coin}-USDT', start_ms, end_ms))
        print(f'✅ {coin}-USDT: {len(candles[f"{EXCHANGE}-{coin}-USDT"]["candles"])} 1m candles')

    routes = [{'exchange': EXCHANGE, 'symbol': f'{c}-USDT', 'timeframe': '1h',
               'strategy': 'perrobotillo', 'stake': 1000.0} for c in coins]
    data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]
    config = {'starting_balance': 10_000.0 * len(coins), 'fee': 0.001, 'type': 'spot',
              'simulation_model': 'spot', 'annualization': 365,
              'exchange': EXCHANGE, 'warm_up_candles': args.warmup}

    result = backtest(config=config, routes=routes, data_routes=data_routes, candles=candles, fast_mode=True)
    metrics = result.get('metrics', {})

    baseline = {}
    if Path(args.baseline).exists():
        baseline = json.loads(Path(args.baseline).read_text())

    payload = {
        'symbol': 'ALL' if len(coins) > 1 else f'{coins[0]}-USDT',
        'period': {'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d')},
        'baseline': baseline,
        'latest': to_latest(metrics),
        'metrics': metrics,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2, default=float))

    latest = payload['latest']
    if args.json:
        print(json.dumps(payload, default=float))
    else:
        print(f"Backtest {payload['symbol']} {payload['period']['start']} → {payload['period']['end']}")
        print(f"  trades={latest['totalTrades']}  PnL={latest['totalPnL']:+.2f}  "
              f"WR={latest['winRate'] * 100:.1f}%  Sharpe={latest['Sharpe']:+.3f}")
        print(f"  → {args.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
