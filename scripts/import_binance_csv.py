#!/usr/bin/env python3
"""
Importa el historial de transacciones Spot de Binance (CSV de exportación)
y lo fusiona en crypto-bots/trade-history.json, que es lo que lee el dashboard
en la sección 📈 RECENT TRADES HISTORY.

Uso:
    python3 scripts/import_binance_csv.py <archivo.csv> [mas.csv ...]
    python3 scripts/import_binance_csv.py --dir <carpeta>

Qué hace:
  - Parsea fills (órdenes agrupadas por 'Número de orden').
  - Empareja compras/ventas por moneda con FIFO → trades de ida y vuelta.
  - Convierte comisiones a USDT (BNB vía BNBUSDT del propio CSV, activo base
    vía el precio del trade, USDT 1:1).
  - Fusiona con trade-history.json preservando los trades del bot
    (source != 'BINANCE_IMPORT') y renumerando ids.
  - No borra nada: respalda el archivo antes de escribir.

Convención de tiempo: el CSV de Binance trae la hora local (CST, UTC-6);
se conserva igual que los timestamps que escribe el bot.
"""
import csv
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE", "/home/overgon/.openclaw/workspace"))
HISTORY_FILE = WORKSPACE / "crypto-bots" / "trade-history.json"
REPORT_FILE = WORKSPACE / "crypto-bots" / "binance-import-report.json"
IMPORT_SOURCE = "BINANCE_IMPORT"

AMOUNT_RE = re.compile(r'^\s*([\d.]+)\s*(\w+)\s*$')


def parse_amount(s):
    m = AMOUNT_RE.match(s or '')
    if not m:
        return 0.0, None
    return float(m.group(1)), m.group(2)


def parse_csv(path):
    """Devuelve lista de fills con tipos limpios."""
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    fills = []
    for i, r in enumerate(rows):
        qty, base = parse_amount(r.get('Ejecutado', ''))
        quote, qasset = parse_amount(r.get('Cantidad', ''))
        fee, feeasset = parse_amount(r.get('Tarifa', ''))
        price = float(r.get('Precio', 0) or 0)
        side = (r.get('Lado') or '').strip().upper()
        pair = (r.get('Par') or '').strip()
        if not qty or not quote or side not in ('BUY', 'SELL'):
            continue
        fills.append({
            'idx': i,
            'order': (r.get('Número de orden') or '').strip(),
            'time': (r.get('Hora') or '').strip(),
            'ts': datetime.strptime(r['Hora'].strip(), '%Y-%m-%d %H:%M:%S'),
            'pair': pair,
            'symbol': pair.replace('USDT', ''),
            'side': side,
            'price': price,
            'qty': qty,
            'quote': quote,
            'fee': fee,
            'feeasset': feeasset,
        })
    return fills


def aggregate_orders(fills):
    """Agrupa fills por orden (una orden puede tener varios fills parciales)."""
    byorder = {}
    for f in fills:
        key = (f['order'], f['pair'], f['side'])
        o = byorder.get(key)
        if o is None:
            o = {
                'order': f['order'], 'pair': f['pair'], 'symbol': f['symbol'],
                'side': f['side'], 'qty': 0.0, 'quote': 0.0, 'fee': 0.0,
                'feeasset': f['feeasset'], 'ts': f['ts'], 'minidx': f['idx'],
            }
            byorder[key] = o
        o['qty'] += f['qty']
        o['quote'] += f['quote']
        o['fee'] += f['fee']
        o['ts'] = min(o['ts'], f['ts'])
        o['minidx'] = min(o['minidx'], f['idx'])
    orders = sorted(byorder.values(), key=lambda o: (o['ts'], o['minidx']))
    for o in orders:
        o['time'] = o['ts'].strftime('%Y-%m-%d %H:%M:%S')
        o['price'] = o['quote'] / o['qty'] if o['qty'] else 0.0
    return orders


def build_price_series(orders):
    """Serie de precios por activo (vs USDT) para convertir comisiones."""
    series = defaultdict(list)
    for o in orders:
        if o['symbol'] and o['qty']:
            series[o['symbol']].append((o['ts'], o['quote'] / o['qty']))
    for sym in series:
        series[sym].sort()
    return series


def price_at(series, symbol, ts, fallback=None):
    pts = series.get(symbol)
    if not pts:
        return fallback
    best = None
    for t, p in pts:
        if t <= ts:
            best = p
        else:
            break
    if best is None:
        best = pts[0][1]
    return best


