#!/usr/bin/env python3
"""
Perrobotillo ML Feature: Token Audit Risk Gate
==============================================
Integra el token-audit skill del Binance Skill Hub como pre-trade safety check.

- Llama al token-audit endpoint directamente (curl-free vía requests)
- Cachea resultados por contrato (cache TTL: 60 min)
- Genera feature: `token_risk_score` (0-5, donde 4-5 = BLOCK)
- Genera feature: `token_risk_level` (LOW/MID/HIGH)
- Genera feature: `buy_tax`, `sell_tax`, `is_verified`

Uso:
  from ml.token_audit_gate import check_token_audit
  result = check_token_audit("BNB", "0x...")
  if result['risk_level_num'] >= 4:
      print("🚨 BLOCK: token has HIGH risk")
      return

NOTA: Este wrapper es read-only. No ejecuta trades.
"""
import os
import json
import time
import uuid
import hashlib

# Usa urllib (stdlib) para evitar dependencias externas
import urllib.request
import urllib.error

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# Cache: /tmp/token_audit_cache.json (TTL: 60 min)
CACHE_FILE = "/tmp/token_audit_cache.json"
CACHE_TTL_SECONDS = 3600  # 60 minutos

# Risk threshold mapping (del SKILL.md)
# riskLevel 0-1 = LOW, 2-3 = MID, 4 = HIGH (avoid), 5 = HIGH (block)
RISK_BLOCK_THRESHOLD = 4  # riskLevel >= 4 → BLOCK trade

# Config: token symbol → known contract addresses (BSC)
# NOTA: Perrobotillo tradea monedas nativas (BTC, ETH, BNB, SOL) en Binance spot.
# Para token audit, necesitamos contratos BEP20 equivalentes o wrappers:
# - BNB → WBNB (0xbb4CdB9CaDfC9826868725c8d890007515fcD9b9) — nativo en BSC
# - ETH → ETH nativo en BSC (no aplica) — usar ETH-BSC puente si existe
# - BTC → BTCB (0x7130d2a116e8c3768a8b848738b7a7e134c980f5) — BTCB es el BTC wrap en BSC
# - SOL, LINK, XRP, AVAX → tokens BEP20 bridged en BSC
TOKEN_CONTRACTS = {
    "BNB": "0xbb4CdB9CaDfC9826868725c8d890007515fcD9b9",  # WBNB — nativo BSC
    "BTC": "0x7130d2a116e8c3768a8b848725a6e9e6e134c980f5",  # BTCB — BTC wrapped en BSC
    "ETH": "0x55d398326f99059ff775485246999027b3197955",  # test token con datos reales
    "SOL": "0x570a5d26f7763df6fb65273bc8db1f51c6cb6f4c",  # SOL wrapped en BSC
    "LINK": "0x70e4d21a2fcaa975af5a385775b4e88555d60626",  # LINK en BSC
    "XRP": "0x1ab60b307e40c4d7fe9cc66df5c25ee15cb898c2",  # XRP en BSC
    "AVAX": "0x1ba7dde3616c83b8e0b2d751c8a6e1c788a76ad5",  # AVAX en BSC
    "ZEC": "0x1ba42e5193dfa8b03d15dd1b86a3113bbbef8eeb",  # ZEC (Binance-Peg) en BSC
}

# Config: chain mapping per coin (BSC = 56 es default para spot Binance)
# Para Perrobotillo, todas las monedas son nativas o tokens en BSC
CHAIN_ID = "56"  # BSC (Binance Smart Chain)


def fetch_token_audit(contract_address: str, chain_id: str = CHAIN_ID) -> dict:
    """
    Llama al endpoint de token audit directamente.

    URL: https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit

    Args:
        contract_address: Dirección del contrato del token
        chain_id: BSC="56", Base="8453", Solana="CT_501", Ethereum="1"

    Returns:
        dict con: risk_level_enum, risk_level_int, buy_tax, sell_tax,
                  is_verified, risk_items, is_supported, has_result
    """
    if not contract_address or not contract_address.startswith("0x"):
        return {"error": "invalid_contract", "has_result": False, "is_supported": False}

    url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"
    payload = json.dumps({
        "binanceChainId": chain_id,
        "contractAddress": contract_address,
        "requestId": str(uuid.uuid4()),
    })

    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "source": "agent",
            "Accept-Encoding": "identity",
            "User-Agent": "binance-web3/1.4 (Skill)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP error {e.code} for {contract_address[:12]}...")
        return {"error": f"http_{e.code}", "has_result": False}
    except Exception as e:
        print(f"❌ Audit fetch error: {e}")
        return {"error": str(e), "has_result": False}


def cache_audit(contract_address: str, audit_data: dict) -> None:
    """Guarda resultado de audit en cache."""
    cache_key = hashlib.md5(contract_address.lower().encode()).hexdigest()

    try:
        # Load existing cache
        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)

        cache[cache_key] = {
            "timestamp": time.time(),
            "contract_address": contract_address,
            "data": audit_data,
        }

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️ Cache write error: {e}")


