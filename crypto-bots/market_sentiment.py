#!/usr/bin/env python3
"""
market_sentiment.py - Market Sentiment Analyzer (Python 3.11)

Mismo comportamiento que crypto-bots/market-sentiment.sh:
- Obtiene datos de Binance y Fear & Greed
- Calcula EMA20/EMA50, RSI(14)
- Determina modo: BULL / BEAR / VOLATILE_BULL / VOLATILE_BEAR / LATERAL
- Genera market-mode.conf compatible con la versión Bash original
- Emite alerta de cambio de modo (sin reenviar por Telegram)
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


# ════════════════════════════════════════════════════════
# Config
# ════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "market-mode.conf"
STATE_FILE = SCRIPT_DIR / "state" / "last-market-mode.txt"

BINANCE_TICKER = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=50"
FEAR_GREED = "https://api.alternative.me/fng/"

REQUEST_TIMEOUT = 10


# ════════════════════════════════════════════════════════
# HTTP helpers
# ════════════════════════════════════════════════════════
def fetch_text(url: str) -> Optional[str]:
    req = Request(url, headers={"User-Agent": "perrobotillo/1.0"})
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError) as exc:
        print(f"❌ Error fetching {url}: {exc}")
        return None


# ════════════════════════════════════════════════════════
# Market data
# ════════════════════════════════════════════════════════
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


# ════════════════════════════════════════════════════════
# Market mode rules (equivalente a Bash)
# ════════════════════════════════════════════════════════
def detect_market_mode(price: float, ema20: float, ema50: float, fg: int, rsi: float) -> tuple[str, str]:
    if fg > 60 and price > ema20:
        return "BULL", "Fear & Greed > 60 + Precio > EMA20"
    if fg < 40 and price < ema20:
        return "BEAR", "Fear & Greed < 40 + Precio < EMA20"
    if rsi > 70:
        return "VOLATILE_BULL", "RSI > 70 (sobrecompra)"
    if rsi < 30:
        return "VOLATILE_BEAR", "RSI < 30 (sobreventa)"
    return "LATERAL", "RSI neutral, precio entre EMAs"


# ════════════════════════════════════════════════════════
# IO helpers
# ════════════════════════════════════════════════════════
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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
        f"LAST_UPDATE={int(datetime.now(timezone.utc).timestamp())}",
        "",
    ]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════
# Output compatibility helpers
# ════════════════════════════════════════════════════════
def quote(text: str) -> str:
    return str(text).replace('"', '\\"')


def display_summary(
    mode: str,
    params: dict,
    btc_price: float,
    btc_change: float,
    fg_value: int,
    fg_class: str,
    ema20: float,
    ema50: float,
    rsi: float,
) -> None:
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  📊 MARKET SENTIMENT ANALYZER                         ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print("")
    print("📊 DATOS DEL MERCADO:")
    print(f"   Precio BTC: ${btc_price}")
    print(f"   24h Change: {btc_change}%")
    print(f"   Fear & Greed: {fg_value} ({fg_class})")
    print(f"   EMA20: ${ema20}")
    print(f"   EMA50: ${ema50}")
    print(f"   RSI: {rsi}")
    print("")
    print("🔍 Analizando modo de mercado...")
    print("")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🎯 CONFIGURACIÓN APLICADA                            ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print("")
    print(f"   Modo: {mode}")
    print("")
    print(f"   TP1: +{params['TP1']}%")
    print(f"   TP2: +{params['TP2']}%")
    print(f"   TP3: +{params['TP3']}%")
    print(f"   SL: -{params['SL']}%")
    print(f"   Position Size: {params['POSITION_SIZE']}%")
    print(f"   Trailing Stop: {params['TRAILING_STOP']}")
    print("")
    print("✅ Market sentiment analysis completed")


# ════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════
def main() -> int:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  📊 MARKET SENTIMENT ANALYZER                         ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print("")
    print("⏳ Obteniendo datos del mercado...")

    ticker = get_ticker()
    btc_price = ticker["price"]
    btc_change = ticker["change_pct"]

    print("   📊 Obteniendo Fear & Greed Index...")
    fg_value, fg_class = get_fear_greed()
    print(f"   ✅ F&G: {fg_value} ({fg_class})")

    print("   Calculando EMAs...")
    closes = get_klines()
    ema20 = round(ema(closes, 20), 2)
    ema50 = round(ema(closes, 50), 2)
    print(f"   ✅ EMA20: {ema20} | EMA50: {ema50}")

    print("   Calculando RSI...")
    rsi = round(compute_rsi(closes, 14), 2)
    print(f"   ✅ RSI: {rsi}")

    print("")
    print("🔍 Analizando modo de mercado...")
    mode, reason = detect_market_mode(btc_price, ema20, ema50, fg_value, rsi)
    print(f"   🎯 MODO DETECTADO: {mode}")
    print(f"   📝 Razón: {reason}")
    print("")

    params = MODE_PARAMS[mode]
    conf_text = format_conf(mode, reason, params, btc_price, btc_change, fg_value, fg_class, ema20, ema50, rsi)
    CONFIG_FILE.write_text(conf_text, encoding="utf-8")
    print(f"✅ Configuración guardada en: {CONFIG_FILE}")
    print("")

    display_summary(mode, params, btc_price, btc_change, fg_value, fg_class, ema20, ema50, rsi)

    last_mode = read_last_mode()
    if last_mode and last_mode != mode and last_mode:
        print("")
        print(f"⚠️  CAMBIO DE MODO DETECTADO: {last_mode} → {mode}")

    write_state(mode)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ market_sentiment.py failed: {exc}")
        raise SystemExit(1)
