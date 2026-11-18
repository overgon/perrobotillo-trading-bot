#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# JESSE — Importador de velas Binance → DB de Jesse (1h → 1m)
#
# Jesse 3.6 solo acepta velas de 1m en research.store_candles(); este script
# descarga klines de 1h desde la API pública de Binance, los expande a 1m
# (preservando OHLC al resamplear) y los guarda en la DB PostgreSQL de Jesse.
#
# Uso (desde la raíz del proyecto, con venv-jesse):
#   venv-jesse/bin/python3 research/jesse_import_candles.py --coins BTC --start 2025-11-01 --end 2025-11-08
#   venv-jesse/bin/python3 research/jesse_import_candles.py --coins BTC,ETH --start 2024-11-01 --end 2026-11-01
#   venv-jesse/bin/python3 research/jesse_import_candles.py --coins BTC --reset
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import sys
import time
from datetime import datetime

import numpy as np
import requests

sys.path.insert(0, '/home')

from jesse.research import store_candles  # noqa: E402

BINANCE_API = "https://api.binance.com/api/v3/klines"
EXCHANGE = "Binance Spot"
INTERVAL = "1h"
RATE_LIMIT_SLEEP = 0.1
CHUNK_ROWS = 20_000  # filas 1m por llamada a store_candles


def download_klines(symbol: str, start_ts: int, end_ts: int) -> list:
    """Descarga klines 1h de Binance con paginación (máx. 1000 por página)."""
    rows = []
    current = start_ts
    while current < end_ts:
        resp = requests.get(
            BINANCE_API,
            params={
                'symbol': symbol,
                'interval': INTERVAL,
                'startTime': current,
                'endTime': end_ts,
                'limit': 1000,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} para {symbol}: {resp.text[:200]}")
        data = resp.json()
        if not data:
            break
        for row in data:
            rows.append({
                'timestamp': datetime.fromtimestamp(row[0] / 1000).strftime('%Y-%m-%dT%H:%M:%S'),
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': float(row[5]),
            })
        if len(data) < 1000:
            break
        current = data[-1][0] + 1
        time.sleep(RATE_LIMIT_SLEEP)
    return rows


def expand_1h_to_1m(rows: list) -> np.ndarray:
    """Expande velas 1h a 1m preservando OHLC (mismo criterio que el repo)."""
    out = []
    prev_close = None
    prev_ts = None
    for r in rows:
        ts = int(datetime.strptime(r['timestamp'], '%Y-%m-%dT%H:%M:%S').timestamp() * 1000)
        o, h, l, c, v = r['open'], r['high'], r['low'], r['close'], r['volume']
        vol_min = v / 60.0

        # Rellena huecos de horas faltantes con el último cierre conocido.
        if prev_ts is not None and ts > prev_ts + 3_600_000:
            t = prev_ts + 3_600_000
            while t < ts:
                out.append([t, prev_close, prev_close, prev_close, prev_close, 0.0])
                t += 60_000

        for minute in range(60):
            t = ts + minute * 60_000
            if minute == 0:
                m_open, m_close = o, o
            elif minute == 59:
                m_open, m_close = c, c
            else:
                m_open = o + (c - o) * (minute / 59.0)
                m_close = m_open
            out.append([t, m_open, h, l, m_close, vol_min])

        prev_close = c
        prev_ts = ts

    out.sort(key=lambda r: r[0])
    arr = np.array(out, dtype=np.float64)
    diffs = np.diff(arr[:, 0])
    if not np.all(diffs == 60_000):
        raise ValueError(f"Intervalos no uniformes (min={diffs.min()} max={diffs.max()})")
    return arr


def reset_symbol(symbol: str) -> None:
    """Borra las velas 1m de una moneda en la DB de Jesse."""
    from jesse.models import Candle
    q = Candle.delete().where(
        (Candle.exchange == EXCHANGE) & (Candle.symbol == symbol) & (Candle.timeframe == '1m')
    )
    n = q.execute()
    print(f"  🧹 {symbol}: {n} velas previas eliminadas")


def import_coin(coin: str, start_ts: int, end_ts: int, reset: bool = False) -> bool:
    symbol = f"{coin}-USDT"      # notación Jesse
    binance_symbol = f"{coin}USDT"  # notación Binance
    print(f"\n{'=' * 56}\n📥 {symbol}  ({datetime.fromtimestamp(start_ts/1000):%Y-%m-%d} → {datetime.fromtimestamp(end_ts/1000):%Y-%m-%d})\n{'=' * 56}")

    rows = download_klines(binance_symbol, start_ts, end_ts)
    if not rows:
        print("  ❌ Binance no devolvió datos")
        return False
    print(f"  📊 {len(rows)} velas 1h descargadas")

    arr = expand_1h_to_1m(rows)
    print(f"  🔄 {len(arr)} velas 1m generadas")

    if reset:
        reset_symbol(symbol)

    t0 = time.time()
    for i in range(0, len(arr), CHUNK_ROWS):
        chunk = arr[i:i + CHUNK_ROWS]
        store_candles(chunk, EXCHANGE, symbol)
        print(f"  💾 {min(i + CHUNK_ROWS, len(arr))}/{len(arr)} filas ({time.time() - t0:.1f}s)")
    print(f"  ✅ {symbol} guardado en Jesse DB")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description='Binance 1h → Jesse DB (1m)')
    ap.add_argument('--coins', required=True, help='BTC,ETH,... (o ALL para las 8)')
    ap.add_argument('--start', required=True, help='YYYY-MM-DD')
    ap.add_argument('--end', default=datetime.now().strftime('%Y-%m-%d'), help='YYYY-MM-DD (hoy por defecto)')
    ap.add_argument('--reset', action='store_true', help='borra las velas de la moneda antes de importar')
    args = ap.parse_args()

    coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC'] if args.coins.upper() == 'ALL' else \
        [c.strip().upper() for c in args.coins.split(',')]

    start_ts = int(datetime.strptime(args.start, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(args.end, '%Y-%m-%d').timestamp() * 1000)
    if end_ts <= start_ts:
        sys.exit("❌ --end debe ser posterior a --start")

    print(f"=== Jesse candle import ===\nMonedas: {coins}\nPeriodo: {args.start} → {args.end}")

    ok, fail = [], []
    for coin in coins:
        try:
            (ok if import_coin(coin, start_ts, end_ts, reset=args.reset) else fail).append(coin)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {coin}: {type(exc).__name__}: {exc}")
            fail.append(coin)

    print(f"\n=== Resumen ===\n  ✅ {ok}\n  ❌ {fail}")


if __name__ == '__main__':
    main()
