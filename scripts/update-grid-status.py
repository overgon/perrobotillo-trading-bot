#!/usr/bin/env python3
# ════════════════════════════════════════════
# 🐕 GRID STATUS UPDATER - ACTUALIZA DASHBOARD
# ════════════════════════════════════════════
# Actualiza grid-status.json con datos EN TIEMPO REAL desde Binance
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════

import ccxt
import json
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
DASHBOARD = WORKSPACE / "dashboard"
GRID_STATUS_FILE = DASHBOARD / "grid-status.json"
SECRETS = Path("/home/overgon/.openclaw/secrets/binance.env")
CONFIG_FILE = WORKSPACE / "crypto-bots" / "grid-trading-bot.py"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

def load_binance_credentials():
    """Cargar credenciales de Binance"""
    creds = {}
    if SECRETS.exists():
        with open(SECRETS) as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    creds[key] = val
    return creds

def get_grid_ranges():
    """Obtener rangos configurados del grid-trading-bot.py"""
    ranges = {}
    
    if not CONFIG_FILE.exists():
        return ranges
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
        
        for coin in COINS:
            # Buscar low_price y high_price para cada moneda (primera ocurrencia)
            low_match = re.search(f'"{coin}":\\s*{{[^}}]*?"low_price":\\s*([\\d.]+)', content)
            high_match = re.search(f'"{coin}":\\s*{{[^}}]*?"high_price":\\s*([\\d.]+)', content)
            
            if low_match and high_match:
                ranges[coin] = {
                    'low': float(low_match.group(1)),
                    'high': float(high_match.group(1))
                }
    except Exception as e:
        print(f"Error leyendo rangos: {e}")
    
    return ranges

def get_bot_pids():
    """Obtener PIDs de los procesos grid-trading-bot"""
    import subprocess
    try:
        result = subprocess.run(
            "pgrep -f 'grid-trading-bot.py'",
            shell=True, capture_output=True, text=True
        )
        pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid.isdigit()]
        return pids[0] if pids else None
    except:
        return None

def main():
    """Actualizar dashboard con datos en tiempo real de Binance"""
    print(f"🔄 Actualizando Grid Status - {datetime.now().strftime('%H:%M:%S')}")
    
    # Cargar credenciales
    creds = load_binance_credentials()
    if not creds.get('BINANCE_API_KEY'):
        print("❌ Error: Credenciales de Binance no encontradas")
        return False
    
    # Conectar a Binance
    try:
        exchange = ccxt.binance({
            'apiKey': creds['BINANCE_API_KEY'],
            'secret': creds['BINANCE_API_SECRET'],
            'enableRateLimit': True,
        })
    except Exception as e:
        print(f"❌ Error conectando a Binance: {e}")
        return False
    
    # Obtener rangos configurados
    grid_ranges = get_grid_ranges()
    
    # Obtener PID del bot
    bot_pid = get_bot_pids()
    
    # Inicializar status
    status_data = {
        "lastUpdate": datetime.now().isoformat(),
        "status": "active",
        "totalBots": 7,
        "totalOrders": 0,
        "bots": {},
        "tradesExecuted": 0,
        "totalPnL": 0.0
    }
    
    total_orders = 0
    
    # Consultar cada moneda
    for coin in COINS:
        symbol = f"{coin}/USDT"
        
        try:
            # Obtener órdenes abiertas
            open_orders = exchange.fetch_open_orders(symbol)
            orders_count = len(open_orders)
            
            # Obtener precio actual
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # Obtener balances
            balance = exchange.fetch_balance()
            balance_usdt = balance['free'].get('USDT', 0)
            balance_coin = balance['free'].get(coin, 0)
            
            # Obtener rangos configurados
            coin_range = grid_ranges.get(coin, {'low': 0, 'high': 0})
            
            status_data["bots"][coin] = {
                "active": orders_count > 0,
                "pid": bot_pid,
                "orders": orders_count,
                "price": price,
                "range": coin_range,
                "balanceUSDT": balance_usdt,
                "balanceCoin": balance_coin
            }
            
            total_orders += orders_count
            
            if orders_count > 0:
                print(f"✅ {coin}: {orders_count} órdenes @ ${price:,.2f}")
            else:
                print(f"⚪ {coin}: Sin órdenes @ ${price:,.2f}")
                
        except Exception as e:
            print(f"❌ Error con {coin}: {e}")
            status_data["bots"][coin] = {
                "active": False,
                "pid": bot_pid,
                "orders": 0,
                "price": 0,
                "range": grid_ranges.get(coin, {'low': 0, 'high': 0}),
                "balanceUSDT": 0,
                "balanceCoin": 0
            }
    
    status_data["totalOrders"] = total_orders
    
    # Guardar status
    try:
        DASHBOARD.mkdir(parents=True, exist_ok=True)
        with open(GRID_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
        
        print(f"\n✅ Status actualizado: {total_orders} órdenes totales")
        return True
        
    except Exception as e:
        print(f"❌ Error guardando status: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
