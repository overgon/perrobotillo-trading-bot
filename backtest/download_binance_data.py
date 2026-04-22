#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║  📥 BINANCE DATA DOWNLOADER                           ║
║  Perrobotillo Trading Bot - Backtest Data            ║
╚═══════════════════════════════════════════════════════╝

Descarga datos históricos de Binance Futures API
"""

import requests
import csv
import os
from datetime import datetime, timedelta
import time
import json

# ============================================
# CONFIGURACIÓN
# ============================================

COINS = ['BNBUSDT', 'AVAXUSDT']  # Solo las 2 coins 100% win rate
INTERVAL = '1h'  # 1 hora
DAYS_TO_DOWNLOAD = 180  # 6 meses para validación robusta
OUTPUT_DIR = '/home/overgon/.openclaw/workspace/backtest/data'
RATE_LIMIT_DELAY = 0.5  # Segundos entre requests (evitar rate limit)

# ============================================
# FUNCIONES
# ============================================

def get_klines(symbol, interval, start_time, end_time):
    """Descargar klines/candlesticks de Binance"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    
    all_klines = []
    current_start = start_time
    
    while current_start < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': int(current_start.timestamp() * 1000),
            'endTime': int(end_time.timestamp() * 1000),
            'limit': 1000  # Máximo permitido por Binance
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            klines = response.json()
            if not klines:
                break
            
            all_klines.extend(klines)
            
            # Avanzar al último timestamp + 1
            last_time = datetime.fromtimestamp(klines[-1][0] / 1000)
            current_start = last_time + timedelta(minutes=1)
            
            print(f"  {symbol}: {len(all_klines)} velas descargadas...")
            
            # Rate limit
            time.sleep(RATE_LIMIT_DELAY)
            
        except Exception as e:
            print(f"  ❌ Error descargando {symbol}: {e}")
            time.sleep(2)  # Esperar más en caso de error
            continue
    
    return all_klines

def parse_kline(kline):
    """Parsear un kline de Binance"""
    # Binance kline format: [open_time, open, high, low, close, volume, ...]
    return {
        'timestamp': datetime.fromtimestamp(kline[0] / 1000).isoformat(),
        'open': float(kline[1]),
        'high': float(kline[2]),
        'low': float(kline[3]),
        'close': float(kline[4]),
        'volume': float(kline[5])
    }

def save_to_csv(klines, symbol, output_dir):
    """Guardar klines en CSV"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Nombre del archivo: BTCUSDT_1h_90days.csv
    filename = f"{symbol}_{INTERVAL}_{DAYS_TO_DOWNLOAD}days.csv"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', newline='') as f:
        fieldnames = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for kline in klines:
            parsed = parse_kline(kline)
            writer.writerow(parsed)
    
    print(f"  ✅ Guardado: {filepath} ({len(klines)} velas)")
    return filepath

def download_all_coins():
    """Descargar datos de todas las coins"""
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  📥 BINANCE DATA DOWNLOADER                           ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=DAYS_TO_DOWNLOAD)
    
    print(f"📅 Período: {start_time.strftime('%Y-%m-%d')} → {end_time.strftime('%Y-%m-%d')}")
    print(f"⏱️  Intervalo: {INTERVAL}")
    print(f"🪙 Coins: {len(COINS)}")
    print()
    
    all_files = []
    total_klines = 0
    
    for i, coin in enumerate(COINS, 1):
        print(f"[{i}/{len(COINS)}] Descargando {coin}...")
        
        klines = get_klines(coin, INTERVAL, start_time, end_time)
        
        if klines:
            filepath = save_to_csv(klines, coin, OUTPUT_DIR)
            all_files.append(filepath)
            total_klines += len(klines)
        else:
            print(f"  ❌ No se pudieron descargar datos para {coin}")
        
        print()
    
    # Crear archivo de metadatos
    metadata = {
        'download_date': datetime.now().isoformat(),
        'period': {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'days': DAYS_TO_DOWNLOAD
        },
        'interval': INTERVAL,
        'coins': COINS,
        'files': all_files,
        'total_klines': total_klines
    }
    
    metadata_file = os.path.join(OUTPUT_DIR, 'metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("="*60)
    print("✅ DESCARGA COMPLETADA")
    print(f"   Total velas: {total_klines}")
    print(f"   Archivos: {len(all_files)}")
    print(f"   Metadata: {metadata_file}")
    print("="*60)
    
    return metadata

if __name__ == "__main__":
    try:
        metadata = download_all_coins()
        print("\n💾 Datos listos para backtest!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Descarga interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
