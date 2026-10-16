#!/usr/bin/env python3
"""
Perrobotillo ML Feature: Smart Money Signal Integration
========================================================
Integra on-chain smart money signals del Binance Skill Hub como feature ML.

- Llama al trading-signal skill para BSC (chainId 56)
- Cachea resultados en /tmp/smart_money_signals.json (actualización: 15 min)
- Genera feature: `smart_money_signal` (1 buy, -1 sell, 0 neutral)
- Genera feature: `smart_money_score` = maxGain * (100 - exitRate) / 100

Uso:
  from ml.smart_money_signal import get_smart_money_features
  features = get_smart_money_features("BNB")
  # {'smart_money_signal': 1, 'smart_money_score': 12.36, 'confidence_boost': 5}

NOTA: Este wrapper es read-only. No ejecuta trades.
"""
import os
import json
import time
import uuid
import hashlib
import subprocess
from datetime import datetime, timezone

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(WORKSPACE, ".agents", "skills")
CACHE_FILE = "/tmp/smart_money_signals_cache.json"
CACHE_TTL_SECONDS = 900  # 15 minutos

# Configuración por moneda (chain + symbol mapping)
CHAIN_CONFIG = {
    "BTC": {"chainId": "56", "symbol": "BTC"},
    "ETH": {"chainId": "56", "symbol": "ETH"},
    "BNB": {"chainId": "56", "symbol": "BNB"},
    "SOL": {"chainId": "56", "symbol": "SOL"},
    "LINK": {"chainId": "56", "symbol": "LINK"},
    "XRP": {"chainId": "56", "symbol": "XRP"},
    "AVAX": {"chainId": "56", "symbol": "AVAX"},
    "ZEC": {"chainId": "56", "symbol": "ZEC"},
}


def fetch_smart_money_signals(chain_id: str = "56", page_size: int = 100) -> list:
    """
    Llama al trading-signal skill y retorna signals raw.
    Usa npx skills call o node cli.mjs directamente.
    """
    cli_path = os.path.join(SKILL_DIR, "trading-signal", "scripts", "cli.mjs")
    payload = json.dumps({"chainId": chain_id, "page": 1, "pageSize": page_size})

    try:
        result = subprocess.run(
            ["node", cli_path, "smart-money", payload],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE,
        )
        if result.returncode != 0:
            print(f"⚠️ trading-signal skill error: {result.stderr.strip()}")
            return []

        data = json.loads(result.stdout.strip())
        return data.get("data", []) if data.get("code") == "000000" else []
    except Exception as e:
        print(f"❌ Error fetching smart money signals: {e}")
        return []


