#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# RECONCILIACIÓN BINANCE ↔ STATE - Perrobotillo Trading Bot
# ════════════════════════════════════════════════════════
# Compara posiciones abiertas en Binance con estado local
# Detecta slots "zombie" y los auto-fixea
# ════════════════════════════════════════════════════════

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Config
WORKSPACE = Path("/home/overgon/.openclaw/workspace")
STATE_DIR = WORKSPACE / "crypto-bots"
LOG_FILE = WORKSPACE / "logs" / "reconciliation.log"
BINANCE_ENV = Path("/home/overgon/.openclaw/secrets/binance.env")

# Telegram config
TELEGRAM_CHAT_ID = "7543955537"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

def load_binance_credentials():
    """Carga API credentials de binance.env"""
    if not BINANCE_ENV.exists():
        print(f"❌ No se encontró {BINANCE_ENV}")
        return None, None
    
    creds = {}
    with open(BINANCE_ENV) as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                creds[key] = val
    
    return creds.get("BINANCE_API_KEY"), creds.get("BINANCE_API_SECRET")

def get_binance_positions(api_key, api_secret):
    """Obtiene posiciones abiertas de Binance API"""
    try:
        import hmac
        import hashlib
        import time
        import urllib.parse
        import requests
        
        base_url = "https://api.binance.com"
        endpoint = "/api/v3/openOrders"
        
        timestamp = int(time.time() * 1000)
        recv = 60000
        params = f"timestamp={timestamp}&recvWindow={recv}"
        
        signature = hmac.new(
            api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        url = f"{base_url}{endpoint}?{params}&signature={signature}"
        
        headers = {
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Error Binance API: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error conectando a Binance: {e}")
        return None

def get_binance_balances(api_key, api_secret):
    """Obtiene balances reales desde /account para detectar posición"""
    try:
        import hmac
        import hashlib
        import time
        import requests

        base_url = "https://api.binance.com"
        endpoint = "/api/v3/account"

        timestamp = int(time.time() * 1000)
        params = f"timestamp={timestamp}"

        signature = hmac.new(
            api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        url = f"{base_url}{endpoint}?{params}&signature={signature}"
        headers = {
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Error balances Binance: {response.status_code} - {response.text[:200]}")
            return {}
        data = response.json()
        balances = {}
        for item in data.get("balances", []):
            asset = item.get("asset")
            free = float(item.get("free", 0))
            locked = float(item.get("locked", 0))
            if free > 0 or locked > 0:
                balances[asset] = free + locked
        return balances

    except Exception as e:
        print(f"⚠️ Error leyendo balances: {e}")
        return {}


def load_local_state(coin):
    """Carga estado local de un slot"""
    state_file = STATE_DIR / f"{coin}-trade-state.json"
    if not state_file.exists():
        return None
    
    with open(state_file) as f:
        return json.load(f)

def save_local_state(coin, data):
    """Guarda estado local actualizado"""
    state_file = STATE_DIR / f"{coin}-trade-state.json"
    with open(state_file, "w") as f:
        json.dump(data, f, indent=4)

def send_telegram_alert(message):
    """Envía alerta a Telegram"""
    try:
        token_file = WORKSPACE / "secrets" / "telegram.bot.token"
        if not token_file.exists():
            return
        
        with open(token_file) as f:
            bot_token = f.read().strip()
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        print(f"⚠️ Error enviando Telegram: {e}")

def reconcile():
    """Función principal de reconciliación"""
    print(f"═══════════════════════════════════════════════════════")
    print(f"RECONCILIACIÓN BINANCE ↔ STATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"═══════════════════════════════════════════════════════\n")
    
    # Cargar credentials
    api_key, api_secret = load_binance_credentials()
    if not api_key or not api_secret:
        print("❌ No se pudo cargar credentials de Binance")
        return
    
    # Cargar balances reales desde /account
    balances_by_coin = {"btc": {}, "eth": {}, "bnb": {}, "sol": {}, "link": {}, "xrp": {}, "avax": {}}
    try:
        account_balances = get_binance_balances(api_key, api_secret)
        if account_balances:
            coin_lower_map = {
                "BTCUSDT": "btc",
                "ETHUSDT": "eth",
                "BNBUSDT": "bnb",
                "SOLUSDT": "sol",
                "LINKUSDT": "link",
                "XRPUSDT": "xrp",
                "AVAXUSDT": "avax",
            }
            for symbol, coin_lower in coin_lower_map.items():
                balances_by_coin[coin_lower] = {"coin": symbol.replace("USDT", ""), "balance": account_balances.get(symbol.replace("USDT", ""), 0)}
    except Exception as e:
        print(f"⚠️ No se pudieron cargar balances para reconciliación: {e}")
    
    # Obtener posiciones de Binance
    binance_orders = get_binance_positions(api_key, api_secret)
    if binance_orders is None:
        print("❌ No se pudo obtener datos de Binance")
        return
    
    # Agrupar órdenes por símbolo
    binance_by_symbol = {}
    for order in binance_orders:
        symbol = order["symbol"]
        if symbol not in binance_by_symbol:
            binance_by_symbol[symbol] = []
        binance_by_symbol[symbol].append(order)
    
    # Mapear símbolos de Binance (ej: BTCUSDT) a nuestras monedas
    symbol_to_coin = {
        "BTCUSDT": "BTC",
        "ETHUSDT": "ETH",
        "BNBUSDT": "BNB",
        "SOLUSDT": "SOL",
        "LINKUSDT": "LINK",
        "XRPUSDT": "XRP",
        "AVAXUSDT": "AVAX"
    }
    
    findings = []
    fixes_applied = []
    
    for coin in COINS:
        print(f"🪙 {coin}:")
        
        # Cargar estado local
        local_state = load_local_state(coin)
        if not local_state:
            print(f"   ⚠️ No hay estado local para {coin}")
            continue
        
        # Verificar slots activos
        active_slots = [s for s in local_state.get("slots", []) if s.get("status") == "ACTIVE"]
        
        # Obtener símbolo de Binance
        binance_symbol = f"{coin}USDT"
        binance_orders_for_coin = binance_by_symbol.get(binance_symbol, [])
        
        print(f"   Slots activos (local): {len(active_slots)}")
        print(f"   Órdenes abiertas (Binance): {len(binance_orders_for_coin)}")
        
        # Detectar inconsistencias
        if len(active_slots) > 0 and len(binance_orders_for_coin) == 0:
            # Nunca auto-cerrar un slot ACTIVE: solo reportar
            local_balance = float(balances_by_coin.get(coin, {}).get(coin.lower(), 0))
            finding = {
                "coin": coin,
                "type": "ACTIVE_NO_OPEN_ORDERS",
                "active_slots": len(active_slots),
                "binance_orders": 0,
                "slots": [s["slotId"] for s in active_slots],
                "balance": local_balance,
                "note": "NO_AUTO_FIX"
            }
            findings.append(finding)
        elif len(active_slots) == 0 and len(binance_orders_for_coin) > 0:
            # ⚠️ FANTASMA: Órdenes en Binance pero sin slots activos
            print(f"   👻 FANTASMA DETECTADO: {len(binance_orders_for_coin)} órdenes en Binance sin slots locales")
            
            finding = {
                "coin": coin,
                "type": "GHOST_ORDERS",
                "active_slots": 0,
                "binance_orders": len(binance_orders_for_coin),
                "order_ids": [o["orderId"] for o in binance_orders_for_coin]
            }
            findings.append(finding)
            
        elif len(active_slots) != len(binance_orders_for_coin):
            # ⚠️ MISMATCH: Cantidad diferente
            print(f"   ⚠️ MISMATCH: {len(active_slots)} slots vs {len(binance_orders_for_coin)} órdenes")
            
            finding = {
                "coin": coin,
                "type": "MISMATCH_COUNT",
                "active_slots": len(active_slots),
                "binance_orders": len(binance_orders_for_coin)
            }
            findings.append(finding)
        
        else:
            print(f"   ✅ OK - Consistente")
        
        print()
    
    # Reporte final
    print(f"═══════════════════════════════════════════════════════")
    print(f"RESUMEN")
    print(f"═══════════════════════════════════════════════════════")
    print(f"Findings: {len(findings)}")
    print(f"Fixes aplicados: {len(fixes_applied)}")
    
    if findings:
        print(f"\n📊 FINDINGS:")
        for f in findings:
            if f["type"] == "ZOMBIE_SLOTS":
                print(f"   🚨 {f['coin']}: {f['active_slots']} zombie slots → AUTO-FIXED")
            elif f["type"] == "GHOST_ORDERS":
                print(f"   👻 {f['coin']}: {f['binance_orders']} ghost orders (requiere revisión manual)")
            else:
                print(f"   ⚠️ {f['coin']}: {f['type']}")
    
    if fixes_applied:
        print(f"\n🔧 FIXES APLICADOS:\n")
        for fix in fixes_applied:
            print(f"   ✅ {fix['coin']} Slots {fix.get('slotIds', [])}: {fix['action']}")
    
    # Enviar alerta Telegram si hubo zombies
    zombie_count = sum(1 for f in findings if f["type"] == "ZOMBIE_SLOTS")
    if zombie_count > 0:
        alert_msg = f"🚨 RECONCILIACIÓN - Zombies Detectados\n"
        alert_msg += f"{zombie_count} monedas con slots zombie | Auto-fix: {len(fixes_applied)} reseteados a READY\n"
        alert_msg += f"Revisá el log para más detalles 🐕"
        
        print(f"\n📤 Enviando alerta Telegram...")
        send_telegram_alert(alert_msg)
        print(f"✅ Alerta enviada!")
    
    print(f"\n═══════════════════════════════════════════════════════")
    print(f"RECONCILIACIÓN COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"═══════════════════════════════════════════════════════")

if __name__ == "__main__":
    reconcile()