def match_trades(orders, series):
    """FIFO por moneda. Devuelve (trades, open_lots, unmatched_sells)."""
    lots = defaultdict(list)
    trades = []
    open_lots = defaultdict(list)
    unmatched_sells = []

    for o in orders:
        fee_usdt = 0.0
        if o['fee'] > 0 and o['feeasset']:
            if o['feeasset'] == 'USDT':
                fee_usdt = o['fee']
            elif o['feeasset'] == o['symbol']:
                fee_usdt = o['fee'] * o['price']
            else:
                p = price_at(series, o['feeasset'], o['ts'])
                fee_usdt = o['fee'] * p if p else 0.0
        fee_unit = fee_usdt / o['qty'] if o['qty'] else 0.0

        if o['side'] == 'BUY':
            lots[o['symbol']].append({
                'qty': o['qty'], 'price': o['price'], 'fee_unit': fee_unit,
                'time': o['time'], 'ts': o['ts'], 'order': o['order'],
            })
            continue

        remaining = o['qty']
        sym = o['symbol']
        while remaining > 1e-12 and lots[sym]:
            lot = lots[sym][0]
            take = min(lot['qty'], remaining)
            pnl = (o['price'] - lot['price']) * take - (lot['fee_unit'] + fee_unit) * take
            trades.append({
                'symbol': sym,
                'type': 'LONG',
                'quantity': round(take, 8),
                'entryPrice': round(lot['price'], 8),
                'exitPrice': round(o['price'], 8),
                'pnlUSDT': round(pnl, 4),
                'feeUSDT': round((lot['fee_unit'] + fee_unit) * take, 6),
                'entryTime': lot['time'],
                'exitTime': o['time'],
                'entryOrder': lot['order'],
                'exitOrder': o['order'],
            })
            lot['qty'] -= take
            remaining -= take
            if lot['qty'] <= 1e-12:
                lots[sym].pop(0)
        if remaining > 1e-9:
            unmatched_sells.append({
                'symbol': sym, 'qty': round(remaining, 8), 'time': o['time'],
                'price': round(o['price'], 8), 'order': o['order'],
            })

    for sym, ls in lots.items():
        ls[:] = [l for l in ls if l['qty'] > 1e-12]
        if ls:
            open_lots[sym] = ls
    return trades, open_lots, unmatched_sells


def to_history_trades(matched):
    out = []
    for t in matched:
        out.append({
            'symbol': t['symbol'],
            'coin': t['symbol'],
            'slotId': None,
            'type': 'LONG',
            'entryPrice': t['entryPrice'],
            'exitPrice': t['exitPrice'],
            'quantity': t['quantity'],
            'closeType': 'BINANCE',
            'pnlUSDT': t['pnlUSDT'],
            'pnl': t['pnlUSDT'],
            'timestamp': t['exitTime'].replace(' ', 'T'),
            'closeTime': t['exitTime'],
            'source': IMPORT_SOURCE,
            'orderId': t['exitOrder'],
            'reason': None,
            'entryTime': t['entryTime'],
            'entryOrder': t['entryOrder'],
            'feeUSDT': t['feeUSDT'],
        })
    return out


def compute_aggregates(trades):
    wins = sum(1 for t in trades if (t.get('pnlUSDT') or 0) > 0)
    losses = sum(1 for t in trades if (t.get('pnlUSDT') or 0) <= 0)
    profit = sum(t.get('pnlUSDT', 0) or 0 for t in trades if (t.get('pnlUSDT') or 0) > 0)
    loss = sum(t.get('pnlUSDT', 0) or 0 for t in trades if (t.get('pnlUSDT') or 0) <= 0)
    by_symbol = {}
    by_day = {}
    for t in trades:
        sym = t.get('symbol') or 'UNKNOWN'
        s = by_symbol.setdefault(sym, {'trades': 0, 'wins': 0, 'netPnL': 0.0})
        s['trades'] += 1
        if (t.get('pnlUSDT') or 0) > 0:
            s['wins'] += 1
        s['netPnL'] = round(s['netPnL'] + (t.get('pnlUSDT') or 0), 4)
        day = (t.get('closeTime') or t.get('timestamp') or '')[:10]
        d = by_day.setdefault(day, {'trades': 0, 'wins': 0, 'netPnL': 0.0})
        d['trades'] += 1
        if (t.get('pnlUSDT') or 0) > 0:
            d['wins'] += 1
        d['netPnL'] = round(d['netPnL'] + (t.get('pnlUSDT') or 0), 4)
    return {
        'totalTrades': len(trades),
        'totalWins': wins,
        'totalLosses': losses,
        'totalProfitUSDT': round(profit, 4),
        'totalLossUSDT': round(loss, 4),
        'netPnLUSDT': round(sum(t.get('pnlUSDT', 0) or 0 for t in trades), 4),
        'winRate': round((wins / len(trades) * 100) if trades else 0, 2),
        'bySymbol': by_symbol,
        'byDay': by_day,
    }


