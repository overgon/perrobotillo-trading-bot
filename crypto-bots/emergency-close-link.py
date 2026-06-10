#!/usr/bin/env python3
"""Emergency close para LINK Slot 2 - SL cruzado"""

import hmac
import hashlib
import time
import requests
import os

# Cargar credenciales
API_KEY = "VEXct8ZtvU7E27yrQ9PXHtn2q77LXvWda0KFMJ7SJjVSOPN1mlAVyhwLFa23kazY"
API_SECRET = "lN0ZASgSWFF6EUCrsnFK0MklraRPl58jqcUSxRuAjYQVGOsjd3BdJEFhkuuFdXof"

BASE_URL = "https://api.binance.com"

def generate_signature(query_string):
    return hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def get_account_balance():
    """Obtener balance de LINK"""
    timestamp = int(time.time() * 1000)
    query = f"timestamp={timestamp}&recvWindow=10000"
    signature = generate_signature(query)
    
    url = f"{BASE_URL}/api/v3/account?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    response = requests.get(url, headers=headers, timeout=5)
    data = response.json()
    
    for balance in data.get('balances', []):
        if balance['asset'] == 'LINK':
            free = float(balance['free'])
            locked = float(balance['locked'])
            return free + locked
    return 0

def cancel_open_orders(symbol):
    """Cancelar todas las órdenes abiertas"""
    timestamp = int(time.time() * 1000)
    query = f"symbol={symbol}&timestamp={timestamp}&recvWindow=10000"
    signature = generate_signature(query)
    
    url = f"{BASE_URL}/api/v3/openOrders?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    response = requests.delete(url, headers=headers, timeout=5)
    return response.json()

def sell_market(symbol, quantity):
    """Vender todo el LINK a mercado"""
    timestamp = int(time.time() * 1000)
    query = f"symbol={symbol}&side=SELL&type=MARKET&quantity={quantity}&timestamp={timestamp}&recvWindow=10000"
    signature = generate_signature(query)
    
    url = f"{BASE_URL}/api/v3/order?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    response = requests.post(url, headers=headers, timeout=5)
    return response.json()

def main():
    print("🚨 EMERGENCY CLOSE - LINK Slot 2")
    print("=" * 50)
    
    # Paso 1: Cancelar órdenes abiertas
    print("\n1️⃣ Cancelando órdenes abiertas...")
    cancel_result = cancel_open_orders("LINKUSDT")
    print(f"   Resultado: {len(cancel_result) if isinstance(cancel_result, list) else cancel_result}")
    
    # Paso 2: Obtener balance de LINK
    print("\n2️⃣ Obteniendo balance de LINK...")
    link_balance = get_account_balance()
    print(f"   Balance LINK: {link_balance}")
    
    if link_balance < 0.001:
        print("   ❌ No hay LINK tradeable")
        return
    
    # Paso 3: Vender todo a mercado (stepSize=0.01 para LINK, redondear hacia abajo)
    import math
    sell_qty = math.floor(link_balance * 100) / 100  # Redondear hacia abajo a 2 decimales
    print(f"\n3️⃣ Vendiendo {sell_qty} LINK a mercado...")
    sell_result = sell_market("LINKUSDT", sell_qty)
    print(f"   Resultado: {sell_result}")
    
    if 'executedQty' in sell_result:
        executed_qty = float(sell_result['executedQty'])
        total_price = float(sell_result.get('cummulativeQuoteQty', 0))
        avg_price = total_price / executed_qty if executed_qty > 0 else 0
        
        print("\n" + "=" * 50)
        print("✅ EMERGENCY CLOSE COMPLETADO")
        print(f"   Cantidad vendida: {executed_qty} LINK")
        print(f"   Precio promedio: ${avg_price:.4f}")
        print(f"   Total recibido: ${total_price:.2f} USDT")
        print("=" * 50)
    else:
        print(f"\n❌ Error en la venta: {sell_result}")

if __name__ == "__main__":
    main()
