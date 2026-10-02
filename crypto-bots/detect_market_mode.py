#!/usr/bin/env python3
"""
detect_market_mode.py - Lógica de detección de modo de mercado
Compatibilidad total con crypto-bots/market-sentiment.sh

Uso:
  ./detect_market_mode.py

Salida estándar:
  MARKET_MODE=<MODE>
  MARKET_REASON=<REASON>
  TP1=<v>
  TP2=<v>
  TP3=<v>
  SL=<v>
  POSITION_SIZE=<v>
  TRAILING_STOP=<true|false>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "market-mode.conf"
STATE_FILE = SCRIPT_DIR / "state" / "last-market-mode.txt"

BINANCE_TICKER = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=50"
FEAR_GREED = "https://api.alternative.me/fng/"

REQUEST_TIMEOUT = 10


def fetch_text(url: str) -> Optional[str]:
    req = Request(url, headers={"User-Agent": "perrobotillo/1.0"})
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError) as exc:
        print(f"WARN: fetch failed {url}: {exc}", file=sys.stderr)
        return None


def get_ticker() -> dict:
    text = fetch_text(BINANCE_TICKER)
    if not text:
        raise RuntimeError("No se pudo obtener ticker de Binance")
    data = json.loads(text)
    return {
        "price": float(data["lastPrice"]),
        "change_pct": float(data["priceChangePercent"]),
        "volume": float(data["volume"]),
    }


def get_fear_greed() -> tuple[int, str]:
    text = fetch_text(FEAR_GREED)
    if not text:
        return 50, "Neutral"
    data = json.loads(text)
    try:
        value = int(data["data"][0]["value"])
        classification = str(data["data"][0]["value_classification"])
        return value, classification
    except (KeyError, IndexError, ValueError):
        return 50, "Neutral"


def get_klines() -> list[float]:
    text = fetch_text(BINANCE_KLINES)
    if not text:
        raise RuntimeError("No se pudo obtener klines de Binance")
    data = json.loads(text)
    return [float(k[4]) for k in data]


def ema(values: list[float], span: int) -> float:
    if not values:
        return 0.0
    if len(values) <= span:
        return sum(values) / len(values)
    k = 2.0 / (span + 1)
    ema_value = sum(values[:span]) / span
    for price in values[span:]:
        ema_value = (price * k) + (ema_value * (1.0 - k))
    return ema_value


def compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        change = curr - prev
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def detect_market_mode(price: float, ema20: float, ema50: float, fg: int, rsi: float) -> tuple[str, str]:
    if fg > 60 and price > ema20:
        return "BULL", "Fear & Greed > 60 + Precio > EMA20"
    if fg < 40 and price < ema20:
        return "BEAR", "Fear & Greed < 40 + Precio < EMA20"
    if price > ema20 and rsi >= 45 and fg < 50:
        return "LATERAL_BULL", "Precio > EMA20 + RSI >= 45 + Fear/Greed < 50"
    if rsi > 70:
        return "VOLATILE_BULL", "RSI > 70 (sobrecompra)"
    if rsi < 30:
        return "VOLATILE_BEAR", "RSI < 30 (sobreventa)"
    return "LATERAL", "RSI neutral, precio entre EMAs"


MODE_PARAMS = {
    "BULL": dict(TP1=3.0, TP2=6.0, TP3=10.0, SL=8.0, POSITION_SIZE=25, TRAILING_STOP="true"),
    "LATERAL_BULL": dict(TP1=3.0, TP2=6.0, TP3=9.0, SL=3.5, POSITION_SIZE=20, TRAILING_STOP="false"),
    "BEAR": dict(TP1=2.0, TP2=4.0, TP3=6.0, SL=4.0, POSITION_SIZE=15, TRAILING_STOP="false"),
    "VOLATILE_BULL": dict(TP1=3.5, TP2=7.0, TP3=12.0, SL=10.0, POSITION_SIZE=20, TRAILING_STOP="true"),
    "VOLATILE_BEAR": dict(TP1=2.0, TP2=4.0, TP3=6.0, SL=5.0, POSITION_SIZE=15, TRAILING_STOP="false"),
    "LATERAL": dict(TP1=2.5, TP2=5.0, TP3=7.0, SL=5.0, POSITION_SIZE=20, TRAILING_STOP="false"),
}


def read_last_mode() -> Optional[str]:
    if not STATE_FILE.exists():
        return None
    text = STATE_FILE.read_text(encoding="utf-8").strip()
    return text or None


def write_state(mode: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(f"{mode}\n", encoding="utf-8")


def format_conf(
    mode: str,
    reason: str,
    params: dict,
    btc_price: float,
    btc_change: float,
    fg_value: int,
    fg_class: str,
    ema20: float,
    ema50: float,
    rsi: float,
) -> str:
    now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Market Mode Configuration",
        f"# Generated: {now}",
        "",
        f'MARKET_MODE="{mode}"',
        f'MARKET_REASON="{reason}"',
        "",
        "# Trading Parameters",
        f"TP1={params['TP1']}",
        f"TP2={params['TP2']}",
        f"TP3={params['TP3']}",
        f"SL={params['SL']}",
        f"POSITION_SIZE={params['POSITION_SIZE']}",
        f"TRAILING_STOP={params['TRAILING_STOP']}",
        "",
        "# Market Data",
        f"BTC_PRICE={btc_price}",
        f"BTC_CHANGE={btc_change}",
        f"FG_VALUE={fg_value}",
        f'FG_CLASS="{fg_class}"',
        f"EMA20={ema20}",
        f"EMA50={ema50}",
        f"RSI={rsi}",
        "",
        "# Timestamp",
        f"LAST_UPDATE={int(__import__('time').time())}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        ticker = get_ticker()
        btc_price = ticker["price"]
        btc_change = ticker["change_pct"]

        fg_value, fg_class = get_fear_greed()

        closes = get_klines()
        ema20 = round(ema(closes, 20), 2)
        ema50 = round(ema(closes, 50), 2)
        rsi = round(compute_rsi(closes, 14), 2)

        mode, reason = detect_market_mode(btc_price, ema20, ema50, fg_value, rsi)
        params = MODE_PARAMS[mode]

        conf_text = format_conf(mode, reason, params, btc_price, btc_change, fg_value, fg_class, ema20, ema50, rsi)
        CONFIG_FILE.write_text(conf_text, encoding="utf-8")
        print(f"✅ Configuración guardada en: {CONFIG_FILE}")

        print(f"MARKET_MODE={mode}")
        print(f"MARKET_REASON={reason}")
        print(f"TP1={params['TP1']}")
        print(f"TP2={params['TP2']}")
        print(f"TP3={params['TP3']}")
        print(f"SL={params['SL']}")
        print(f"POSITION_SIZE={params['POSITION_SIZE']}")
        print(f"TRAILING_STOP={params['TRAILING_STOP']}")
        print(f"FG_VALUE={fg_value}")
        print(f"FG_CLASS={fg_class}")
        print(f"BTC_PRICE={btc_price}")
        print(f"EMA20={ema20}")
        print(f"EMA50={ema50}")
        print(f"RSI={rsi}")

        last_mode = read_last_mode()
        if last_mode and last_mode != mode:
            print(f"CAMBIO_MODO={last_mode} -> {mode}")

        write_state(mode)
        return 0
    except Exception as exc:
        print(f"❌ detect_market_mode.py failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