def main():
    args = sys.argv[1:]
    paths = []
    if args and args[0] == '--dir':
        folder = Path(args[1])
        paths = sorted(folder.glob('*.csv'))
    else:
        paths = [Path(a) for a in args]

    if not paths:
        print("Uso: import_binance_csv.py <archivo.csv> [...] | --dir <carpeta>", file=sys.stderr)
        sys.exit(1)

    all_fills = []
    for p in paths:
        if not p.exists():
            print(f"⚠️  No existe: {p}", file=sys.stderr)
            continue
        fills = parse_csv(p)
        print(f"📄 {p.name}: {len(fills)} fills")
        all_fills.extend(fills)
    if not all_fills:
        print("❌ No se leyeron fills", file=sys.stderr)
        sys.exit(1)

    orders = aggregate_orders(all_fills)
    series = build_price_series(orders)
    matched, open_lots, unmatched = match_trades(orders, series)
    imported = to_history_trades(matched)
    print(f"🔁 Órdenes agrupadas: {len(orders)} | Trades FIFO: {len(imported)}")
    print(f"♻️  Ventas sin compra previa (posiciones preexistentes): {len(unmatched)}")
    for sym, ls in open_lots.items():
        qty = sum(l['qty'] for l in ls)
        print(f"📌 Abierto {sym}: {len(ls)} lotes, qty={qty:.6f}")

    # Fusionar con lo que ya haya (preservando trades del bot)
    kept = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                prev = json.load(f)
            kept = [t for t in prev.get('trades', []) if t.get('source') != IMPORT_SOURCE]
            print(f"🧩 Trades no-importados preservados: {len(kept)}")
        except Exception as e:
            print(f"⚠️  No se pudo leer {HISTORY_FILE}: {e}", file=sys.stderr)

    merged = kept + imported
    # IDs crecientes en orden cronológico: el trade más reciente queda con el
    # ID más alto (igual que hace el bot con next_id = max(id)+1).
    merged.sort(key=lambda t: (t.get('closeTime') or t.get('timestamp') or ''))
    for i, t in enumerate(merged, start=1):
        t['id'] = i
    # Se guarda del más nuevo al más antiguo, como inserta el bot (índice 0).
    merged.reverse()

    data = compute_aggregates(merged)
    data['trades'] = merged
    data['updatedAt'] = datetime.now().isoformat()
    data['import'] = {
        'source': IMPORT_SOURCE,
        'files': [p.name for p in paths],
        'importedTrades': len(imported),
        'firstFill': min(f['time'] for f in all_fills),
        'lastFill': max(f['time'] for f in all_fills),
    }

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        backup = HISTORY_FILE.with_name(
            f"trade-history.json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(HISTORY_FILE, backup)
        print(f"💾 Respaldo: {backup.name}")

    tmp = HISTORY_FILE.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(HISTORY_FILE)

    with open(REPORT_FILE, 'w') as f:
        json.dump({
            'generatedAt': datetime.now().isoformat(),
            'files': [p.name for p in paths],
            'fills': len(all_fills),
            'orders': len(orders),
            'matchedTrades': len(imported),
            'unmatchedSells': unmatched,
            'openPositions': {
                sym: {'lots': len(ls), 'qty': round(sum(l['qty'] for l in ls), 8),
                      'avgCost': round(sum(l['qty'] * l['price'] for l in ls) /
                                        max(sum(l['qty'] for l in ls), 1e-12), 4),
                      'firstBuy': ls[0]['time'], 'lastBuy': ls[-1]['time']}
                for sym, ls in open_lots.items()
            },
            'netPnLUSDT': data['netPnLUSDT'],
            'winRate': data['winRate'],
        }, f, indent=2)

    print(f"✅ {HISTORY_FILE}")
    print(f"   trades={data['totalTrades']} wins={data['totalWins']} "
          f"losses={data['totalLosses']} netPnL={data['netPnLUSDT']:.2f} USDT "
          f"winRate={data['winRate']}%")


if __name__ == '__main__':
    main()
