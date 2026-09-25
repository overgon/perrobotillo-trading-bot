#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime
from pathlib import Path
import tempfile

WORKSPACE = Path(os.environ.get("WORKSPACE", "/home/overgon/.openclaw/workspace"))
HISTORY_FILE = WORKSPACE / "crypto-bots" / "trade-history.json"
COIN_CONFIG_FILE = WORKSPACE / "crypto-bots" / "per-coin-config.env"

# 🔧 FIX: REMOVED hardcoded SLOT_TO_COIN that was WRONG - each coin uses
# its own slots 1-3, not global slots 1-21. Now using SYMBOL env var
# (resolved by the bash script before calling this Python script).
# SLOT_TO_COIN mapping is now ONLY used as a last-resort fallback via
# _resolve_symbol_from_slot() when SYMBOL env is empty AND entryPrice
# doesn't definitively match a coin.
SLOT_TO_COIN = {
    1: 'BTC', 2: 'BTC', 3: 'BTC',
    4: 'ETH', 5: 'ETH', 6: 'ETH',
    7: 'BNB', 8: 'BNB', 9: 'BNB',
    10: 'SOL', 11: 'SOL', 12: 'SOL',
    13: 'LINK', 14: 'LINK', 15: 'LINK',
    16: 'XRP', 17: 'XRP', 18: 'XRP',
    19: 'AVAX', 20: 'AVAX', 21: 'AVAX',
}

# 🔧 FIX: Per-coin slot assignment — each coin has its own slots 1-3
# This is read from <SYMBOL>-trade-state.json which has slotId 1-3 per coin
# We don't use SLOT_TO_COIN for resolution anymore, only SYMBOL env + entryPrice

