#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime
from pathlib import Path
import tempfile

WORKSPACE = Path(os.environ.get("WORKSPACE", "/home/overgon/.openclaw/workspace"))
HISTORY_FILE = WORKSPACE / "crypto-bots" / "trade-history.json"

def main():
    if len(sys.argv) < 7:
        print("Usage: log_trade_to_history.py <slot_id> <close_type> <entry> <exit> <qty> <pnl> [order_id] [source] [reason]", file=sys.stderr)
        sys.exit(1)

    slot_id = sys.argv[1]
    close_type = sys.argv[2]
    entry = float(sys.argv[3])
    exit_ = float(sys.argv[4])
    qty = float(sys.argv[5])
    pnl = float(sys.argv[6])
    order_id = sys.argv[7] if len(sys.argv) > 7 else ""
    source = sys.argv[8] if len(sys.argv) > 8 else "BOT"
    reason = sys.argv[9] if len(sys.argv) > 9 else ""

    if not HISTORY_FILE.exists():
        print(f"⚠️ HISTORY_FILE no existe: {HISTORY_FILE}", file=sys.stderr)
        sys.exit(0)

    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)

    trades = data.get("trades", [])
    next_id = max((t.get("id", 0) for t in trades), default=0) + 1

    dup_key = f"{close_type}|{slot_id}|{close_type}|{datetime.now().strftime('%Y-%m-%dT%H:%M')}"
    existing = sum(
        1 for t in trades
        if t.get("symbol") == os.environ.get("SYMBOL")
        and t.get("slotId") == int(slot_id)
        and t.get("closeType") == close_type
        and (t.get("timestamp", "")[:16] == datetime.now().strftime('%Y-%m-%dT%H:%M'))
    )
    if existing > 0 and close_type != "MANUAL_CLOSE_ZOMBIE":
        print(f"  ⚠️ Trade DUPLICADO por clave minuto exacta - NO guardar")
        sys.exit(0)

    timestamp = datetime.now().isoformat()
    close_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    wins = sum(1 for t in trades if (t.get("pnlUSDT") or 0) > 0)
    losses = sum(1 for t in trades if (t.get("pnlUSDT") or 0) <= 0)
    profit = sum(t.get("pnlUSDT", 0) or 0 for t in trades if (t.get("pnlUSDT") or 0) > 0)
    loss = sum(t.get("pnlUSDT", 0) or 0 for t in trades if (t.get("pnlUSDT") or 0) <= 0)
    net = (data.get("netPnLUSDT") or 0) + pnl
    win_rate = (wins / len(trades) * 100) if trades else 0

    new_trade = {
        "id": next_id,
        "symbol": os.environ.get("SYMBOL"),
        "slotId": int(slot_id),
        "type": "LONG",
        "entryPrice": entry,
        "exitPrice": exit_,
        "quantity": qty,
        "closeType": close_type,
        "pnlUSDT": pnl,
        "timestamp": timestamp,
        "closeTime": close_time,
        "source": source,
        "orderId": order_id if order_id else None,
        "reason": reason if reason else None,
    }

    if pnl > 0:
        wins += 1
        profit += pnl
    else:
        losses += 1
        loss += pnl

    total = len(trades) + 1
    win_rate = (wins / total * 100) if total > 0 else 0

    data["trades"].insert(0, new_trade)
    data["totalTrades"] = total
    data["totalWins"] = wins
    data["totalLosses"] = losses
    data["totalProfitUSDT"] = round(profit, 8)
    data["totalLossUSDT"] = round(loss, 8)
    data["netPnLUSDT"] = round(net, 8)
    data["winRate"] = round(win_rate, 2)
    data["updatedAt"] = datetime.now().isoformat()

    symbol_key = os.environ.get("SYMBOL")
    day_key = datetime.now().strftime('%Y-%m-%d')
    by_symbol = data.get("bySymbol", {})
    by_day = data.get("byDay", {})

    sym = by_symbol.get(symbol_key, {"trades": 0, "wins": 0, "netPnL": 0})
    sym["trades"] = sym.get("trades", 0) + 1
    if pnl > 0:
        sym["wins"] = sym.get("wins", 0) + 1
    sym["netPnL"] = round((sym.get("netPnL", 0) or 0) + pnl, 8)
    by_symbol[symbol_key] = sym

    day = by_day.get(day_key, {"trades": 0, "wins": 0, "netPnL": 0})
    day["trades"] = day.get("trades", 0) + 1
    if pnl > 0:
        day["wins"] = day.get("wins", 0) + 1
    day["netPnL"] = round((day.get("netPnL", 0) or 0) + pnl, 8)
    by_day[day_key] = day

    data["bySymbol"] = by_symbol
    data["byDay"] = by_day

    temp_file = HISTORY_FILE.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp_file.replace(HISTORY_FILE)

    print(f"  📜 Trade logged to history: #{next_id} {os.environ.get('SYMBOL')} {close_type} PnL=${pnl:+.2f} source={source} orderId={order_id or 'n/a'}")

if __name__ == "__main__":
    main()
