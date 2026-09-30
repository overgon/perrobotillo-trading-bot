#!/usr/bin/env python3
"""
🔄 SYNC BALANCES WITH BINANCE
Sincroniza los trade-state files con los balances reales de Binance
"""

import hmac
import hashlib
import time
import requests
import json
import os
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS = Path("/home/overgon/.openclaw/secrets")

# Cargar credenciales
def load_secrets():
    secrets_file = SECRETS / "binance.env"
    creds = {}
    with open(secrets_file) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                creds[key] = value
    return creds

creds = load_secrets()
API_KEY = creds.get('BINANCE_API_KEY', '')
API_SECRET = creds.get('BINANCE_API_SECRET', '')

BASE_URL = "https://api.binance.com"

def generate_signature(query_string):
    return hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def get_account_balances():
    """Obtener todos los balances de Binance (solo > 0)"""
    timestamp = int(time.time() * 1000)
    query = f"timestamp={timestamp}&recvWindow=10000"
    signature = generate_signature(query)
    
    url = f"{BASE_URL}/api/v3/account?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    response = requests.get(url, headers=headers, timeout=10)
    data = response.json()
    
    if 'balances' not in data:
        print(f"❌ Error: {data}")
        return {}
    
    balances = {}
    for bal in data['balances']:
        free = float(bal['free'])
        locked = float(bal['locked'])
        total = free + locked
        if total > 0.00000001:  # Solo balances significativos
            balances[bal['asset']] = {
                'free': free,
                'locked': locked,
                'total': total
            }
    
    return balances

def sync_trade_state(coin, api_balance):
    """Sincronizar trade-state file con balance real"""
    state_file = WORKSPACE / "crypto-bots" / f"{coin}-trade-state.json"
    
    if not state_file.exists():
        print(f"  ⚠️  {coin}: No state file")
        return None
    
    with open(state_file) as f:
        state = json.load(f)
    
    # Actualizar usdtBalance con el balance real de USDT
    if coin == "USDT":
        return api_balance
    
    # Para coins, verificar si hay discrepancia
    active_qty = sum(slot.get('quantity', 0) or 0 
                     for slot in state['slots'] 
                     if slot.get('status') == 'ACTIVE')
    
    closed_slots = [slot for slot in state['slots'] if slot.get('status') in ['CLOSED', 'CLOSED_SYNC']]
    
    # El balance debería ser: dust de slots cerrados + remanentes de TP parcial
    file_balance = active_qty  # Simplificado: solo slots activos
    
    diff = api_balance - file_balance
    
    if abs(diff) > 0.0001:
        print(f"  📊 {coin}: API={api_balance:.8f}, File={file_balance:.8f}, Diff={diff:+.8f}")
        
        # Agregar nota de sync
        if 'syncHistory' not in state:
            state['syncHistory'] = []
        
        state['syncHistory'].append({
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'action': 'BALANCE_SYNC',
            'apiBalance': api_balance,
            'fileBalance': file_balance,
            'difference': diff,
            'reason': 'TP_PARTIAL_FILLS_OR_DUST'
        })
        
        # Actualizar lastUpdated
        from datetime import datetime, timezone
        state['lastUpdated'] = datetime.now(timezone.utc).astimezone().isoformat()
        
        # Guardar cambios
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        return diff
    
    print(f"  ✅ {coin}: Sincronizado")
    return None

def main():
    print("🔄 SYNC BALANCES WITH BINANCE")
    print("=" * 60)
    
    # Obtener balances reales
    print("\n📡 Obteniendo balances de Binance...")
    balances = get_account_balances()
    
    if not balances:
        print("❌ No se pudieron obtener balances")
        return
    
    # Coins del bot
    COINS = ["BTC", "ETH", "SOL", "ZEC", "XRP", "BNB", "AVAX"]
    
    print("\n🔍 Sincronizando trade-states...")
    discrepancies = {}
    
    for coin in COINS:
        if coin in balances:
            diff = sync_trade_state(coin, balances[coin]['total'])
            if diff is not None and abs(diff) > 0.0001:
                discrepancies[coin] = diff
        else:
            print(f"  ⚪ {coin}: Sin balance en Binance")
    
    # USDT especial
    if 'USDT' in balances:
        print(f"\n💰 USDT Balance: ${balances['USDT']['total']:.2f}")
    
    # Reporte final
    print("\n" + "=" * 60)
    if discrepancies:
        print("⚠️  DISCREPANCIAS ENCONTRADAS:")
        for coin, diff in discrepancies.items():
            print(f"   {coin}: {diff:+.8f}")
        print("\n📝 Estas discrepancias son normales por:")
        print("   • TP partial fills (ventas parciales)")
        print("   • Dust no tradeable")
        print("   • Comisiones pagadas en BNB")
        print("   • Emergency closes incompletos")
    else:
        print("✅ Todos los balances sincronizados")
    
    print("\n📊 Balances actuales en Binance:")
    for coin in COINS:
        if coin in balances:
            print(f"   {coin}: {balances[coin]['total']:.8f}")

if __name__ == "__main__":
    main()