def load_cached_audit(contract_address: str) -> dict:
    """Carga audit desde cache si es reciente (≤60 min)."""
    cache_key = hashlib.md5(contract_address.lower().encode()).hexdigest()

    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        entry = cache.get(cache_key)
        if not entry:
            return None

        age = time.time() - entry.get("timestamp", 0)
        if age > CACHE_TTL_SECONDS:
            return None

        print(f"   📦 Usando cache de token audit (age={age:.0f}s)")
        return entry.get("data", {}).get("data")
    except Exception:
        return None


def parse_audit_response(response: dict) -> dict:
    """
    Parsea la respuesta del audit endpoint.

    Response example:
    {
      "code": "000000",
      "data": {
        "hasResult": true,
        "isSupported": true,
        "riskLevelEnum": "MID",
        "riskLevel": 3,
        "extraInfo": {"buyTax": "0", "sellTax": "0", "isVerified": true},
        "riskItems": [...]
      }
    }
    """
    if not response or response.get("code") != "000000":
        return {"error": response.get("error", "api_error"), "has_result": False}

    data = response.get("data", {})
    has_result = data.get("hasResult", False)
    is_supported = data.get("isSupported", False)

    if not has_result or not is_supported:
        return {
            "has_result": has_result,
            "is_supported": is_supported,
            "risk_level_enum": "UNKNOWN",
            "risk_level_num": 0,
            "buy_tax": 0,
            "sell_tax": 0,
            "is_verified": None,
            "block_trade": False,
            "risk_items": [],
        }

    risk_level_enum = data.get("riskLevelEnum", "UNKNOWN")
    risk_level_num = data.get("riskLevel", 0)

    extra_info = data.get("extraInfo", {})
    buy_tax = float(extra_info.get("buyTax") or 0)
    sell_tax = float(extra_info.get("sellTax") or 0)
    is_verified = extra_info.get("isVerified")

    risk_items = data.get("riskItems", [])
    # Extract any HIT risks (isHit=True)
    hit_risks = []
    for item in risk_items:
        details = item.get("details", [])
        for d in details:
            if d.get("isHit"):
                hit_risks.append({
                    "title": d.get("title"),
                    "description": d.get("description"),
                    "risk_type": d.get("riskType"),
                })

    # BLOCK trade if riskLevel >= 4 (HIGH)
    block_trade = risk_level_num >= RISK_BLOCK_THRESHOLD

    return {
        "has_result": True,
        "is_supported": True,
        "risk_level_enum": risk_level_enum,
        "risk_level_num": risk_level_num,
        "buy_tax": buy_tax,
        "sell_tax": sell_tax,
        "is_verified": is_verified,
        "block_trade": block_trade,
        "risk_items": hit_risks,
    }


def check_token_audit(symbol: str, contract_address: str = None, force_refresh: bool = False) -> dict:
    """
    Chequea riesgo de token antes de trade.

    Args:
        symbol: "BNB", "ETH", "LINK", etc.
        contract_address: Dirección del contrato (si es None, usa TOKEN_CONTRACTS)
        force_refresh: Forzar refresco de cache

    Returns:
        {
            'has_result': bool,
            'is_supported': bool,
            'risk_level_enum': 'LOW'|'MID'|'HIGH'|'UNKNOWN',
            'risk_level_num': int,
            'buy_tax': float,
            'sell_tax': float,
            'is_verified': bool|None,
            'block_trade': bool,
            'risk_items': list,
            'symbol': str,
        }
    """
    symbol_upper = symbol.upper()

    # Si no se provee contrato, usar el mapeo conocido
    if not contract_address:
        contract_address = TOKEN_CONTRACTS.get(symbol_upper)
        if not contract_address:
            return {
                "symbol": symbol,
                "error": "no_contract_address",
                "has_result": False,
                "is_supported": False,
                "block_trade": False,
                "risk_level_enum": "UNKNOWN",
                "risk_level_num": 0,
            }

    # Cache logic
    audit_response = None
    if not force_refresh:
        audit_response = load_cached_audit(contract_address)

    if audit_response is None:
        print(f"   🔄 Refrescando token audit para {symbol} ({contract_address[:12]}...) en chain {CHAIN_ID}...")
        response = fetch_token_audit(contract_address, CHAIN_ID)

        # Cache the full response
        cache_audit(contract_address, response)

        parsed = parse_audit_response(response)
    else:
        parsed = parse_audit_response({"code": "000000", "data": audit_response})

    parsed["symbol"] = symbol
    parsed["contract_address"] = contract_address[:12] + "..." if contract_address else None

    if parsed.get("block_trade"):
        print(f"   🚨 BLOCK: {symbol} tiene riesgo HIGH (level {parsed['risk_level_num']})")
    elif parsed.get("is_supported") and parsed.get("has_result"):
        print(f"   ✅ OK: {symbol} riesgo {parsed['risk_level_enum']} (level {parsed['risk_level_num']}) "
              f"tax={parsed['buy_tax']}/{parsed['sell_tax']}% verified={parsed['is_verified']}")
    else:
        print(f"   ℹ️ Sin datos de audit para {symbol}")

    return parsed


# === CLI para test/manual run ===
if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ETH"
    contract = sys.argv[2] if len(sys.argv) > 2 else None
    force = "--refresh" in sys.argv

    print(f"=== Token Audit Gate — {symbol} ===")
    result = check_token_audit(symbol, contract, force_refresh=force)
    print(f"\nResult for {symbol}:")
    print(json.dumps(result, indent=2, default=str))
