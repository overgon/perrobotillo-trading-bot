#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 AUTO-ACTUALIZACIÓN DE RANGOS - GRID TRADING
# ════════════════════════════════════════════════════════
# Verifica precios actuales vs. rangos configurados
# Actualiza automáticamente si el precio está \u003e10% fuera del rango
# ════════════════════════════════════════════════════════

import json
import re
import sys
from pathlib import Path
import requests

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
CONFIG_FILE = WORKSPACE / "crypto-bots" / "grid-trading-bot.py"
LOG_FILE = WORKSPACE / "logs" / "grid-ranges-update.log"

COINS = ["BTC", "ETH", "BNB", "SOL", "ZEC", "XRP", "AVAX"]
RANGE_THRESHOLD = 0.10  # 10% fuera del rango → actualizar

def log(msg):
    print(msg)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{msg}\n")

def get_binance_prices():
    """Obtener precios actuales de Binance"""
    try:
        resp = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
        data = resp.json()
        prices = {}
        for item in data:
            if item['symbol'].endswith('USDT'):
                coin = item['symbol'].replace('USDT', '')
                prices[coin] = float(item['price'])
        return prices
    except Exception as e:
        log(f"❌ Error obteniendo precios: {e}")
        return None

def get_current_ranges():
    """Leer rangos actuales del archivo de configuración"""
    if not CONFIG_FILE.exists():
        log(f"❌ Config file no encontrado: {CONFIG_FILE}")
        return None
    
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    
    ranges = {}
    for coin in COINS:
        # Buscar configuración de cada moneda
        pattern = rf'"{coin}":\s*\{{[^}}]*?"low_price":\s*([\d.]+).*?"high_price":\s*([\d.]+)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            ranges[coin] = {
                'low': float(match.group(1)),
                'high': float(match.group(2))
            }
    
    return ranges

def calculate_new_range(current_price, coin):
    """Calcular nuevo rango ±15% del precio actual"""
    low = current_price * 0.85
    high = current_price * 1.15
    
    # Redondear a números bonitos
    if current_price > 10000:
        low = round(low / 1000) * 1000
        high = round(high / 1000) * 1000
    elif current_price > 100:
        low = round(low / 10) * 10
        high = round(high / 10) * 10
    elif current_price > 1:
        low = round(low, 2)
        high = round(high, 2)
    else:
        low = round(low, 4)
        high = round(high, 4)
    
    return low, high

def update_config_file(updates):
    """Actualizar archivo de configuración con nuevos rangos"""
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    
    for coin, new_range in updates.items():
        # Actualizar low_price
        low_pattern = rf'("{coin}":\s*\{{[^}}]*?"low_price":\s*)([\d.]+)'
        low_match = re.search(low_pattern, content, re.DOTALL)
        if low_match:
            old_low = low_match.group(2)
            new_content = re.sub(
                low_pattern,
                f'\\g<1>{new_range["low"]},',
                content,
                count=1,
                flags=re.DOTALL
            )
            content = new_content
            log(f"  {coin}: low {old_low} → {new_range['low']}")
        
        # Actualizar high_price
        high_pattern = rf'("{coin}":\s*\{{[^}}]*?"high_price":\s*)([\d.]+)'
        high_match = re.search(high_pattern, content, re.DOTALL)
        if high_match:
            old_high = high_match.group(2)
            new_content = re.sub(
                high_pattern,
                f'\\g<1>{new_range["high"]},',
                content,
                count=1,
                flags=re.DOTALL
            )
            content = new_content
            log(f"  {coin}: high {old_high} → {new_range['high']}")
    
    with open(CONFIG_FILE, 'w') as f:
        f.write(content)
    
    log(f"✅ Archivo actualizado: {CONFIG_FILE}")

def main():
    log("=" * 60)
    log("📊 AUTO-ACTUALIZACIÓN DE RANGOS - GRID TRADING")
    log("=" * 60)
    
    # Obtener precios actuales
    log("\n🔍 Obteniendo precios de Binance...")
    prices = get_binance_prices()
    if not prices:
        log("❌ No se pudieron obtener precios")
        return False
    
    for coin in COINS:
        if coin in prices:
            log(f"  {coin}: ${prices[coin]:,.2f}")
    
    # Obtener rangos actuales
    log("\n📋 Leyendo rangos actuales...")
    current_ranges = get_current_ranges()
    if not current_ranges:
        log("❌ No se pudieron leer rangos actuales")
        return False
    
    # Verificar qué rangos necesitan actualización
    log("\n🔍 Verificando rangos...")
    updates_needed = {}
    
    for coin in COINS:
        if coin not in prices or coin not in current_ranges:
            continue
        
        current_price = prices[coin]
        low = current_ranges[coin]['low']
        high = current_ranges[coin]['high']
        
        # Calcular thresholds (10% dentro del rango)
        low_threshold = low * 1.10
        high_threshold = high * 0.90
        
        # Verificar si necesita ajuste
        needs_update = False
        reason = ""
        
        if current_price > high_threshold:
            needs_update = True
            reason = f"Precio ${current_price:,.2f} > 90% del high (${high_threshold:,.2f})"
        elif current_price < low_threshold:
            needs_update = True
            reason = f"Precio ${current_price:,.2f} < 110% del low (${low_threshold:,.2f})"
        
        if needs_update:
            log(f"⚠️  {coin}: {reason}")
            new_low, new_high = calculate_new_range(current_price, coin)
            updates_needed[coin] = {'low': new_low, 'high': new_high}
            log(f"   Nuevo rango sugerido: ${new_low:,.2f} - ${new_high:,.2f}")
        else:
            log(f"✅ {coin}: Precio dentro de rango [${low:,.0f}-${high:,.0f}]")
    
    # Actualizar si es necesario
    if updates_needed:
        log(f"\n🔄 Actualizando {len(updates_needed)} monedas...")
        update_config_file(updates_needed)
        
        coins_updated = ", ".join(updates_needed.keys())
        log(f"\n✅ Rangos actualizados: {coins_updated}")
        return True
    else:
        log("\n✅ Todos los rangos están correctos - No se requieren cambios")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