def _resolve_symbol_from_slot(slot_id, workspace=WORKSPACE):
    """🔧 Derive coin symbol from slotId as fallback when SYMBOL env is empty.
    
    Reads per-coin-config.env for symbol override, falls back to SLOT_TO_COIN map.
    This prevents symbol: null in trade-history.json.
    """
    try:
        sid = int(slot_id)
        # Intentar leer symbol del per-coin-config.env
        from configparser import ConfigParser
        config = ConfigParser()
        config.read(str(workspace / "crypto-bots" / "per-coin-config.env"))
        # per-coin-config.env usa formato KEY=VALUE, no INI estándar
        # Leerlo como archivo plano
        coin_config_path = workspace / "crypto-bots" / "per-coin-config.env"
        if coin_config_path.exists():
            with open(coin_config_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        key = key.strip()
                        val = val.strip()
                        # Buscar claves como BTC_SYMBOL or COIN_BTC
                        if key.endswith(f'_{sid}') or key.endswith('_symbol'):
                            # Extraer coin del slotId
                            coin = SLOT_TO_COIN.get(sid)
                            if coin and f"{coin}_SYMBOL" == key:
                                return val
        # Fallback: usar mapeo directo slotId → coin
        return SLOT_TO_COIN.get(sid, f"UNKNOWN_{sid}")
    except Exception:
        # Último recurso: usar mapeo memoria
        try:
            return SLOT_TO_COIN.get(int(slot_id), "UNKNOWN")
        except Exception:
            return "UNKNOWN"

def _resolve_symbol_from_price(entry_price, slot_id=None, symbol_env=None):
    """🔧 FIX ROOT CAUSE: validate symbol from entryPrice when env var conflicts.
    
    Bot sometimes passes wrong SYMBOL env (BTC) for altcoin closes.
    Use entryPrice ranges to identify the real coin.
    Returns the coin with highest confidence, or None if ambiguous.
    
    When slot_id is provided, use it to disambiguate overlapping price ranges.
    When price is ambiguous, fall back to symbol_env (resolved by bash script)
    instead of hardcoded SLOT_TO_COIN (which is WRONG — each coin uses slots 1-3).
    """
    # 🔧 FIX (2026-09-25): AVAX and LINK trade in overlapping ranges (both $5-30).
    # Previous narrow ranges (AVAX:4-8, LINK:8-30) caused AVAX at $10.48 to be
    # misidentified as LINK. Widen both to (4.0, 30.0). Trust symbol_env
    # (authoritative from bash cron invocation) when price is plausible for it.
    # Only override symbol_env when price is wildly outside its range.
    PRICE_RANGES = {
        "BTC": (20000, 120000),
        "ETH": (800, 8000),
        "BNB": (200, 1000),
        "SOL": (40, 500),
        "AVAX": (4.0, 30.0),  # 🔧 widened from (4.0, 8.0) — AVAX trades $7-13+ in practice
        "LINK": (4.0, 30.0),  # 🔧 widened from (8.0, 30.0) — overlaps with AVAX by design
        "XRP": (0.2, 5.0),
    }
    KNOWN_COINS = set(PRICE_RANGES.keys())
    # If symbol_env is a known coin and price is plausible for it -> trust it.
    # symbol_env is authoritative: bash knows which coin it's processing.
    if symbol_env and symbol_env in KNOWN_COINS:
        env_lo, env_hi = PRICE_RANGES[symbol_env]
        if env_lo <= entry_price <= env_hi:
            return symbol_env  # Price plausible for the env symbol -> trust it
    # Price outside symbol_env's range OR symbol_env unknown -> use price-based candidates
    candidates = []
    for coin, (lo, hi) in PRICE_RANGES.items():
        if lo <= entry_price <= hi:
            candidates.append(coin)
    if len(candidates) == 1:
        return candidates[0]
    # Ambiguous (e.g. price falls in multiple ranges) — try symbol_env first
    if len(candidates) > 1:
        if symbol_env and symbol_env in candidates:
            return symbol_env
    # If price doesn't match any known range, or ambiguous with stale symbol_env
    # fall back to slot_id resolution
    if slot_id is not None:
        resolved = _resolve_symbol_from_slot(slot_id, WORKSPACE)
        if resolved and resolved != "UNKNOWN":
            return resolved
    return None

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
    # 🔧 FIX: symbol MUST be resolved BEFORE deduplication + by_symbol keys
    # (prevents None key corrupting JSON → silent write failure → missing trades)
    symbol = os.environ.get("SYMBOL")
    if symbol:
        # 🔧 FIX: normalize SYMBOL env var — strip USDT suffix (e.g. BNBUSDT → BNB)
        if symbol.endswith("USDT"):
            symbol = symbol.replace("USDT", "")
    if not symbol:
        symbol = _resolve_symbol_from_slot(slot_id, WORKSPACE)
    # 🔧 FIX ROOT CAUSE: validate symbol against entryPrice — bot sometimes passes
    # wrong SYMBOL env (BTC) for other coins. entryPrice ~$11.5 = LINK, not BTC.
    # Pass slot_id + symbol_env to disambiguate: price ranges first, then
    # symbol_env (resolved by bash) second, then slot_id last resort
    symbol_from_price = _resolve_symbol_from_price(entry, slot_id, symbol)
    if symbol_from_price and symbol_from_price != symbol:
        print(f"  ⚠️ SYMBOL mismatch: env='{symbol}' slot={_resolve_symbol_from_slot(slot_id, WORKSPACE)} price=${entry} → confiable: {symbol_from_price}")
        symbol = symbol_from_price
    # 🆕 If _resolve_symbol_from_price returned None (ambiguous but symbol_env valid),
    # keep the symbol_env value — it was resolved by bash script using same logic
    # This handles the case where entryPrice $11.5 matches both AVAX and LINK ranges,
    # but SYMBOL env already correctly says LINK

    # ✅ Now check duplicates with resolved symbol
    existing = sum(
        1 for t in trades
        if t.get("symbol") == symbol
        and t.get("slotId") == int(slot_id)
        and t.get("closeType") == close_type
        and (t.get("timestamp", "")[:16] == datetime.now().strftime('%Y-%m-%dT%H:%M'))
    )
    if existing > 0 and close_type != "MANUAL_CLOSE_ZOMBIE":
        # 🔧 FIX: allow same slotId same minute for DIFFERENT slots — only block
        # exact same (symbol+slotId+closeType+minute) duplicates
        print(f"  ⚠️ Trade DUPLICADO exacto (slotId={slot_id}) - NO guardar")
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
        "symbol": symbol,
        "coin": symbol,  # 🔧 FIX: frontend needs coin field (was NULL)
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

    # ✅ DEDUP: Skip if exact duplicate (same symbol+slot+closeTime+pnl)
    # Also match on minute-level timestamp to catch race conditions
    # where bot and log_trade_to_history fire within the same second
    # but with slightly different millisecond precision (e.g. #437 vs #438)
    close_time_str = str(new_trade.get("closeTime", ""))
    minute_key_close = close_time_str[:16] if close_time_str else ""  # "2026-08-24 22:35"
    
    dedup_key = f"{new_trade.get('symbol','?')}:{new_trade.get('slotId','?')}:{close_time_str}:{new_trade.get('pnlUSDT',0)}"
    existing = [t for t in trades if (
        t.get("symbol") == new_trade.get("symbol") and
        t.get("slotId") == new_trade.get("slotId") and
        str(t.get("closeTime", "")) == close_time_str and
        float(t.get("pnlUSDT", 0) or 0) == float(new_trade.get("pnlUSDT", 0) or 0)
    )]
    # Also check minute-level + same exitPrice + same pnl (race condition guard)
    if not existing and minute_key_close:
        existing = [t for t in trades if (
            t.get("symbol") == new_trade.get("symbol") and
            t.get("slotId") == new_trade.get("slotId") and
            str(t.get("closeTime", ""))[:16] == minute_key_close and
            float(t.get("pnlUSDT", 0) or 0) == float(new_trade.get("pnlUSDT", 0) or 0) and
            float(t.get("exitPrice", 0) or 0) == float(new_trade.get("exitPrice", 0) or 0)
        )]
    if existing:
        print(f"  ⏭️  DEDUP_SKIP: Trade already exists (key={dedup_key[:60]})")
        return
    data["trades"].insert(0, new_trade)
    # 🔧 FIX ROOT CAUSE: totalTrades MUST match len(trades) — race conditions
    # and concurrent writes could desync the counter. Derive from array length.
    actual_trades = len(data["trades"])
    data["totalTrades"] = actual_trades
    data["totalWins"] = wins
    data["totalLosses"] = losses
    data["totalProfitUSDT"] = round(profit, 8)
    data["totalLossUSDT"] = round(loss, 8)
    data["netPnLUSDT"] = round(net, 8)
    data["winRate"] = round(win_rate, 2)
    data["updatedAt"] = datetime.now().isoformat()
    # Consistency guard: detect if totalTrades was previously desynced
    prev_total = actual_trades - 1  # before this insert
    if prev_total != data.get("totalTrades", 0) and "totalTrades" in data:
        print(f"  🔧 Consistency fix: totalTrades was {data.get('totalTrades')}, recalculating from trades array ({actual_trades})")

    # ✅ FIX: Use resolved symbol (not raw env var) for by_symbol aggregation
    # Previously used os.environ.get("SYMBOL") which could be stale/wrong (e.g. BTC for LINK trades)
    # The resolved `symbol` variable already has price-based correction applied
    symbol_key = symbol
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

    # Escritura atomica con retry y backup de seguridad
    temp_file = HISTORY_FILE.with_suffix('.tmp')
    write_success = False
    for attempt in range(1, 4):  # intentos 1,2,3
        try:
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(HISTORY_FILE)
            # Verificar que se escribió correctamente
            with open(HISTORY_FILE) as vf:
                json.load(vf)  # raises si corrupto
            write_success = True
            break
        except Exception as write_err:
            print(f"  ⚠️ Write failed (attempt {attempt}/3): {write_err}")
    if not write_success:
        # Último recurso: escribir directamente + backup
        backup = HISTORY_FILE.with_suffix('.bak')
        if HISTORY_FILE.exists():
            HISTORY_FILE.replace(backup)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  ⚠️ Escritura de emergencia completada (backup en {backup})")

    print(f"  📜 Trade logged to history: #{next_id} {symbol} {close_type} PnL=${pnl:+.2f} source={source} orderId={order_id or 'n/a'}")

    # 🔧 FIX: notify Telegram for forced/manual trades
    # Bot runtime normally publishes TRADE_CLOSED to Redis; this fires notify.sh
    # so manual closes via log_trade_to_history.py also produce notifications
    try:
        import subprocess
        notify_script = WORKSPACE / "scripts" / "notify_trade.sh"
        if notify_script.exists():
            subprocess.Popen([
                "bash", str(notify_script),
                str(symbol),
                str(close_type),
                str(pnl),
                str(next_id),
                str(entry),
                str(exit_)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"  ⚠️ notify_trade.sh dispatch failed: {e}")

if __name__ == "__main__":
    main()
