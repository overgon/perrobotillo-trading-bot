#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO TRADING DASHBOARD - CYBERPUNK EDITION
# ════════════════════════════════════════════════════════
# Dashboard avanzado con tiempo real
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

from flask import Flask, render_template, jsonify
import json
import os
import subprocess
from datetime import datetime
import glob

app = Flask(__name__)

WORKSPACE = "/home/overgon/.openclaw/workspace"
CRYPTO_BOTS = f"{WORKSPACE}/crypto-bots"
CONFIG_FILE = f"{WORKSPACE}/config/capital-config.sh"

# ════════════════════════════════════════════════════════
# FUNCIONES DE DATOS
# ════════════════════════════════════════════════════════

def get_portfolio_value():
    """Obtener valor total del portfolio"""
    try:
        snapshot_file = f"{WORKSPACE}/portfolio-snapshot.json"
        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
                return float(data.get('value', 0))
        
        # Si no existe, calcular desde Binance
        result = subprocess.run(
            f"cd {WORKSPACE} && ./crypto-exchange-compare.sh BTC,ETH,BNB,SOL,LINK,XRP,AVAX USDT 2>/dev/null | grep -oP '\\$[\\d,]+\\.\\d{{2}}' | tail -1 | tr -d '$,'",
            shell=True, capture_output=True, text=True
        )
        if result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting portfolio: {e}")
    
    return 0

def get_trade_states():
    """Obtener estado de trades para todas las coins"""
    coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
    states = {}
    
    for coin in coins:
        state_file = f"{CRYPTO_BOTS}/{coin}-trade-state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    states[coin] = json.load(f)
            except:
                states[coin] = {'error': True}
        else:
            states[coin] = {'error': 'File not found'}
    
    return states

def get_current_prices():
    """Obtener precios actuales de Binance"""
    try:
        result = subprocess.run(
            "curl -s 'https://api.binance.com/api/v3/ticker/price' | jq -r '.[] | select(.symbol | test(\"USDT$\")) | {(.symbol): .price}' | jq -s 'add'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
    except:
        pass
    
    return {}

def get_trade_history():
    """Obtener histórico de trades"""
    history_file = f"{CRYPTO_BOTS}/trade-history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'totalTrades': 0, 'totalWins': 0, 'totalLosses': 0, 'winRate': 0, 'trades': []}

def get_daily_pnl():
    """Obtener P&L del día actual"""
    today = datetime.now().strftime('%Y-%m-%d')
    pnl_data = {}
    
    for coin in ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']:
        pnl_file = f"{CRYPTO_BOTS}/{coin}-daily-pnl.json"
        if os.path.exists(pnl_file):
            try:
                with open(pnl_file, 'r') as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        pnl_data[coin] = data
            except:
                pass
    
    return pnl_data

def get_system_status():
    """Obtener estado del sistema"""
    status = {
        'api_binance': 'unknown',
        'ip_whitelist': 'unknown',
        'gateway': 'unknown',
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Verificar API Binance
    try:
        result = subprocess.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' 'https://api.binance.com/api/v3/ping'",
            shell=True, capture_output=True, text=True, timeout=5
        )
        status['api_binance'] = '✅ Online' if result.stdout.strip() == '200' else '❌ Error'
    except:
        status['api_binance'] = '❌ Error'
    
    # Verificar Gateway OpenClaw
    try:
        result = subprocess.run(
            "openclaw status 2>&1 | grep -q 'Gateway.*reachable' && echo 'OK' || echo 'Error'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        status['gateway'] = '✅ Online' if 'OK' in result.stdout else '❌ Offline'
    except:
        status['gateway'] = '❌ Error'
    
    # Verificar IP whitelist
    ip_file = f"{CRYPTO_BOTS}/.public_ip"
    if os.path.exists(ip_file):
        try:
            with open(ip_file, 'r') as f:
                ip = f.read().strip()
                if ip and len(ip) > 7:
                    status['ip_whitelist'] = f'✅ {ip}'
                else:
                    status['ip_whitelist'] = '⚠️ No configurada'
        except:
            status['ip_whitelist'] = '⚠️ Error'
    
    return status

# ════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    """API endpoint para datos en tiempo real"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'portfolio': {
            'total_usdt': get_portfolio_value(),
            'total_mxn': get_portfolio_value() * 17.5  # Aproximado
        },
        'coins': get_trade_states(),
        'prices': get_current_prices(),
        'history': get_trade_history(),
        'daily_pnl': get_daily_pnl(),
        'system': get_system_status()
    }
    return jsonify(data)

@app.route('/api/prices')
def api_prices():
    """API endpoint solo para precios (más rápido)"""
    return jsonify(get_current_prices())

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("🐕 Perrobotillo Dashboard - Cyberpunk Edition")
    print("🚀 Iniciando servidor...")
    print("📡 Acceso: http://192.168.3.215:8080")
    print("⚠️  Presiona Ctrl+C para detener")
    
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=False,
        threaded=True
    )
