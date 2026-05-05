#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO TRADING DASHBOARD - CYBERPUNK EDITION
# ════════════════════════════════════════════════════════
# Dashboard avanzado con tiempo real
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

from flask import Flask, render_template, jsonify, request
from functools import wraps
import json
import os
import subprocess
from datetime import datetime
import glob
import base64

app = Flask(__name__)

WORKSPACE = "/home/overgon/.openclaw/workspace"
CRYPTO_BOTS = f"{WORKSPACE}/crypto-bots"
CONFIG_FILE = f"{WORKSPACE}/config/capital-config.sh"

# ════════════════════════════════════════════════════════
# 🔐 HTTP BASIC AUTH CONFIGURATION
# ════════════════════════════════════════════════════════

AUTH_FILE = f"{WORKSPACE}/dashboard/.htpasswd"

def check_auth(username, password):
    """Verificar credenciales usando subprocess con htpasswd"""
    try:
        result = subprocess.run(
            ['htpasswd', '-vb', AUTH_FILE, username, password],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Auth error: {e}")
        return False

def authenticate():
    """Retornar respuesta 401 con header WWW-Authenticate"""
    return (
        jsonify({'error': 'Authentication required'}),
        401,
        {'WWW-Authenticate': 'Basic realm="Perrobotillo Dashboard"'}
    )

def requires_auth(f):
    """Decorator para proteger rutas"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth:
            return authenticate()
        
        try:
            auth_type, auth_string = auth.split(None, 1)
            if auth_type.lower() != 'basic':
                return authenticate()
            
            decoded = base64.b64decode(auth_string).decode('utf-8')
            username, password = decoded.split(':', 1)
            
            if not check_auth(username, password):
                return authenticate()
                
        except Exception as e:
            print(f"Auth decode error: {e}")
            return authenticate()
        
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════
# FUNCIONES DE DATOS
# ════════════════════════════════════════════════════════

def get_portfolio_value():
    """Obtener valor total del portfolio DESDE BINANCE (tiempo real)"""
    try:
        import requests
        import time
        import hmac
        import hashlib
        
        # Leer API keys
        secrets_file = "/home/overgon/.openclaw/secrets/binance.env"
        if not os.path.exists(secrets_file):
            snapshot_file = f"{WORKSPACE}/portfolio-snapshot.json"
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    return float(data.get('value', 0))
            return 0.0
        
        with open(secrets_file, 'r') as f:
            lines = f.readlines()
            API_KEY = lines[0].split('=')[1].strip()
            API_SECRET = lines[1].split('=')[1].strip()
        
        # 1. Obtener balance de Binance
        timestamp = int(time.time() * 1000)
        params = f'recvWindow=5000&timestamp={timestamp}'
        signature = hmac.new(API_SECRET.encode(), params.encode(), hashlib.sha256).hexdigest()
        
        headers = {'X-MBX-APIKEY': API_KEY}
        url = f'https://api.binance.com/api/v3/account?{params}&signature={signature}'
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if 'balances' not in data:
            raise Exception(f"Binance API error: {data}")
        
        # 2. Obtener precios actuales
        prices_url = 'https://api.binance.com/api/v3/ticker/price'
        prices_response = requests.get(prices_url, timeout=10)
        prices = {p['symbol']: float(p['price']) for p in prices_response.json()}
        
        # 3. Calcular valor total en USDT
        total_usdt = 0.0
        
        for b in data['balances']:
            free = float(b['free'])
            locked = float(b['locked'])
            total = free + locked
            
            if total < 0.001:
                continue
            
            asset = b['asset']
            
            if asset in ['USDT', 'BUSD', 'USDC']:
                total_usdt += total
                continue
            
            symbol = f'{asset}USDT'
            if symbol in prices:
                total_usdt += total * prices[symbol]
        
        return total_usdt
        
    except Exception as e:
        print(f"Error getting portfolio: {e}")
        try:
            snapshot_file = f"{WORKSPACE}/portfolio-snapshot.json"
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    return float(data.get('value', 0))
        except:
            pass
        return 0.0

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
            except Exception as e:
                print(f"Error reading {coin} state: {e}")
                states[coin] = {"status": "error"}
        else:
            states[coin] = {"status": "no_data"}
    
    return states

def get_trade_history():
    """Obtener historial de trades"""
    history_file = f"{CRYPTO_BOTS}/trade-history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading trade history: {e}")
    
    return {
        "version": "1.0",
        "totalTrades": 0,
        "totalWins": 0,
        "totalLosses": 0,
        "netPnLUSDT": 0,
        "winRate": 0,
        "trades": []
    }

def get_daily_pnl():
    """Calcular P&L de las últimas 24 horas"""
    try:
        total_pnl = 0.0
        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
        
        for coin in coins:
            pnl_file = f"{CRYPTO_BOTS}/{coin}-daily-pnl.json"
            if os.path.exists(pnl_file):
                with open(pnl_file, 'r') as f:
                    data = json.load(f)
                    total_pnl += float(data.get('pnl', 0))
        
        return total_pnl
    except Exception as e:
        print(f"Error calculating daily PnL: {e}")
        return 0.0

def get_cashout_history():
    """Obtener historial de cashouts"""
    cashout_file = f"{CRYPTO_BOTS}/cashout-history.json"
    if os.path.exists(cashout_file):
        try:
            with open(cashout_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cashout history: {e}")
    
    return {"cashouts": [], "totalUSDT": 0, "totalMXN": 0}

def get_market_mode():
    """Obtener modo de mercado actual"""
    config_file = f"{CRYPTO_BOTS}/market-mode.conf"
    if os.path.exists(config_file):
        try:
            mode_data = {}
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        mode_data[key.strip()] = value.strip().strip('"')
            return mode_data
        except Exception as e:
            print(f"Error reading market mode: {e}")
    
    return {"MARKET_MODE": "LATERAL", "TP1": "2.5", "TP2": "5.0", "TP3": "7.0", "SL": "5.0"}

# ════════════════════════════════════════════════════════
# RUTAS
# ════════════════════════════════════════════════════════

@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
@requires_auth
def api_portfolio():
    """API endpoint para valor del portfolio"""
    value = get_portfolio_value()
    return jsonify({
        'value': value,
        'value_mx': value * 17.5,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
@requires_auth
def api_status():
    """API endpoint para estado completo"""
    portfolio_value = get_portfolio_value()
    trade_states = get_trade_states()
    trade_history = get_trade_history()
    daily_pnl = get_daily_pnl()
    cashout_history = get_cashout_history()
    market_mode = get_market_mode()
    
    # Calcular slots activos
    active_slots = sum(1 for coin, state in trade_states.items() 
                      if state.get('status') in ['IN_TRADE', 'TP1_HIT', 'TP2_HIT'])
    ready_slots = sum(1 for coin, state in trade_states.items() 
                     if state.get('status') == 'READY')
    total_slots = active_slots + ready_slots
    
    return jsonify({
        'portfolio': {
            'value': portfolio_value,
            'value_mx': portfolio_value * 17.5
        },
        'slots': {
            'total': total_slots,
            'active': active_slots,
            'ready': ready_slots,
            'percentage': round((active_slots / total_slots * 100) if total_slots > 0 else 0, 1)
        },
        'pnl': {
            '24h': daily_pnl,
            '24h_percent': round((daily_pnl / portfolio_value * 100) if portfolio_value > 0 else 0, 2)
        },
        'history': {
            'total_trades': trade_history.get('totalTrades', 0),
            'win_rate': trade_history.get('winRate', 0),
            'net_pnl': trade_history.get('netPnLUSDT', 0)
        },
        'cashout': {
            'total_usdt': cashout_history.get('totalUSDT', 0),
            'total_mxn': cashout_history.get('totalMXN', 0)
        },
        'market_mode': market_mode,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/prices')
@requires_auth
def api_prices():
    """API endpoint para precios en tiempo real"""
    try:
        import requests
        
        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
        prices = {}
        
        for coin in coins:
            try:
                response = requests.get(
                    f'https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT',
                    timeout=5
                )
                data = response.json()
                prices[coin] = {
                    'price': float(data.get('lastPrice', 0)),
                    'change_24h': float(data.get('priceChangePercent', 0)),
                    'volume': float(data.get('volume', 0)),
                    'high': float(data.get('highPrice', 0)),
                    'low': float(data.get('lowPrice', 0))
                }
            except Exception as e:
                print(f"Error getting {coin} price: {e}")
                prices[coin] = {'price': 0, 'change_24h': 0}
        
        return jsonify(prices)
        
    except Exception as e:
        print(f"Error getting prices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
@requires_auth
def api_trades():
    """API endpoint para historial de trades"""
    history = get_trade_history()
    return jsonify(history)

if __name__ == '__main__':
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🐕 PERROBOTILLO DASHBOARD - STARTING                 ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    print(f"📁 Workspace: {WORKSPACE}")
    print(f"🔐 Auth file: {AUTH_FILE}")
    print()
    print("🚀 Starting Flask server on port 8080...")
    print()
    app.run(host='0.0.0.0', port=8080, debug=False)
