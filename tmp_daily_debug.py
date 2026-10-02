import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
CRYPTO_BOTS_DIR = WORKSPACE / "crypto-bots"
LOGS_DIR = WORKSPACE / "logs"
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

history_file = CRYPTO_BOTS_DIR / "trade-history.json"
if history_file.exists():
    with open(history_file) as f:
        data = json.load(f)
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recent = []
    for t in data.get("trades", []):
        ts = t.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt >= cutoff:
            recent.append(t)

    from collections import defaultdict
    pnl_by_coin = defaultdict(float)
    for t in recent:
        coin = t.get("symbol")
        if coin in COINS:
            pnl = t.get("pnlUSDT", 0) or 0
            pnl_by_coin[coin] += pnl

    print("=== P&L 24H POR MONEDA (desde history) ===")
    for coin in COINS:
        print(f"{coin}: ${pnl_by_coin[coin]:+.2f}")
    print(f"Total: ${sum(pnl_by_coin.values()):+.2f}")
    print(f"Trades últimas 24h: {len(recent)}")
else:
    print("No history file")

print("\n=== TRADES DE AYER ===")
yesterday = datetime.now() - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")
trades_yesterday = []
for coin in COINS:
    log_file = LOGS_DIR / f"trade-{coin}.log"
    if log_file.exists():
        with open(log_file, "r") as f:
            for line in f:
                if yesterday_str in line:
                    if any(x in line for x in ["TP", "SL", "cerrado", "Trade logged"]):
                        trades_yesterday.append(f"{coin}: {line.strip()}")

print(f"Trades ayer: {len(trades_yesterday)}")
for t in trades_yesterday[-10:]:
    print(t)