def cache_signals(signals: list) -> None:
    """Guarda signals en cache con timestamp."""
    cache_data = {
        "timestamp": time.time(),
        "data": signals,
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Cache write error: {e}")


def load_cached_signals() -> list:
    """Carga signals desde cache si son frescos (≤15 min)."""
    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            cache_data = json.load(f)

        age = time.time() - cache_data.get("timestamp", 0)
        if age > CACHE_TTL_SECONDS:
            return None

        print(f"   📦 Usando cache de smart money (age={age:.0f}s)")
        return cache_data.get("data", [])
    except Exception:
        return None


def find_signals_for_coin(signals: list, symbol: str) -> list:
    """
    Filtra signals para el token/coin solicitado.
    - Coin side: match por ticker o symbol (BTC, ETH, etc.)
    - Token side: los signals vienen de tokens BSC, no stablecoins tradicionales.
    - Para BTC/ETH/BNB: usamos tokens wrap (WBNB, WETH, WBTC) o matches exactos.
    """
    matches = []
    symbol_upper = symbol.upper()

    # Mapeo común: BTC→WBTC, ETH→WETH, BNB→BNB/WBNB, SOL→SOL, etc.
    aliases = {
        "BTC": ["BTC", "WBTC", "BTCB"],
        "ETH": ["ETH", "WETH"],
        "BNB": ["BNB", "WBNB", "CAKE"],
        "SOL": ["SOL"],
        "LINK": ["LINK", "LINKB"],
        "XRP": ["XRP"],
        "AVAX": ["AVAX"],
    }

    target_tickers = set([symbol_upper] + aliases.get(symbol_upper, []))

    for sig in signals:
        ticker = sig.get("ticker", "").upper()
        # Normaliza: quita emojis/símbolos raros
        clean_ticker = "".join(c for c in ticker if c.isalnum())
        if clean_ticker in target_tickers:
            matches.append(sig)

    return matches


def calculate_smart_money_features(signals: list) -> dict:
    """
    Calcula features de smart money para Perrobotillo ML.
    
    Returns:
        {
            'smart_money_signal': 1 (buy) / -1 (sell) / 0 (neutral),
            'smart_money_score': float (maxGain * (100 - exitRate) / 100),
            'confidence_boost': int (extra ML confidence en %, max 5%),
            'smart_money_count': int (número de wallets),
        }
    """
    if not signals:
        return {
            "smart_money_signal": 0,
            "smart_money_score": 0.0,
            "confidence_boost": 0,
            "smart_money_count": 0,
        }

    # Usar el signal más fuerte (mayor smartMoneyCount)
    best_signal = max(signals, key=lambda x: x.get("smartMoneyCount", 0))

    direction = best_signal.get("direction", "buy")
    smart_money_count = best_signal.get("smartMoneyCount", 0)
    exit_rate = float(best_signal.get("exitRate", 0))
    max_gain = float(best_signal.get("maxGain", 0))  # ya es un ratio (0.3698 = 36.98%)
    status = best_signal.get("status", "timeout")

    # Signal: solo activo si status == "valid"
    if status not in ("active", "valid"):
        signal_dir = 0
    elif direction == "buy":
        signal_dir = 1
    else:
        signal_dir = -1

    # Score: maxGain (ratio) * (100 - exitRate) / 100
    # Ejemplo: maxGain=0.3698 (36.98%), exitRate=88 → score = 0.3698 * 12 = 4.44
    smart_money_score = round(max_gain * (100 - exit_rate) / 100, 2)

    # Confidence boost: solo si hay suficientes whales y bajo exit rate
    # smartMoneyCount >= 5 AND exitRate < 70 → boost 5%
    # smartMoneyCount >= 3 AND exitRate < 80 → boost 3%
    # else → 0
    if smart_money_count >= 5 and exit_rate < 70 and signal_dir != 0:
        confidence_boost = 5
    elif smart_money_count >= 3 and exit_rate < 80 and signal_dir != 0:
        confidence_boost = 3
    else:
        confidence_boost = 0

    return {
        "smart_money_signal": signal_dir,
        "smart_money_score": smart_money_score,
        "confidence_boost": confidence_boost,
        "smart_money_count": smart_money_count,
        "exit_rate": exit_rate,
        "max_gain": max_gain,
        "signal_status": status,
    }


def get_smart_money_features(symbol: str, chain_id: str = None, force_refresh: bool = False) -> dict:
    """
    Obtiene features de smart money para un coin symbol.

    Args:
        symbol: "BTC", "ETH", "BNB", etc.
        chain_id: "56" (BSC) por defecto
        force_refresh: Forzar refresco de cache (bypass 15-min TTL)

    Returns:
        Features dict para integración ML
    """
    config = CHAIN_CONFIG.get(symbol.upper())
    if not config:
        print(f"⚠️ No chain config for {symbol}")
        return {
            "smart_money_signal": 0,
            "smart_money_score": 0.0,
            "confidence_boost": 0,
            "smart_money_count": 0,
        }

    chain = chain_id or config["chainId"]

    # Cache logic
    signals = None if force_refresh else load_cached_signals()
    if signals is None:
        print(f"   🔄 Refrescando smart money signals para {symbol} (chain {chain})...")
        signals = fetch_smart_money_signals(chain_id=chain)
        cache_signals(signals)
        if not signals:
            print(f"   ❌ No signals found")
            return {
                "smart_money_signal": 0,
                "smart_money_score": 0.0,
                "confidence_boost": 0,
                "smart_money_count": 0,
            }

    # Filtrar para el coin solicitado
    coin_signals = find_signals_for_coin(signals, symbol)

    if not coin_signals:
        print(f"   ℹ️ No smart money signals para {symbol} en este batch")
        return {
            "smart_money_signal": 0,
            "smart_money_score": 0.0,
            "confidence_boost": 0,
            "smart_money_count": 0,
        }

    features = calculate_smart_money_features(coin_signals)
    print(f"   📈 {symbol}: signal={features['smart_money_signal']} "
          f"score={features['smart_money_score']} "
          f"whales={features['smart_money_count']} "
          f"exit_rate={features['exit_rate']}% "
          f"boost={features['confidence_boost']}%")

    return features


# === CLI para test/manual run ===
if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BNB"
    force = "--refresh" in sys.argv

    print(f"=== Smart Money Signal Fetcher — {symbol} ===")
    features = get_smart_money_features(symbol, force_refresh=force)

    print(f"\nResults for {symbol}:")
    print(json.dumps(features, indent=2))
